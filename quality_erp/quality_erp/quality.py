"""Quality management services: 7-stage supplier quality lifecycle, return quarantine, and review bundles."""

import base64
import hashlib
import json
import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)
from quality_erp.api_security import (
    check_rate_limit,
    record_security_audit_event,
    validate_int,
    validate_string,
)
from quality_erp.security import (
    assert_can_approve_quality_gate,
    get_current_user,
    is_quality_admin,
    is_quality_manager,
    require_role,
)

QUALITY_STAGES = (
    "1. First Submission",
    "2. Second Submission",
    "3. Size Set Submission",
    "4. Production Go Ahead",
    "5. Inline Visit",
    "6. Mid-line Visit",
    "7. Final Inspection",
)


def check_stage_prerequisites(
    stage: str,
    supplier: str,
    item_code: str,
    purchase_order: str | None = None,
    current_inspection: str | None = None,
    visit_number: int = 1,
):
    """Ensure all ordered preceding stages have an approved inspection.
    
    Supports multiple visits for 5. Inline Visit and 6. Mid-line Visit:
    - Subsequent inline visits (visit_number > 1) require Production Go Ahead to be approved.
    - Subsequent mid-line visits (visit_number > 1) require Production Go Ahead to be approved.
    """
    if stage not in QUALITY_STAGES:
        frappe.throw(_("Invalid quality stage '{0}'").format(stage), frappe.ValidationError)

    stage_idx = QUALITY_STAGES.index(stage)
    if stage_idx == 0:
        return

    # For subsequent visits of multi-visit stages, prerequisite is Gate 4 (Production Go Ahead)
    if stage in ("5. Inline Visit", "6. Mid-line Visit") and int(visit_number or 1) > 1:
        prereq_stages = ["4. Production Go Ahead"]
    else:
        prereq_stages = QUALITY_STAGES[:stage_idx]

    filters = {
        "supplier": supplier,
        "item_code": item_code,
    }
    inspections = frappe.get_all(
        "Supplier Quality Inspection",
        filters=filters,
        fields=["stage", "status", "result", "purchase_order"],
    )
    approved_set = set()
    for row in inspections:
        if not purchase_order or not row.purchase_order or row.purchase_order == purchase_order:
            if row.status == "Approved" or row.get("result") == "Passed":
                approved_set.add(row.stage)

    for req in prereq_stages:
        if req not in approved_set:
            frappe.throw(
                _(
                    "Cannot approve stage '{0}': prerequisite stage '{1}' has not been approved for {2}."
                ).format(stage, req, item_code),
                frappe.ValidationError,
            )


def _populate_checklist_items(doc, checklist_template=None, checklist_items=None):
    """Populate or snapshot checklist items onto inspection report for immutable historical retention."""
    if checklist_items and isinstance(checklist_items, (list, tuple)):
        for itm in checklist_items:
            if isinstance(itm, dict) and itm.get("check_point"):
                doc.append("checklist_items", {
                    "check_point": itm["check_point"],
                    "check_type": itm.get("check_type") or "Visual Inspection",
                    "target_value": itm.get("target_value"),
                    "actual_value": itm.get("actual_value"),
                    "status": itm.get("status") or "Pending",
                    "criticality": itm.get("criticality") or "Major",
                    "notes": itm.get("notes"),
                })
    elif checklist_template and frappe.db.exists("Quality Checklist Template", checklist_template):
        template_doc = frappe.get_doc("Quality Checklist Template", checklist_template)
        doc.checklist_template_version = template_doc.version
        for t_item in template_doc.items:
            doc.append("checklist_items", {
                "check_point": t_item.check_point,
                "check_type": t_item.check_type,
                "target_value": t_item.target_value,
                "actual_value": None,
                "status": "Pending",
                "criticality": t_item.criticality,
                "notes": t_item.guidelines,
            })


def _populate_measurements(doc, measurements=None):
    """Populate measurements and compute variances and tolerance status."""
    if measurements and isinstance(measurements, (list, tuple)):
        for m in measurements:
            if isinstance(m, dict) and m.get("parameter_name"):
                target = flt(m.get("spec_target"))
                actual = flt(m.get("actual_reading"))
                tol_plus = flt(m.get("tolerance_plus", 0.5))
                tol_minus = flt(m.get("tolerance_minus", 0.5))
                variance = round(actual - target, 4)
                status = "Out of Spec" if (actual > (target + tol_plus) or actual < (target - tol_minus)) else "In Spec"
                doc.append("measurements", {
                    "parameter_name": m["parameter_name"],
                    "spec_size": m.get("spec_size"),
                    "spec_target": target,
                    "tolerance_plus": tol_plus,
                    "tolerance_minus": tol_minus,
                    "actual_reading": actual,
                    "variance": variance,
                    "reading_status": status,
                    "uom": m.get("uom") or "cm",
                    "notes": m.get("notes"),
                })


def _populate_defects(doc, defects=None):
    """Populate defects table with codes, severity, counts, and dispositions."""
    if defects and isinstance(defects, (list, tuple)):
        for d in defects:
            if isinstance(d, dict) and d.get("defect_code"):
                doc.append("defects", {
                    "defect_code": d["defect_code"],
                    "defect_description": d.get("defect_description") or d["defect_code"],
                    "severity": d.get("severity") or "Minor",
                    "defect_count": int(d.get("defect_count") or 1),
                    "sample_reference": d.get("sample_reference"),
                    "action_required": d.get("action_required"),
                })


def _build_evidence_photo_rows(evidence_photos=None, photo_evidence=None, revision=1, user=None):
    rows = []
    user = user or frappe.session.user
    now = now_datetime()

    if isinstance(evidence_photos, str):
        try:
            evidence_photos = json.loads(evidence_photos)
        except Exception:
            evidence_photos = None

    if evidence_photos and isinstance(evidence_photos, (list, tuple)):
        for idx, item in enumerate(evidence_photos):
            if isinstance(item, dict):
                file_url = item.get("file") or item.get("photo_evidence")
                if file_url:
                    rows.append({
                        "file": file_url,
                        "caption": item.get("caption") or f"Inspection evidence {idx + 1}",
                        "evidence_type": item.get("evidence_type") or "Fabric Defect",
                        "display_order": item.get("display_order") or idx,
                        "uploader": item.get("uploader") or user,
                        "uploaded_on": item.get("uploaded_on") or now,
                        "revision": item.get("revision") or revision,
                    })
            elif isinstance(item, str):
                rows.append({
                    "file": item,
                    "caption": f"Inspection photo {idx + 1}",
                    "evidence_type": "Fabric Defect",
                    "display_order": idx,
                    "uploader": user,
                    "uploaded_on": now,
                    "revision": revision,
                })

    if not rows and photo_evidence:
        rows.append({
            "file": photo_evidence,
            "caption": "Primary inspection photograph",
            "evidence_type": "General Defect",
            "display_order": 0,
            "uploader": user,
            "uploaded_on": now,
            "revision": revision,
        })

    return rows


@frappe.whitelist(methods=["POST"])
def create_checklist_template(
    template_name: str,
    item_group: str | None = None,
    product_category: str | None = None,
    version: int = 1,
    description: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Create a versioned checklist template for product groups/categories."""
    check_rate_limit("create_checklist_template", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})

    template_name = validate_string(template_name, "Template Name", max_len=140, required=True)
    version = validate_int(version, "Version", min_val=1, max_val=1000) or 1

    existing = frappe.db.get_value(
        "Quality Checklist Template",
        {"template_name": template_name, "version": version},
        "name",
    )
    if existing:
        frappe.throw(
            _("Checklist template '{0}' version {1} already exists ({2}).").format(
                template_name, version, existing
            ),
            frappe.DuplicateEntryError,
        )

    doc = frappe.get_doc({
        "doctype": "Quality Checklist Template",
        "template_name": template_name,
        "item_group": item_group,
        "product_category": product_category,
        "version": version,
        "status": "Active",
        "description": description,
    })

    if items and isinstance(items, (list, tuple)):
        for itm in items:
            if isinstance(itm, dict) and itm.get("check_point"):
                doc.append("items", {
                    "check_point": itm["check_point"],
                    "check_type": itm.get("check_type") or "Visual Inspection",
                    "criticality": itm.get("criticality") or "Major",
                    "is_mandatory": cint(itm.get("is_mandatory", 1)),
                    "target_value": itm.get("target_value"),
                    "min_value": flt(itm.get("min_value")),
                    "max_value": flt(itm.get("max_value")),
                    "uom": itm.get("uom"),
                    "guidelines": itm.get("guidelines"),
                })

    doc.insert()

    record_security_audit_event(
        "Quality Checklist Template Created",
        "Quality Checklist Template",
        doc.name,
        {"template_name": template_name, "version": version, "item_count": len(doc.items)},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["GET", "POST"])
def get_checklist_template(
    template_name: str | None = None,
    item_group: str | None = None,
    version: int | None = None,
) -> dict:
    """Retrieve active checklist template and its check points."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})

    filters = {"status": "Active"}
    if template_name:
        filters["template_name"] = template_name
    elif item_group:
        filters["item_group"] = item_group

    if version:
        filters["version"] = int(version)

    templates = frappe.get_all(
        "Quality Checklist Template",
        filters=filters,
        fields=["name", "template_name", "item_group", "product_category", "version", "description", "status"],
        order_by="version desc",
        limit=1,
    )
    if not templates:
        return {}

    t_doc = frappe.get_doc("Quality Checklist Template", templates[0].name)
    return t_doc.as_dict()


@frappe.whitelist(methods=["POST"])
def create_quality_inspection(
    supplier,
    item_code,
    stage,
    purchase_order=None,
    production_quality_cycle=None,
    company=None,
    production_lot="01",
    season=None,
    visit_number=1,
    visit_type=None,
    location_details=None,
    checklist_template=None,
    checklist_items=None,
    measurements=None,
    defects=None,
    sampling_plan="AQL 2.5 Level II",
    lot_size=0,
    sample_size=0,
    passed_quantity=0,
    failed_quantity=0,
    max_allowed_defects=0,
    status="Pending Review",
    result="Pending Review",
    recommendation=None,
    recommendation_notes=None,
    corrective_action_required=0,
    corrective_action=None,
    corrective_action_owner=None,
    corrective_action_owner_name=None,
    corrective_action_due_date=None,
    spec_notes=None,
    photo_evidence=None,
    revision=1,
    supersedes=None,
    evidence_photos=None,
    fabric_quality_score=None,
    stitching_quality_score=None,
):
    """Create a new supplier quality inspection entry with multi-photo evidence and stage reports."""
    check_rate_limit("create_quality_inspection", limit=60, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    supplier = validate_string(supplier, "Supplier", max_len=140, required=True)
    item_code = validate_string(item_code, "Item Code", max_len=140, required=True)
    stage = validate_string(stage, "Stage", max_len=140, required=True, allowed_values=QUALITY_STAGES)
    purchase_order = validate_string(purchase_order, "Purchase Order", max_len=140)
    revision = validate_int(revision, "Revision", min_val=1, max_val=1000) or 1
    visit_number = validate_int(visit_number, "Visit Number", min_val=1, max_val=100) or 1

    # Check multi-company and supplier User Permission boundaries
    if not is_quality_admin(user):
        if company:
            allowed_comps = frappe.get_all(
                "User Permission",
                filters={"user": user, "allow": "Company"},
                pluck="for_value",
            )
            if allowed_comps and company not in allowed_comps:
                frappe.throw(_("Permission denied for company {0}.").format(company), frappe.PermissionError)

        allowed_supps = frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Supplier"},
            pluck="for_value",
        )
        if allowed_supps and supplier not in allowed_supps:
            frappe.throw(_("Permission denied for supplier {0}.").format(supplier), frappe.PermissionError)

    photo_rows = _build_evidence_photo_rows(evidence_photos, photo_evidence, revision=revision, user=user)
    primary_photo = photo_evidence or (photo_rows[0]["file"] if photo_rows else None)

    # Auto-resolve or create production_quality_cycle if not given
    if not production_quality_cycle and frappe.db.table_exists("Production Quality Cycle"):
        from quality_erp.cycle import generate_cycle_key
        comp = company or (frappe.db.get_value("Purchase Order", purchase_order, "company") if purchase_order else None)
        if not comp:
            comp = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if comp:
            try:
                ckey = generate_cycle_key(comp, supplier, item_code, purchase_order, production_lot, season)
                production_quality_cycle = frappe.db.get_value("Production Quality Cycle", {"cycle_key": ckey}, "name")
            except Exception:
                pass

    if isinstance(checklist_items, str):
        try:
            checklist_items = json.loads(checklist_items)
        except Exception:
            checklist_items = None

    if isinstance(measurements, str):
        try:
            measurements = json.loads(measurements)
        except Exception:
            measurements = None

    if isinstance(defects, str):
        try:
            defects = json.loads(defects)
        except Exception:
            defects = None

    if not visit_type:
        if "First Submission" in stage or "Fit" in stage:
            visit_type = "Fit Review"
        elif "Inline" in stage:
            visit_type = "Initial Inline" if int(visit_number or 1) == 1 else "Follow-up Inline"
        elif "Mid-line" in stage:
            visit_type = "Mid-line Visit 1" if int(visit_number or 1) == 1 else "Mid-line Visit 2"
        elif "Final" in stage:
            visit_type = "Final Inspection"
        else:
            visit_type = "Ad-Hoc Visit"

    try:
        doc = frappe.get_doc(
            {
                "doctype": "Supplier Quality Inspection",
                "company": company,
                "supplier": supplier,
                "item_code": item_code,
                "purchase_order": purchase_order,
                "production_quality_cycle": production_quality_cycle,
                "production_lot": production_lot or "01",
                "season": season,
                "stage": stage,
                "visit_number": visit_number,
                "visit_type": visit_type,
                "location_details": location_details,
                "status": status or "Pending Review",
                "result": result or "Pending Review",
                "recommendation": recommendation,
                "recommendation_notes": recommendation_notes,
                "sampling_plan": sampling_plan or "AQL 2.5 Level II",
                "lot_size": cint(lot_size),
                "sample_size": cint(sample_size),
                "passed_quantity": cint(passed_quantity),
                "failed_quantity": cint(failed_quantity),
                "max_allowed_defects": cint(max_allowed_defects),
                "revision": int(revision or 1),
                "supersedes": supersedes,
                "is_latest": 1,
                "inspector": user,
                "spec_measurements": spec_notes,
                "fabric_quality_score": fabric_quality_score,
                "stitching_quality_score": stitching_quality_score,
                "corrective_action_required": cint(corrective_action_required or (1 if corrective_action else 0)),
                "corrective_action": corrective_action,
                "corrective_action_owner": corrective_action_owner,
                "corrective_action_owner_name": corrective_action_owner_name,
                "corrective_action_due_date": corrective_action_due_date,
                "corrective_action_status": "Open" if corrective_action else None,
                "photo_evidence": primary_photo,
                "evidence_photos": photo_rows,
                "checklist_template": checklist_template,
            }
        )

        _populate_checklist_items(doc, checklist_template, checklist_items)
        _populate_measurements(doc, measurements)
        _populate_defects(doc, defects)

        doc.insert()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Quality Inspection Created",
        "Supplier Quality Inspection",
        doc.name,
        {
            "stage": stage,
            "supplier": supplier,
            "item_code": item_code,
            "revision": doc.revision,
            "visit_number": doc.visit_number,
            "photo_count": len(photo_rows),
            "checklist_items_count": len(doc.get("checklist_items") or []),
            "measurements_count": len(doc.get("measurements") or []),
            "defects_count": len(doc.get("defects") or []),
        },
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def revise_quality_inspection(
    inspection_name,
    spec_notes=None,
    photo_evidence=None,
    evidence_photos=None,
    checklist_items=None,
    measurements=None,
    defects=None,
    sampling_plan=None,
    lot_size=None,
    sample_size=None,
    passed_quantity=None,
    failed_quantity=None,
    result=None,
    recommendation=None,
    recommendation_notes=None,
    corrective_action=None,
    corrective_action_status=None,
    resolution_notes=None,
    fabric_quality_score=None,
    stitching_quality_score=None,
    comments=None,
):
    """Create a new versioned revision of a rejected or pending inspection report, preserving prior evidence and checklist history."""
    check_rate_limit("revise_quality_inspection", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    inspection_name = validate_string(inspection_name, "Inspection Name", max_len=140, required=True)

    # Lock original inspection
    rows = frappe.db.sql(
        """
        SELECT name, supplier, item_code, purchase_order, stage, status, revision, company,
               production_quality_cycle, production_lot, season, visit_number, visit_type, location_details,
               gate_locked
        FROM `tabSupplier Quality Inspection`
        WHERE name = %s
        FOR UPDATE
        """,
        (inspection_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Inspection {0} does not exist.").format(inspection_name), frappe.DoesNotExistError)
    curr = rows[0]
    if curr.get("gate_locked"):
        frappe.throw(_("Cannot revise a gate-locked inspection report."), frappe.ValidationError)
    if curr.status in ("Approved", "Conditionally Approved"):
        frappe.throw(_("Cannot revise an already approved inspection report."), frappe.ValidationError)

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    doc.check_permission("write")

    new_revision = (curr.revision or 1) + 1

    # Preserve all prior photos from superseded revision
    combined_photos = []
    for prev_photo in doc.get("evidence_photos") or []:
        combined_photos.append({
            "file": prev_photo.file,
            "caption": prev_photo.caption,
            "evidence_type": prev_photo.evidence_type,
            "display_order": prev_photo.display_order,
            "uploader": prev_photo.uploader,
            "uploaded_on": prev_photo.uploaded_on,
            "revision": prev_photo.revision or curr.revision,
        })

    # Append newly uploaded photos for this revision
    new_photos = _build_evidence_photo_rows(evidence_photos, photo_evidence, revision=new_revision, user=user)
    combined_photos.extend(new_photos)

    primary_photo = (
        (new_photos[0]["file"] if new_photos else None)
        or photo_evidence
        or doc.photo_evidence
        or (combined_photos[0]["file"] if combined_photos else None)
    )

    if isinstance(checklist_items, str):
        try:
            checklist_items = json.loads(checklist_items)
        except Exception:
            checklist_items = None
    if isinstance(measurements, str):
        try:
            measurements = json.loads(measurements)
        except Exception:
            measurements = None
    if isinstance(defects, str):
        try:
            defects = json.loads(defects)
        except Exception:
            defects = None

    try:
        new_doc = frappe.get_doc({
            "doctype": "Supplier Quality Inspection",
            "company": curr.company,
            "supplier": curr.supplier,
            "item_code": curr.item_code,
            "purchase_order": curr.purchase_order,
            "production_quality_cycle": curr.production_quality_cycle,
            "production_lot": curr.production_lot,
            "season": curr.season,
            "stage": curr.stage,
            "visit_number": curr.visit_number,
            "visit_type": curr.visit_type,
            "location_details": curr.location_details,
            "status": "Pending Review",
            "result": result or "Pending Review",
            "recommendation": recommendation or doc.recommendation,
            "recommendation_notes": recommendation_notes or doc.recommendation_notes,
            "sampling_plan": sampling_plan or doc.sampling_plan,
            "lot_size": cint(lot_size) if lot_size is not None else doc.lot_size,
            "sample_size": cint(sample_size) if sample_size is not None else doc.sample_size,
            "passed_quantity": cint(passed_quantity) if passed_quantity is not None else doc.passed_quantity,
            "failed_quantity": cint(failed_quantity) if failed_quantity is not None else doc.failed_quantity,
            "revision": new_revision,
            "supersedes": inspection_name,
            "is_latest": 1,
            "inspector": user,
            "spec_measurements": spec_notes or doc.spec_measurements,
            "fabric_quality_score": fabric_quality_score if fabric_quality_score is not None else doc.fabric_quality_score,
            "stitching_quality_score": stitching_quality_score if stitching_quality_score is not None else doc.stitching_quality_score,
            "corrective_action_required": 1 if (corrective_action or doc.corrective_action) else 0,
            "corrective_action": corrective_action or doc.corrective_action,
            "corrective_action_owner": doc.corrective_action_owner,
            "corrective_action_owner_name": doc.corrective_action_owner_name,
            "corrective_action_due_date": doc.corrective_action_due_date,
            "corrective_action_status": corrective_action_status or doc.corrective_action_status,
            "resolution_notes": resolution_notes or doc.resolution_notes,
            "photo_evidence": primary_photo,
            "evidence_photos": combined_photos,
            "checklist_template": doc.checklist_template,
            "checklist_template_version": doc.checklist_template_version,
            "comments": comments or f"Revision {new_revision} superseding {inspection_name}",
        })

        # If updated checklist items supplied, use them; else preserve from original
        if checklist_items is not None:
            _populate_checklist_items(new_doc, None, checklist_items)
        else:
            for item in doc.get("checklist_items") or []:
                new_doc.append("checklist_items", {
                    "check_point": item.check_point,
                    "check_type": item.check_type,
                    "target_value": item.target_value,
                    "actual_value": item.actual_value,
                    "status": item.status,
                    "criticality": item.criticality,
                    "notes": item.notes,
                })

        # If updated measurements supplied, use them; else preserve from original
        if measurements is not None:
            _populate_measurements(new_doc, measurements)
        else:
            for m in doc.get("measurements") or []:
                new_doc.append("measurements", {
                    "parameter_name": m.parameter_name,
                    "spec_size": m.spec_size,
                    "spec_target": m.spec_target,
                    "tolerance_plus": m.tolerance_plus,
                    "tolerance_minus": m.tolerance_minus,
                    "actual_reading": m.actual_reading,
                    "variance": m.variance,
                    "reading_status": m.reading_status,
                    "uom": m.uom,
                    "notes": m.notes,
                })

        # If updated defects supplied, use them; else preserve from original
        if defects is not None:
            _populate_defects(new_doc, defects)
        else:
            for d in doc.get("defects") or []:
                new_doc.append("defects", {
                    "defect_code": d.defect_code,
                    "defect_description": d.defect_description,
                    "severity": d.severity,
                    "defect_count": d.defect_count,
                    "sample_reference": d.sample_reference,
                    "action_required": d.action_required,
                })

        new_doc.insert()

        # Update original inspection to mark superseded and no longer latest
        frappe.db.set_value(
            "Supplier Quality Inspection",
            inspection_name,
            {"superseded_by": new_doc.name, "is_latest": 0},
            update_modified=False,
        )

    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Quality Inspection Revised",
        "Supplier Quality Inspection",
        new_doc.name,
        {
            "supersedes": inspection_name,
            "stage": new_doc.stage,
            "revision": new_revision,
            "photo_count": len(combined_photos),
        },
    )

    return new_doc.as_dict()


@frappe.whitelist(methods=["GET", "POST"])
def compare_inspection_revisions(original_name: str, revision_name: str) -> dict:
    """Side-by-side comparison between two inspection report revisions."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})

    original_name = validate_string(original_name, "Original Inspection Name", max_len=140, required=True)
    revision_name = validate_string(revision_name, "Revision Inspection Name", max_len=140, required=True)

    if not frappe.db.exists("Supplier Quality Inspection", original_name):
        frappe.throw(_("Inspection {0} does not exist.").format(original_name), frappe.DoesNotExistError)
    if not frappe.db.exists("Supplier Quality Inspection", revision_name):
        frappe.throw(_("Inspection {0} does not exist.").format(revision_name), frappe.DoesNotExistError)

    orig = frappe.get_doc("Supplier Quality Inspection", original_name)
    rev = frappe.get_doc("Supplier Quality Inspection", revision_name)

    orig.check_permission("read")
    rev.check_permission("read")

    # Build checklist diff
    orig_checklist = {item.check_point: item for item in orig.get("checklist_items") or []}
    rev_checklist = {item.check_point: item for item in rev.get("checklist_items") or []}
    all_checkpoints = sorted(set(orig_checklist.keys()) | set(rev_checklist.keys()))

    checklist_diff = []
    for cp in all_checkpoints:
        o_item = orig_checklist.get(cp)
        r_item = rev_checklist.get(cp)
        checklist_diff.append({
            "check_point": cp,
            "target_value": (r_item or o_item).target_value,
            "criticality": (r_item or o_item).criticality,
            "original_status": o_item.status if o_item else "Not Tested",
            "revision_status": r_item.status if r_item else "Not Tested",
            "original_actual": o_item.actual_value if o_item else None,
            "revision_actual": r_item.actual_value if r_item else None,
            "status_changed": (o_item.status if o_item else None) != (r_item.status if r_item else None),
        })

    # Build measurements diff
    orig_measurements = {(m.parameter_name, m.spec_size): m for m in orig.get("measurements") or []}
    rev_measurements = {(m.parameter_name, m.spec_size): m for m in rev.get("measurements") or []}
    all_meas_keys = sorted(set(orig_measurements.keys()) | set(rev_measurements.keys()))

    measurements_diff = []
    for (param, size) in all_meas_keys:
        o_m = orig_measurements.get((param, size))
        r_m = rev_measurements.get((param, size))
        measurements_diff.append({
            "parameter_name": param,
            "spec_size": size,
            "spec_target": (r_m or o_m).spec_target,
            "uom": (r_m or o_m).uom,
            "original_reading": o_m.actual_reading if o_m else None,
            "revision_reading": r_m.actual_reading if r_m else None,
            "original_variance": o_m.variance if o_m else None,
            "revision_variance": r_m.variance if r_m else None,
            "original_status": o_m.reading_status if o_m else None,
            "revision_status": r_m.reading_status if r_m else None,
            "status_changed": (o_m.reading_status if o_m else None) != (r_m.reading_status if r_m else None),
        })

    # Build defects diff
    orig_defects = {d.defect_code: d for d in orig.get("defects") or []}
    rev_defects = {d.defect_code: d for d in rev.get("defects") or []}
    all_defect_codes = sorted(set(orig_defects.keys()) | set(rev_defects.keys()))

    defects_diff = []
    for dcode in all_defect_codes:
        o_d = orig_defects.get(dcode)
        r_d = rev_defects.get(dcode)
        o_cnt = o_d.defect_count if o_d else 0
        r_cnt = r_d.defect_count if r_d else 0
        defects_diff.append({
            "defect_code": dcode,
            "defect_description": (r_d or o_d).defect_description,
            "severity": (r_d or o_d).severity,
            "original_count": o_cnt,
            "revision_count": r_cnt,
            "count_diff": r_cnt - o_cnt,
            "resolved": (o_cnt > 0 and r_cnt == 0),
        })

    # Photos comparison
    orig_photos = [p.as_dict() for p in orig.get("evidence_photos") or []]
    rev_photos = [p.as_dict() for p in rev.get("evidence_photos") or []]
    newly_added_photos = [p for p in rev_photos if p.get("revision") == rev.revision]

    return {
        "original_name": orig.name,
        "revision_name": rev.name,
        "original_revision": orig.revision,
        "revision_number": rev.revision,
        "stage": rev.stage,
        "supplier": rev.supplier,
        "item_code": rev.item_code,
        "metadata_diff": {
            "status": {"original": orig.status, "revision": rev.status},
            "result": {"original": orig.result, "revision": rev.result},
            "recommendation": {"original": orig.recommendation, "revision": rev.recommendation},
            "inspector": {"original": orig.inspector, "revision": rev.inspector},
            "inspection_date": {"original": str(orig.inspection_date), "revision": str(rev.inspection_date)},
            "sample_size": {"original": orig.sample_size, "revision": rev.sample_size},
            "passed_quantity": {"original": orig.passed_quantity, "revision": rev.passed_quantity},
            "failed_quantity": {"original": orig.failed_quantity, "revision": rev.failed_quantity},
            "critical_defects_count": {"original": orig.critical_defects_count, "revision": rev.critical_defects_count},
            "major_defects_count": {"original": orig.major_defects_count, "revision": rev.major_defects_count},
            "minor_defects_count": {"original": orig.minor_defects_count, "revision": rev.minor_defects_count},
            "fabric_quality_score": {"original": orig.fabric_quality_score, "revision": rev.fabric_quality_score},
            "stitching_quality_score": {"original": orig.stitching_quality_score, "revision": rev.stitching_quality_score},
        },
        "checklist_diff": checklist_diff,
        "measurements_diff": measurements_diff,
        "defects_diff": defects_diff,
        "corrective_actions_diff": {
            "required": {"original": orig.corrective_action_required, "revision": rev.corrective_action_required},
            "action": {"original": orig.corrective_action, "revision": rev.corrective_action},
            "status": {"original": orig.corrective_action_status, "revision": rev.corrective_action_status},
            "due_date": {"original": str(orig.corrective_action_due_date) if orig.corrective_action_due_date else None, "revision": str(rev.corrective_action_due_date) if rev.corrective_action_due_date else None},
            "resolution_notes": {"original": orig.resolution_notes, "revision": rev.resolution_notes},
        },
        "evidence_photos_diff": {
            "original_photo_count": len(orig_photos),
            "revision_photo_count": len(rev_photos),
            "new_photos_added_count": len(newly_added_photos),
            "newly_added_photos": newly_added_photos,
        },
    }



@frappe.whitelist(methods=["POST"])
def approve_quality_gate(inspection_name, notes=None):
    """Approve a quality inspection gate. Critical gates require Administrator approval."""
    check_rate_limit("approve_quality_gate", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    inspection_name = validate_string(inspection_name, "Inspection Name", max_len=140, required=True)

    # Row-lock transition
    rows = frappe.db.sql(
        "SELECT name, status, stage, supplier, item_code, purchase_order, gate_locked FROM `tabSupplier Quality Inspection` WHERE name = %s FOR UPDATE",
        (inspection_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Inspection {0} does not exist.").format(inspection_name), frappe.DoesNotExistError)

    current = rows[0]
    if current.status == "Approved":
        return frappe.get_doc("Supplier Quality Inspection", inspection_name).as_dict()
    if current.get("gate_locked"):
        frappe.throw(_("Inspection {0} is locked to an approved gate decision and cannot be modified.").format(inspection_name), frappe.ValidationError)

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    doc.check_permission("write")

    # High-security enforcement: Gate 4 (Production Go Ahead) & Gate 7 (Final Inspection)
    # require Administrator role.
    if "Production Go Ahead" in doc.stage:
        assert_can_approve_quality_gate("Production Go Ahead", user)
    elif "Final Inspection" in doc.stage:
        assert_can_approve_quality_gate("Final Inspection", user)

    # Enforce strict 7-stage quality lifecycle ordering
    check_stage_prerequisites(
        stage=doc.stage,
        supplier=doc.supplier,
        item_code=doc.item_code,
        purchase_order=doc.purchase_order,
        current_inspection=doc.name,
    )

    doc.status = "Approved"
    doc.approved_by = user
    doc.approval_date = now_datetime()
    if notes:
        doc.comments = (doc.comments or "") + f"\nApproval notes ({user}): {notes}"
    try:
        doc.save()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Quality Gate Approved",
        "Supplier Quality Inspection",
        doc.name,
        {"stage": doc.stage, "supplier": doc.supplier, "approved_by": user},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def reject_quality_gate(inspection_name, reason):
    """Reject a quality inspection gate with mandatory reason."""
    check_rate_limit("reject_quality_gate", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    inspection_name = validate_string(inspection_name, "Inspection Name", max_len=140, required=True)
    reason = validate_string(reason, "Rejection Reason", max_len=1000, required=True)

    rows = frappe.db.sql(
        "SELECT name, status, stage, supplier FROM `tabSupplier Quality Inspection` WHERE name = %s FOR UPDATE",
        (inspection_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Inspection {0} does not exist.").format(inspection_name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    doc.check_permission("write")

    doc.status = "Rejected"
    doc.approved_by = user
    doc.approval_date = now_datetime()
    doc.comments = (doc.comments or "") + f"\nRejection ({user}): {reason}"
    try:
        doc.save()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Quality Gate Rejected",
        "Supplier Quality Inspection",
        doc.name,
        {"stage": doc.stage, "supplier": doc.supplier, "reason": reason},
    )

    return doc.as_dict()


@frappe.whitelist()
def get_quality_review_bundle(supplier, item_code, purchase_order=None, gate="Production Go Ahead"):
    """Retrieve comprehensive administrative review bundle for critical quality gates."""
    require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})

    if "Production Go Ahead" in gate:
        target_gate = "4. Production Go Ahead"
        prereq_stages = QUALITY_STAGES[:3]
    elif "Final Inspection" in gate:
        target_gate = "7. Final Inspection"
        prereq_stages = QUALITY_STAGES[:6]
    else:
        frappe.throw(_("Invalid gate '{0}'. Must be Production Go Ahead or Final Inspection.").format(gate))

    filters = {
        "supplier": supplier,
        "item_code": item_code,
    }
    all_reports = frappe.get_all(
        "Supplier Quality Inspection",
        filters=filters,
        fields=[
            "name",
            "stage",
            "status",
            "revision",
            "supersedes",
            "inspector",
            "inspection_date",
            "approved_by",
            "approval_date",
            "spec_measurements",
            "photo_evidence",
            "comments",
            "purchase_order",
            "creation",
            "modified",
        ],
        order_by="creation asc, revision asc",
    )

    stage_reports = {}
    approved_stages = set()
    for r in all_reports:
        # Load child evidence photos for comprehensive review
        try:
            r["evidence_photos"] = frappe.get_all(
                "Quality Inspection Evidence",
                filters={"parent": r.name, "parenttype": "Supplier Quality Inspection"},
                fields=["name", "file", "caption", "evidence_type", "display_order", "uploader", "uploaded_on", "revision"],
                order_by="revision asc, display_order asc",
            )
        except Exception:
            r["evidence_photos"] = []

        if not purchase_order or not r.purchase_order or r.purchase_order == purchase_order:
            stage_reports[r.stage] = r
            if r.status == "Approved":
                approved_stages.add(r.stage)

    missing = [req for req in prereq_stages if req not in approved_stages]

    return {
        "gate": target_gate,
        "supplier": supplier,
        "item_code": item_code,
        "purchase_order": purchase_order,
        "ready_for_approval": len(missing) == 0,
        "missing_prerequisites": missing,
        "stage_reports": stage_reports,
        "all_reports": all_reports,
    }


@frappe.whitelist(methods=["POST"])
def record_return_quarantine(
    retailer,
    delivery_note,
    item_code,
    quantity,
    return_reason,
    quarantine_warehouse=None,
    return_delivery_note=None,
    photo_evidence=None,
    evidence_photos=None,
    notes=None,
):
    """Record an item intake into the quarantine warehouse for quality inspection."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "Clothing Warehouse Manager"})
    user = get_current_user()

    photo_rows = _build_evidence_photo_rows(evidence_photos, photo_evidence, revision=1, user=user)
    primary_photo = photo_evidence or (photo_rows[0]["file"] if photo_rows else None)

    doc = frappe.get_doc(
        {
            "doctype": "Return Quarantine",
            "retailer": retailer,
            "delivery_note": delivery_note,
            "return_delivery_note": return_delivery_note,
            "item_code": item_code,
            "quantity": float(quantity),
            "quarantine_warehouse": quarantine_warehouse,
            "return_reason": return_reason,
            "inspection_status": "Quarantined",
            "photo_evidence": primary_photo,
            "evidence_photos": photo_rows,
            "inspected_by": user,
            "inspected_on": now_datetime(),
            "inspection_notes": notes,
        }
    ).insert()

    record_security_audit_event(
        "Return Quarantine Created",
        "Return Quarantine",
        doc.name,
        {
            "retailer": retailer,
            "delivery_note": delivery_note,
            "item_code": item_code,
            "quantity": float(quantity),
            "photo_count": len(photo_rows),
        },
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def inspect_return_quarantine(quarantine_name, decision, notes=None, photo_evidence=None, evidence_photos=None):
    """Quality department inspection decision on returned quarantined garments."""
    check_rate_limit("inspect_return_quarantine", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    valid_decisions = {
        "Passed Refurbishment": "Inspected - Passed Refurbishment",
        "Scrapped": "Inspected - Scrapped",
    }
    decision = str(decision or "").strip()
    if decision not in valid_decisions:
        frappe.throw(
            _("Invalid inspection decision. Must be one of: {0}").format(", ".join(valid_decisions.keys())),
            frappe.ValidationError,
        )

    quarantine_name = str(quarantine_name or "").strip()
    rows = frappe.db.sql(
        "SELECT name, inspection_status FROM `tabReturn Quarantine` WHERE name = %s FOR UPDATE",
        (quarantine_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    curr = rows[0]
    if curr.inspection_status != "Quarantined":
        frappe.throw(
            _("Return Quarantine {0} has already been inspected (current status: {1}).").format(
                quarantine_name, curr.inspection_status
            ),
            frappe.ValidationError,
        )

    doc = frappe.get_doc("Return Quarantine", quarantine_name)
    doc.check_permission("write")
    doc.inspection_status = valid_decisions[decision]
    doc.inspected_by = user
    doc.inspected_on = now_datetime()
    if notes:
        doc.inspection_notes = (doc.inspection_notes or "") + f"\nInspection ({user}): {notes.strip()}"

    new_photos = _build_evidence_photo_rows(evidence_photos, photo_evidence, revision=1, user=user)
    if new_photos:
        for p in new_photos:
            doc.append("evidence_photos", p)
        if not doc.photo_evidence:
            doc.photo_evidence = new_photos[0]["file"]
    elif photo_evidence:
        doc.photo_evidence = photo_evidence

    doc.save()

    record_security_audit_event(
        "Return Quarantine Inspected",
        "Return Quarantine",
        doc.name,
        {"decision": decision, "status": doc.inspection_status, "photo_count": len(doc.get("evidence_photos") or [])},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["GET", "POST"])
def get_quality_dashboard_summary(supplier=None, item_code=None):
    """Return high-level summary counts for quality inspections and return quarantines."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})

    stage_counts = {stage: 0 for stage in QUALITY_STAGES}
    conditions = ["status = 'Pending Review'"]
    params = []
    if supplier:
        conditions.append("supplier = %s")
        params.append(str(supplier).strip())
    if item_code:
        conditions.append("item_code = %s")
        params.append(str(item_code).strip())

    where_clause = " AND ".join(conditions)
    rows = frappe.db.sql(
        f"""
        SELECT stage, COUNT(*) as cnt
        FROM `tabSupplier Quality Inspection`
        WHERE {where_clause}
        GROUP BY stage
        """,
        tuple(params),
        as_dict=True,
    )
    total_pending = 0
    for r in rows:
        if r.stage in stage_counts:
            stage_counts[r.stage] = int(r.cnt)
            total_pending += int(r.cnt)

    pga_pending = stage_counts.get("4. Production Go Ahead", 0)
    final_pending = stage_counts.get("7. Final Inspection", 0)

    q_rows = frappe.db.sql(
        """
        SELECT inspection_status, COUNT(*) as cnt, COALESCE(SUM(quantity), 0) as total_qty
        FROM `tabReturn Quarantine`
        GROUP BY inspection_status
        """,
        as_dict=True,
    )
    quarantine_summary = {
        "quarantined_count": 0,
        "quarantined_qty": 0.0,
        "passed_refurbishment_count": 0,
        "scrapped_count": 0,
    }
    for r in q_rows:
        if r.inspection_status == "Quarantined":
            quarantine_summary["quarantined_count"] = int(r.cnt)
            quarantine_summary["quarantined_qty"] = float(r.total_qty or 0.0)
        elif r.inspection_status == "Inspected - Passed Refurbishment":
            quarantine_summary["passed_refurbishment_count"] = int(r.cnt)
        elif r.inspection_status == "Inspected - Scrapped":
            quarantine_summary["scrapped_count"] = int(r.cnt)

    recent_inspections = frappe.get_all(
        "Supplier Quality Inspection",
        fields=["name", "supplier", "item_code", "stage", "status", "creation", "modified"],
        order_by="creation desc",
        limit=5,
    )
    recent_quarantines = frappe.get_all(
        "Return Quarantine",
        fields=["name", "retailer", "item_code", "quantity", "return_reason", "inspection_status", "creation"],
        order_by="creation desc",
        limit=5,
    )

    return {
        "total_pending_inspections": total_pending,
        "pending_by_stage": stage_counts,
        "critical_gates_pending": {
            "production_go_ahead": pga_pending,
            "final_inspection": final_pending,
        },
        "quarantine_summary": quarantine_summary,
        "recent_inspections": recent_inspections,
        "recent_quarantines": recent_quarantines,
    }


# ===========================================================================
# SESSION 13: CRITICAL GATES, EXACT REVISION LOCKING, CORRECTIONS,
# COMPLETE HISTORY, CONTROLLED PDF REPORT BUNDLES, DISPOSITIONS & CLAIMS
# ===========================================================================


def _resolve_cycle(cycle_name=None, supplier=None, item_code=None, purchase_order=None, ptype="read"):
    """Resolve and assert access to a Production Quality Cycle."""
    from quality_erp.cycle import assert_cycle_access

    if cycle_name:
        return assert_cycle_access(cycle_name, ptype=ptype)

    filters = {}
    if supplier:
        filters["supplier"] = supplier
    if item_code:
        filters["item_code"] = item_code
    if purchase_order:
        filters["purchase_order"] = purchase_order

    if not filters:
        frappe.throw(_("Either cycle_name or supplier and item_code must be provided."), frappe.ValidationError)

    cycles = frappe.get_all("Production Quality Cycle", filters=filters, pluck="name", limit=1)
    if not cycles:
        frappe.throw(_("No Production Quality Cycle found matching {0}.").format(filters), frappe.DoesNotExistError)

    return assert_cycle_access(cycles[0], ptype=ptype)


def _compute_bundle_hash(cycle_name: str, cycle_key: str, reviewed_revisions: dict) -> str:
    """Compute deterministic cryptographic SHA-256 revision hash for a gate bundle."""
    tokens = [f"CYCLE:{cycle_name}", f"KEY:{cycle_key}"]
    for stage, rev_info in sorted(reviewed_revisions.items()):
        name = rev_info.get("name") or "None"
        rev = rev_info.get("revision") or 0
        status = rev_info.get("status") or "None"
        tokens.append(f"{stage}={name}@r{rev}#{status}")
    combined = "||".join(tokens)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


@frappe.whitelist(methods=["GET", "POST"])
def get_production_go_ahead_review_bundle(
    cycle_name: str | None = None,
    supplier: str | None = None,
    item_code: str | None = None,
    purchase_order: str | None = None,
) -> dict:
    """Retrieve comprehensive review bundle for Gate 4: Production Go Ahead."""
    require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
    cycle = _resolve_cycle(cycle_name, supplier, item_code, purchase_order, ptype="read")

    prereq_stages = ["1. First Submission", "2. Second Submission", "3. Size Set Submission"]
    inspections = frappe.get_all(
        "Supplier Quality Inspection",
        filters={"production_quality_cycle": cycle.name, "is_latest": 1},
        fields=[
            "name", "stage", "status", "result", "revision", "inspector", "inspection_date",
            "sample_size", "passed_quantity", "failed_quantity", "critical_defects_count",
            "major_defects_count", "minor_defects_count", "fabric_quality_score",
            "stitching_quality_score", "comments", "recommendation", "recommendation_notes",
            "corrective_action_required", "corrective_action", "corrective_action_status",
            "correction_request_reason", "gate_locked", "locked_gate_decision",
        ],
        order_by="creation asc",
    )

    stage_map = {}
    reviewed_revisions = {}
    for insp in inspections:
        stage_map[insp.stage] = insp
        # Load evidence photos
        insp["evidence_photos"] = frappe.get_all(
            "Quality Inspection Evidence",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["name", "file", "caption", "evidence_type", "display_order", "uploader", "uploaded_on", "revision"],
            order_by="revision asc, display_order asc",
        )
        # Load checklist items
        insp["checklist_items"] = frappe.get_all(
            "Quality Inspection Checklist Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["check_point", "check_type", "target_value", "actual_value", "status", "criticality", "notes"],
        )
        # Load measurements
        insp["measurements"] = frappe.get_all(
            "Quality Inspection Reading Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["parameter_name", "spec_target", "tolerance_plus", "tolerance_minus", "actual_reading", "variance", "reading_status", "uom"],
        )
        # Load defects
        insp["defects"] = frappe.get_all(
            "Quality Inspection Defect Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["defect_code", "defect_description", "severity", "defect_count", "action_required"],
        )
        if insp.stage in prereq_stages:
            reviewed_revisions[insp.stage] = {
                "name": insp.name,
                "revision": insp.revision,
                "status": insp.status,
                "result": insp.result,
            }

    missing_stages = []
    blocking_reasons = []
    for stg in prereq_stages:
        if stg not in stage_map:
            missing_stages.append(stg)
            blocking_reasons.append(_("Missing inspection report for stage '{0}'").format(stg))
        else:
            doc = stage_map[stg]
            if doc.status not in ("Approved", "Conditionally Approved") and doc.result not in ("Passed", "Conditionally Passed"):
                blocking_reasons.append(_("Stage '{0}' is not approved or passed (status: {1}, result: {2})").format(stg, doc.status, doc.result))
            if doc.status == "Correction Requested":
                blocking_reasons.append(_("Stage '{0}' has open correction request: {1}").format(stg, doc.correction_request_reason))

    bundle_hash = _compute_bundle_hash(cycle.name, cycle.cycle_key, reviewed_revisions)

    return {
        "gate": "4. Production Go Ahead",
        "cycle_name": cycle.name,
        "cycle_key": cycle.cycle_key,
        "company": cycle.company,
        "supplier": cycle.supplier,
        "item_code": cycle.item_code,
        "purchase_order": cycle.purchase_order,
        "production_lot": cycle.production_lot,
        "season": cycle.season,
        "go_ahead_status": cycle.go_ahead_status,
        "go_ahead_approved_by": cycle.go_ahead_approved_by,
        "go_ahead_date": str(cycle.go_ahead_date) if cycle.go_ahead_date else None,
        "go_ahead_conditions": cycle.go_ahead_conditions,
        "ready_for_decision": len(blocking_reasons) == 0,
        "missing_stages": missing_stages,
        "blocking_reasons": blocking_reasons,
        "reviewed_revisions": reviewed_revisions,
        "bundle_hash": bundle_hash,
        "stage_reports": stage_map,
        "authority_notice": _("Authorized administrators only: approving Gate 4 authorizes bulk fabric cutting and manufacturing start. Does not post stock or GL entries."),
    }


@frappe.whitelist(methods=["POST"])
def decide_production_go_ahead(
    cycle_name: str,
    decision: str,
    reviewed_revisions: dict | str,
    conditions: str | None = None,
    notes: str | None = None,
    bundle_hash: str | None = None,
) -> dict:
    """Decide Gate 4 (Production Go Ahead) under strict exact-revision locking.
    
    Authority: Clothing Business Administrator or System Manager only.
    Authorizes bulk cutting and production start. Does NOT post stock or GL entries.
    """
    check_rate_limit("decide_production_go_ahead", limit=20, window_seconds=60)
    require_role({ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()

    cycle_name = validate_string(cycle_name, "Cycle Name", max_len=140, required=True)
    decision = validate_string(decision, "Decision", allowed_values={"Approved", "Conditionally Approved", "Rejected"})

    if isinstance(reviewed_revisions, str):
        try:
            reviewed_revisions = json.loads(reviewed_revisions)
        except Exception:
            frappe.throw(_("Invalid reviewed_revisions JSON payload."), frappe.ValidationError)

    if not reviewed_revisions or not isinstance(reviewed_revisions, dict):
        frappe.throw(_("reviewed_revisions mapping is mandatory for exact-revision locking."), frappe.ValidationError)

    if decision == "Conditionally Approved" and not conditions:
        frappe.throw(_("Conditions and resolution terms are mandatory for Conditional Approval."), frappe.ValidationError)
    if decision == "Rejected" and not (notes or conditions):
        frappe.throw(_("A rejection reason is mandatory when rejecting Production Go Ahead."), frappe.ValidationError)

    # Lock Production Quality Cycle under SELECT ... FOR UPDATE
    cycle_rows = frappe.db.sql(
        """
        SELECT name, go_ahead_status, company, supplier, item_code, purchase_order, cycle_key
        FROM `tabProduction Quality Cycle`
        WHERE name = %s
        FOR UPDATE
        """,
        (cycle_name,),
        as_dict=True,
    )
    if not cycle_rows:
        frappe.throw(_("Production Quality Cycle {0} not found.").format(cycle_name), frappe.DoesNotExistError)

    curr_cycle = cycle_rows[0]
    # Check decision immutability
    if curr_cycle.go_ahead_status in ("Approved", "Conditionally Approved"):
        frappe.throw(
            _("Production Go Ahead has already been decided ('{0}') and cannot be overwritten.").format(curr_cycle.go_ahead_status),
            frappe.ValidationError,
        )

    # Verify and Lock Each Exact Reviewed Revision
    locked_inspections = []
    for stage, rev_info in reviewed_revisions.items():
        insp_name = rev_info.get("name")
        expected_rev = cint(rev_info.get("revision"))

        rows = frappe.db.sql(
            """
            SELECT name, stage, revision, is_latest, status, gate_locked
            FROM `tabSupplier Quality Inspection`
            WHERE name = %s
            FOR UPDATE
            """,
            (insp_name,),
            as_dict=True,
        )
        if not rows:
            frappe.throw(_("Inspection {0} referenced in reviewed revisions does not exist.").format(insp_name), frappe.DoesNotExistError)

        row = rows[0]
        if cint(row.revision) != expected_rev:
            frappe.throw(
                _(
                    "Revision mismatch for stage '{0}': reviewed revision was {1}, but active revision is {2}. "
                    "Another user or inspector has modified the report. Please reload the review screen."
                ).format(stage, expected_rev, row.revision),
                frappe.ValidationError,
            )
        if not row.is_latest:
            frappe.throw(
                _(
                    "Revision mismatch for stage '{1}': inspection {0} is no longer the latest revision. "
                    "Please review the updated revision."
                ).format(insp_name, stage),
                frappe.ValidationError,
            )
        locked_inspections.append(row.name)

    # Compute and verify cryptographic bundle hash
    current_hash = _compute_bundle_hash(cycle_name, curr_cycle.cycle_key, reviewed_revisions)
    if bundle_hash and bundle_hash != current_hash:
        frappe.throw(
            _("Cryptographic bundle hash mismatch: review screen state differs from database state. Please reload."),
            frappe.ValidationError,
        )

    now = now_datetime()
    cycle_doc = frappe.get_doc("Production Quality Cycle", cycle_name)
    cycle_doc.check_permission("write")
    cycle_doc.go_ahead_status = decision
    cycle_doc.go_ahead_approved_by = user
    cycle_doc.go_ahead_date = now
    cycle_doc.go_ahead_conditions = conditions or notes
    cycle_doc.go_ahead_reviewed_revisions = json.dumps(reviewed_revisions)

    if decision in ("Approved", "Conditionally Approved"):
        cycle_doc.status = "Production in Progress"
        # Lock each reviewed inspection report to prevent tampering
        for iname in locked_inspections:
            frappe.db.set_value(
                "Supplier Quality Inspection",
                iname,
                {
                    "gate_locked": 1,
                    "locked_gate_decision": f"Gate 4: Production Go Ahead ({decision})",
                },
                update_modified=False,
            )
    else:
        cycle_doc.status = "On Hold"

    cycle_doc.flags.ignore_permissions = True
    cycle_doc.save()

    record_security_audit_event(
        "Production Go Ahead Decided",
        "Production Quality Cycle",
        cycle_doc.name,
        {
            "decision": decision,
            "approved_by": user,
            "bundle_hash": current_hash,
            "reviewed_revisions": reviewed_revisions,
            "conditions": conditions or notes,
        },
    )

    frappe.db.commit()

    return {
        "success": True,
        "cycle_name": cycle_doc.name,
        "decision": decision,
        "go_ahead_status": cycle_doc.go_ahead_status,
        "status": cycle_doc.status,
        "approved_by": user,
        "approved_date": str(now),
        "bundle_hash": current_hash,
        "authorizes": "Bulk cutting and production commencement authorized.",
    }


@frappe.whitelist(methods=["GET", "POST"])
def get_final_inspection_review_bundle(
    cycle_name: str | None = None,
    supplier: str | None = None,
    item_code: str | None = None,
    purchase_order: str | None = None,
) -> dict:
    """Retrieve comprehensive review bundle across all seven stages for Gate 7: Final Inspection."""
    require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
    cycle = _resolve_cycle(cycle_name, supplier, item_code, purchase_order, ptype="read")

    all_inspections = frappe.get_all(
        "Supplier Quality Inspection",
        filters={"production_quality_cycle": cycle.name},
        fields=[
            "name", "stage", "visit_number", "visit_type", "status", "result", "revision",
            "is_latest", "inspector", "inspection_date", "sampling_plan", "lot_size",
            "sample_size", "passed_quantity", "failed_quantity", "critical_defects_count",
            "major_defects_count", "minor_defects_count", "recommendation", "recommendation_notes",
            "corrective_action_required", "corrective_action", "corrective_action_status",
            "correction_request_reason", "gate_locked", "locked_gate_decision",
        ],
        order_by="stage asc, visit_number asc, revision desc",
    )

    stage_breakdown = {stg: [] for stg in QUALITY_STAGES}
    latest_by_stage = {}
    reviewed_revisions = {}
    open_corrective_actions = []

    for insp in all_inspections:
        # Load photos
        insp["evidence_photos"] = frappe.get_all(
            "Quality Inspection Evidence",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["name", "file", "caption", "evidence_type", "display_order", "uploader", "uploaded_on", "revision"],
            order_by="revision asc, display_order asc",
        )
        # Load checklist items
        insp["checklist_items"] = frappe.get_all(
            "Quality Inspection Checklist Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["check_point", "check_type", "target_value", "actual_value", "status", "criticality"],
        )
        # Load measurements
        insp["measurements"] = frappe.get_all(
            "Quality Inspection Reading Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["parameter_name", "spec_target", "tolerance_plus", "tolerance_minus", "actual_reading", "variance", "reading_status", "uom"],
        )
        # Load defects
        insp["defects"] = frappe.get_all(
            "Quality Inspection Defect Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["defect_code", "defect_description", "severity", "defect_count", "action_required"],
        )

        stg = insp.stage
        if stg in stage_breakdown:
            stage_breakdown[stg].append(insp)

        if insp.is_latest:
            stage_key = f"{stg} [Visit {insp.visit_number}]" if stg in ("5. Inline Visit", "6. Mid-line Visit") else stg
            latest_by_stage[stage_key] = insp
            reviewed_revisions[stage_key] = {
                "name": insp.name,
                "revision": insp.revision,
                "status": insp.status,
                "result": insp.result,
                "visit_number": insp.visit_number,
            }

        if insp.corrective_action_required and insp.corrective_action_status in ("Open", "In Progress", "Overdue"):
            open_corrective_actions.append({
                "inspection": insp.name,
                "stage": insp.stage,
                "action": insp.corrective_action,
                "status": insp.corrective_action_status,
            })

    blocking_reasons = []
    # 1. Gate 4 Check
    if cycle.go_ahead_status not in ("Approved", "Conditionally Approved"):
        blocking_reasons.append(_("Production Go Ahead (Gate 4) has not been approved (current status: {0}).").format(cycle.go_ahead_status))

    # 2. Check required preceding inspection stages: 1, 2, 3, 5, 6
    required_inspection_stages = [
        "1. First Submission",
        "2. Second Submission",
        "3. Size Set Submission",
        "5. Inline Visit",
        "6. Mid-line Visit",
    ]
    for req_stage in required_inspection_stages:
        matching = [i for i in all_inspections if i.stage == req_stage and i.is_latest]
        if not matching:
            blocking_reasons.append(_("Missing required stage report for '{0}'.").format(req_stage))
        else:
            latest_insp = matching[0]
            if latest_insp.status not in ("Approved", "Conditionally Approved") and latest_insp.result not in ("Passed", "Conditionally Passed"):
                blocking_reasons.append(_("Stage '{0}' is not approved (status: {1}, result: {2}).").format(req_stage, latest_insp.status, latest_insp.result))

    # 3. Final inspection stage 7 report presence
    final_stage_reports = [i for i in all_inspections if i.stage == "7. Final Inspection" and i.is_latest]
    if not final_stage_reports:
        blocking_reasons.append(_("Final Inspection (Stage 7) report has not been submitted."))

    # 4. Open CAPA check
    if open_corrective_actions:
        blocking_reasons.append(_("{0} open corrective actions remain unresolved.").format(len(open_corrective_actions)))

    bundle_hash = _compute_bundle_hash(cycle.name, cycle.cycle_key, reviewed_revisions)

    return {
        "gate": "7. Final Inspection",
        "cycle_name": cycle.name,
        "cycle_key": cycle.cycle_key,
        "company": cycle.company,
        "supplier": cycle.supplier,
        "item_code": cycle.item_code,
        "purchase_order": cycle.purchase_order,
        "production_lot": cycle.production_lot,
        "season": cycle.season,
        "go_ahead_status": cycle.go_ahead_status,
        "go_ahead_approved_by": cycle.go_ahead_approved_by,
        "go_ahead_date": str(cycle.go_ahead_date) if cycle.go_ahead_date else None,
        "final_inspection_status": cycle.final_inspection_status,
        "final_inspection_approved_by": cycle.final_inspection_approved_by,
        "final_inspection_date": str(cycle.final_inspection_date) if cycle.final_inspection_date else None,
        "final_inspection_notes": cycle.final_inspection_notes,
        "clearance_status": cycle.clearance_status,
        "purchase_receipt_cleared": cycle.purchase_receipt_cleared,
        "ready_for_decision": len(blocking_reasons) == 0,
        "blocking_reasons": blocking_reasons,
        "open_corrective_actions": open_corrective_actions,
        "reviewed_revisions": reviewed_revisions,
        "bundle_hash": bundle_hash,
        "stage_breakdown": stage_breakdown,
        "latest_by_stage": latest_by_stage,
        "authority_notice": _("Authorized administrators only: approving Gate 7 clears goods for warehouse Purchase Receipt intake. Does not post stock, payables or GL entries."),
    }


@frappe.whitelist(methods=["POST"])
def decide_final_inspection(
    cycle_name: str,
    decision: str,
    reviewed_revisions: dict | str,
    conditions: str | None = None,
    notes: str | None = None,
    bundle_hash: str | None = None,
) -> dict:
    """Decide Gate 7 (Final Inspection) under strict exact-revision locking.
    
    Authority: Clothing Business Administrator or System Manager only.
    Authorizes goods receipt clearance for ERPNext Purchase Receipt. Does NOT post stock or GL entries.
    """
    check_rate_limit("decide_final_inspection", limit=20, window_seconds=60)
    require_role({ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()

    cycle_name = validate_string(cycle_name, "Cycle Name", max_len=140, required=True)
    decision = validate_string(decision, "Decision", allowed_values={"Approved", "Conditionally Approved", "Rejected"})

    if isinstance(reviewed_revisions, str):
        try:
            reviewed_revisions = json.loads(reviewed_revisions)
        except Exception:
            frappe.throw(_("Invalid reviewed_revisions JSON payload."), frappe.ValidationError)

    if not reviewed_revisions or not isinstance(reviewed_revisions, dict):
        frappe.throw(_("reviewed_revisions mapping is mandatory for exact-revision locking."), frappe.ValidationError)

    if decision == "Conditionally Approved" and not conditions:
        frappe.throw(_("Conditions and resolution terms are mandatory for Conditional Approval."), frappe.ValidationError)
    if decision == "Rejected" and not (notes or conditions):
        frappe.throw(_("A rejection reason is mandatory when rejecting Final Inspection."), frappe.ValidationError)

    # Lock Production Quality Cycle under SELECT ... FOR UPDATE
    cycle_rows = frappe.db.sql(
        """
        SELECT name, go_ahead_status, final_inspection_status, company, supplier, item_code, purchase_order, cycle_key
        FROM `tabProduction Quality Cycle`
        WHERE name = %s
        FOR UPDATE
        """,
        (cycle_name,),
        as_dict=True,
    )
    if not cycle_rows:
        frappe.throw(_("Production Quality Cycle {0} not found.").format(cycle_name), frappe.DoesNotExistError)

    curr_cycle = cycle_rows[0]
    if curr_cycle.final_inspection_status in ("Approved", "Conditionally Approved"):
        frappe.throw(
            _("Final Inspection has already been decided ('{0}') and cannot be overwritten.").format(curr_cycle.final_inspection_status),
            frappe.ValidationError,
        )

    if curr_cycle.go_ahead_status not in ("Approved", "Conditionally Approved"):
        frappe.throw(
            _("Cannot decide Final Inspection: Gate 4 (Production Go Ahead) must be approved first (current status: {0}).").format(curr_cycle.go_ahead_status),
            frappe.ValidationError,
        )

    # Verify and Lock Each Exact Reviewed Revision
    locked_inspections = []
    for stage_key, rev_info in reviewed_revisions.items():
        insp_name = rev_info.get("name")
        expected_rev = cint(rev_info.get("revision"))

        rows = frappe.db.sql(
            """
            SELECT name, stage, revision, is_latest, status, gate_locked
            FROM `tabSupplier Quality Inspection`
            WHERE name = %s
            FOR UPDATE
            """,
            (insp_name,),
            as_dict=True,
        )
        if not rows:
            frappe.throw(_("Inspection {0} referenced in reviewed revisions does not exist.").format(insp_name), frappe.DoesNotExistError)

        row = rows[0]
        if cint(row.revision) != expected_rev:
            frappe.throw(
                _(
                    "Revision mismatch for stage '{0}': reviewed revision was {1}, but active revision is {2}. "
                    "Another user or inspector has modified the report. Please reload the review screen."
                ).format(stage_key, expected_rev, row.revision),
                frappe.ValidationError,
            )
        if not row.is_latest:
            frappe.throw(
                _(
                    "Revision mismatch for stage '{1}': inspection {0} is no longer the latest revision. "
                    "Please review the updated revision."
                ).format(insp_name, stage_key),
                frappe.ValidationError,
            )
        locked_inspections.append(row.name)

    current_hash = _compute_bundle_hash(cycle_name, curr_cycle.cycle_key, reviewed_revisions)
    if bundle_hash and bundle_hash != current_hash:
        frappe.throw(
            _("Cryptographic bundle hash mismatch: review screen state differs from database state. Please reload."),
            frappe.ValidationError,
        )

    now = now_datetime()
    cycle_doc = frappe.get_doc("Production Quality Cycle", cycle_name)
    cycle_doc.check_permission("write")
    cycle_doc.final_inspection_status = decision
    cycle_doc.final_inspection_approved_by = user
    cycle_doc.final_inspection_date = now
    cycle_doc.final_inspection_notes = conditions or notes
    cycle_doc.final_inspection_reviewed_revisions = json.dumps(reviewed_revisions)

    if decision in ("Approved", "Conditionally Approved"):
        cycle_doc.status = "Final Inspection Approved"
        cycle_doc.clearance_status = "Cleared for Receipt"
        cycle_doc.purchase_receipt_cleared = 1

        for iname in locked_inspections:
            frappe.db.set_value(
                "Supplier Quality Inspection",
                iname,
                {
                    "gate_locked": 1,
                    "locked_gate_decision": f"Gate 7: Final Inspection ({decision})",
                },
                update_modified=False,
            )
    else:
        cycle_doc.status = "On Hold"
        cycle_doc.clearance_status = "Receipt Blocked"
        cycle_doc.purchase_receipt_cleared = 0

    cycle_doc.flags.ignore_permissions = True
    cycle_doc.save()

    record_security_audit_event(
        "Final Inspection Gate Decided",
        "Production Quality Cycle",
        cycle_doc.name,
        {
            "decision": decision,
            "approved_by": user,
            "bundle_hash": current_hash,
            "clearance_status": cycle_doc.clearance_status,
            "reviewed_revisions": reviewed_revisions,
            "notes": conditions or notes,
        },
    )

    frappe.db.commit()

    return {
        "success": True,
        "cycle_name": cycle_doc.name,
        "decision": decision,
        "final_inspection_status": cycle_doc.final_inspection_status,
        "status": cycle_doc.status,
        "clearance_status": cycle_doc.clearance_status,
        "purchase_receipt_cleared": cycle_doc.purchase_receipt_cleared,
        "approved_by": user,
        "approved_date": str(now),
        "bundle_hash": current_hash,
        "authorizes": "Shipment receipt clearance authorized for ERPNext Purchase Receipt intake.",
    }


@frappe.whitelist(methods=["POST"])
def request_inspection_correction(
    inspection_name: str,
    reason: str,
    required_actions: str | None = None,
    due_date: str | None = None,
) -> dict:
    """Request corrections on an inspection stage report before approval."""
    check_rate_limit("request_inspection_correction", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()

    inspection_name = validate_string(inspection_name, "Inspection Name", max_len=140, required=True)
    reason = validate_string(reason, "Correction Reason", max_len=1000, required=True)

    rows = frappe.db.sql(
        "SELECT name, status, stage, gate_locked, production_quality_cycle FROM `tabSupplier Quality Inspection` WHERE name = %s FOR UPDATE",
        (inspection_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Inspection {0} does not exist.").format(inspection_name), frappe.DoesNotExistError)

    curr = rows[0]
    if curr.status in ("Approved", "Conditionally Approved"):
        frappe.throw(_("Cannot request corrections on an already approved inspection report."), frappe.ValidationError)
    if curr.get("gate_locked"):
        frappe.throw(_("Inspection {0} is locked to an approved gate decision and cannot be altered.").format(inspection_name), frappe.ValidationError)

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    doc.check_permission("write")
    doc.status = "Correction Requested"
    doc.correction_requested_by = user
    doc.correction_requested_on = now_datetime()
    doc.correction_request_reason = reason

    if required_actions:
        doc.corrective_action_required = 1
        doc.corrective_action = required_actions
        doc.corrective_action_status = "Open"
    if due_date:
        doc.corrective_action_due_date = due_date

    doc.comments = (doc.comments or "") + f"\nCorrection Requested ({user}): {reason}"
    doc.save()

    record_security_audit_event(
        "Inspection Correction Requested",
        "Supplier Quality Inspection",
        doc.name,
        {"stage": doc.stage, "reason": reason, "requested_by": user},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def resubmit_inspection_correction(
    inspection_name: str,
    notes: str,
    revised_readings: list[dict] | str | None = None,
    revised_defects: list[dict] | str | None = None,
    new_photos: list[dict] | str | None = None,
) -> dict:
    """Resubmit an inspection stage report following requested corrections."""
    check_rate_limit("resubmit_inspection_correction", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    inspection_name = validate_string(inspection_name, "Inspection Name", max_len=140, required=True)
    notes = validate_string(notes, "Resubmission Notes", max_len=1000, required=True)

    rows = frappe.db.sql(
        "SELECT name, status, stage, gate_locked FROM `tabSupplier Quality Inspection` WHERE name = %s FOR UPDATE",
        (inspection_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Inspection {0} does not exist.").format(inspection_name), frappe.DoesNotExistError)

    curr = rows[0]
    if curr.status != "Correction Requested":
        frappe.throw(
            _("Inspection {0} is not in 'Correction Requested' status (current status: {1}).").format(inspection_name, curr.status),
            frappe.ValidationError,
        )
    if curr.get("gate_locked"):
        frappe.throw(_("Inspection {0} is locked to an approved gate decision and cannot be modified.").format(inspection_name), frappe.ValidationError)

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    doc.check_permission("write")
    doc.status = "Resubmitted"
    doc.resubmitted_by = user
    doc.resubmitted_on = now_datetime()
    doc.resubmission_notes = notes

    if doc.corrective_action_required and doc.corrective_action_status == "Open":
        doc.corrective_action_status = "In Progress"

    # Process new photos
    if new_photos:
        photo_rows = _build_evidence_photo_rows(new_photos, revision=doc.revision, user=user)
        for p in photo_rows:
            doc.append("evidence_photos", p)

    # Process revised readings
    if revised_readings:
        if isinstance(revised_readings, str):
            try:
                revised_readings = json.loads(revised_readings)
            except Exception:
                revised_readings = None
        if revised_readings and isinstance(revised_readings, (list, tuple)):
            doc.set("measurements", [])
            _populate_measurements(doc, revised_readings)

    # Process revised defects
    if revised_defects:
        if isinstance(revised_defects, str):
            try:
                revised_defects = json.loads(revised_defects)
            except Exception:
                revised_defects = None
        if revised_defects and isinstance(revised_defects, (list, tuple)):
            doc.set("defects", [])
            _populate_defects(doc, revised_defects)

    doc.comments = (doc.comments or "") + f"\nResubmitted ({user}): {notes}"
    doc.save()

    record_security_audit_event(
        "Inspection Resubmitted",
        "Supplier Quality Inspection",
        doc.name,
        {"stage": doc.stage, "resubmitted_by": user, "notes": notes},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["GET", "POST"])
def get_complete_stage_history(
    cycle_name: str | None = None,
    supplier: str | None = None,
    item_code: str | None = None,
    purchase_order: str | None = None,
) -> dict:
    """Retrieve complete chronological and structured history of all seven stages for a cycle."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
    cycle = _resolve_cycle(cycle_name, supplier, item_code, purchase_order, ptype="read")

    inspections = frappe.get_all(
        "Supplier Quality Inspection",
        filters={"production_quality_cycle": cycle.name},
        fields=[
            "name", "stage", "visit_number", "visit_type", "location_details",
            "status", "result", "recommendation", "inspector", "inspection_date",
            "revision", "supersedes", "superseded_by", "is_latest", "sampling_plan",
            "lot_size", "sample_size", "passed_quantity", "failed_quantity",
            "critical_defects_count", "major_defects_count", "minor_defects_count",
            "fabric_quality_score", "stitching_quality_score", "corrective_action_required",
            "corrective_action", "corrective_action_status", "correction_request_reason",
            "resubmission_notes", "gate_locked", "locked_gate_decision", "creation", "modified",
        ],
        order_by="stage asc, visit_number asc, revision asc, creation asc",
    )

    stage_groups = {stg: [] for stg in QUALITY_STAGES}
    all_photos = []
    total_defects = 0

    for insp in inspections:
        photos = frappe.get_all(
            "Quality Inspection Evidence",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["name", "file", "caption", "evidence_type", "display_order", "uploader", "uploaded_on", "revision"],
            order_by="revision asc, display_order asc",
        )
        insp["evidence_photos"] = photos
        for p in photos:
            p_dict = dict(p)
            p_dict["stage"] = insp.stage
            p_dict["inspection"] = insp.name
            all_photos.append(p_dict)

        checklist = frappe.get_all(
            "Quality Inspection Checklist Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["check_point", "check_type", "target_value", "actual_value", "status", "criticality"],
        )
        insp["checklist_items"] = checklist

        measurements = frappe.get_all(
            "Quality Inspection Reading Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["parameter_name", "spec_target", "tolerance_plus", "tolerance_minus", "actual_reading", "variance", "reading_status", "uom"],
        )
        insp["measurements"] = measurements

        defects = frappe.get_all(
            "Quality Inspection Defect Item",
            filters={"parent": insp.name, "parenttype": "Supplier Quality Inspection"},
            fields=["defect_code", "defect_description", "severity", "defect_count", "action_required"],
        )
        insp["defects"] = defects
        total_defects += sum(int(d.defect_count or 1) for d in defects)

        if insp.stage in stage_groups:
            stage_groups[insp.stage].append(insp)

    return {
        "cycle_name": cycle.name,
        "cycle_key": cycle.cycle_key,
        "company": cycle.company,
        "supplier": cycle.supplier,
        "item_code": cycle.item_code,
        "purchase_order": cycle.purchase_order,
        "production_lot": cycle.production_lot,
        "season": cycle.season,
        "status": cycle.status,
        "current_stage": cycle.current_stage,
        "go_ahead_status": cycle.go_ahead_status,
        "go_ahead_approved_by": cycle.go_ahead_approved_by,
        "go_ahead_date": str(cycle.go_ahead_date) if cycle.go_ahead_date else None,
        "final_inspection_status": cycle.final_inspection_status,
        "final_inspection_approved_by": cycle.final_inspection_approved_by,
        "final_inspection_date": str(cycle.final_inspection_date) if cycle.final_inspection_date else None,
        "clearance_status": cycle.clearance_status,
        "purchase_receipt_cleared": cycle.purchase_receipt_cleared,
        "summary": {
            "total_reports": len(inspections),
            "total_photos": len(all_photos),
            "total_defects": total_defects,
        },
        "stage_groups": stage_groups,
        "all_photos": all_photos,
    }


@frappe.whitelist(methods=["GET", "POST"])
def export_quality_report_bundle(
    cycle_name: str | None = None,
    supplier: str | None = None,
    item_code: str | None = None,
    purchase_order: str | None = None,
    watermark: str | None = None,
    as_pdf: bool = True,
) -> dict:
    """Generate controlled, watermarked PDF report bundle with cryptographic verification hash."""
    require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()
    cycle = _resolve_cycle(cycle_name, supplier, item_code, purchase_order, ptype="read")

    history = get_complete_stage_history(cycle_name=cycle.name)
    now = now_datetime()

    # Build reviewed revisions dictionary for bundle hash computation
    reviewed_revisions = {}
    for stg, reports in history["stage_groups"].items():
        latest_reports = [r for r in reports if r.is_latest]
        if latest_reports:
            r = latest_reports[0]
            reviewed_revisions[stg] = {"name": r.name, "revision": r.revision, "status": r.status}

    bundle_hash = _compute_bundle_hash(cycle.name, cycle.cycle_key, reviewed_revisions)
    watermark_text = watermark or f"CONFIDENTIAL - CLOTHING ERP - {cycle.company} - {now.strftime('%Y-%m-%d')} - {user}"

    # Render clean HTML report
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Quality Inspection Report Bundle - {cycle.name}</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 15mm 15mm 20mm 15mm;
    @bottom-center {{
      content: "Bundle Verification Hash: SHA256:{bundle_hash[:16]}... | Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #64748b;
    }}
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.4;
    font-size: 10pt;
    position: relative;
  }}
  .watermark {{
    position: fixed;
    top: 35%;
    left: 5%;
    width: 90%;
    text-align: center;
    transform: rotate(-35deg);
    font-size: 32pt;
    font-weight: 800;
    color: rgba(220, 38, 38, 0.08);
    text-transform: uppercase;
    z-index: -1000;
    pointer-events: none;
  }}
  .header {{
    border-bottom: 2px solid #0f172a;
    padding-bottom: 10px;
    margin-bottom: 15px;
  }}
  .header h1 {{
    margin: 0;
    font-size: 16pt;
    color: #0f172a;
  }}
  .header .meta {{
    font-size: 9pt;
    color: #475569;
    margin-top: 4px;
  }}
  .badge {{
    display: inline-block;
    padding: 3px 8px;
    font-size: 8pt;
    font-weight: bold;
    border-radius: 4px;
    text-transform: uppercase;
  }}
  .badge-approved {{ background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }}
  .badge-cond {{ background-color: #fef9c3; color: #854d0e; border: 1px solid #fde047; }}
  .badge-rejected {{ background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }}
  .badge-pending {{ background-color: #e2e8f0; color: #334155; border: 1px solid #cbd5e1; }}
  .gate-grid {{
    display: table;
    width: 100%;
    margin-bottom: 15px;
    border-spacing: 10px;
  }}
  .gate-card {{
    display: table-cell;
    width: 50%;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px;
    vertical-align: top;
  }}
  .gate-card h3 {{ margin: 0 0 6px 0; font-size: 11pt; }}
  table.stage-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 8.5pt;
  }}
  table.stage-table th, table.stage-table td {{
    border: 1px solid #cbd5e1;
    padding: 5px 8px;
    text-align: left;
  }}
  table.stage-table th {{
    background-color: #f1f5f9;
    font-weight: 600;
  }}
  .hash-box {{
    background: #f1f5f9;
    border: 1px dashed #94a3b8;
    padding: 8px;
    font-family: monospace;
    font-size: 8pt;
    word-break: break-all;
    margin-top: 15px;
  }}
</style>
</head>
<body>
<div class="watermark">{watermark_text}</div>

<div class="header">
  <h1>Controlled Quality Report Bundle</h1>
  <div class="meta">
    <strong>Company:</strong> {cycle.company} |
    <strong>Supplier:</strong> {cycle.supplier} |
    <strong>Style / SKU:</strong> {cycle.item_code} |
    <strong>PO:</strong> {cycle.purchase_order or 'N/A'} |
    <strong>Lot:</strong> {cycle.production_lot} |
    <strong>Season:</strong> {cycle.season or 'N/A'}
  </div>
  <div class="meta">
    <strong>Cycle Key:</strong> {cycle.cycle_key} |
    <strong>Current Status:</strong> {cycle.status} |
    <strong>Exported By:</strong> {user} on {now.strftime('%Y-%m-%d %H:%M:%S UTC')}
  </div>
</div>

<div class="gate-grid">
  <div class="gate-card">
    <h3>Gate 4: Production Go Ahead</h3>
    <p><strong>Status:</strong> <span class="badge {'badge-approved' if cycle.go_ahead_status == 'Approved' else ('badge-cond' if cycle.go_ahead_status == 'Conditionally Approved' else 'badge-pending')}">{cycle.go_ahead_status}</span></p>
    <p><strong>Decided By:</strong> {cycle.go_ahead_approved_by or 'Pending'} on {cycle.go_ahead_date or 'N/A'}</p>
    <p><strong>Conditions/Notes:</strong> {cycle.go_ahead_conditions or 'None'}</p>
  </div>
  <div class="gate-card">
    <h3>Gate 7: Final Inspection</h3>
    <p><strong>Status:</strong> <span class="badge {'badge-approved' if cycle.final_inspection_status == 'Approved' else ('badge-cond' if cycle.final_inspection_status == 'Conditionally Approved' else 'badge-pending')}">{cycle.final_inspection_status}</span></p>
    <p><strong>Decided By:</strong> {cycle.final_inspection_approved_by or 'Pending'} on {cycle.final_inspection_date or 'N/A'}</p>
    <p><strong>Clearance:</strong> {cycle.clearance_status} ({'Receipt Cleared' if cycle.purchase_receipt_cleared else 'Receipt Blocked'})</p>
  </div>
</div>

<h3>Complete Seven-Stage Inspection Log</h3>
<table class="stage-table">
  <thead>
    <tr>
      <th>Stage</th>
      <th>Visit</th>
      <th>Revision</th>
      <th>Inspection Date</th>
      <th>Inspector</th>
      <th>Status / Result</th>
      <th>Sample (Pass/Fail)</th>
      <th>Defects (C/M/m)</th>
      <th>CAPA Status</th>
    </tr>
  </thead>
  <tbody>
"""
    for stg in QUALITY_STAGES:
        reports = history["stage_groups"].get(stg) or []
        if not reports:
            html_content += f"""
    <tr>
      <td><strong>{stg}</strong></td>
      <td colspan="8" style="color: #94a3b8; font-style: italic;">No inspection report recorded</td>
    </tr>
"""
        else:
            for r in reports:
                status_badge = f"<span class='badge {'badge-approved' if r.status in ('Approved', 'Conditionally Approved') else 'badge-pending'}'>{r.status}</span>"
                html_content += f"""
    <tr>
      <td><strong>{stg}</strong> {'(Latest)' if r.is_latest else '(Superseded)'}</td>
      <td>{r.visit_number} ({r.visit_type or 'Standard'})</td>
      <td>r{r.revision}</td>
      <td>{r.inspection_date or 'N/A'}</td>
      <td>{r.inspector}</td>
      <td>{status_badge} / {r.result}</td>
      <td>{r.sample_size or 0} ({r.passed_quantity or 0}/{r.failed_quantity or 0})</td>
      <td>{r.critical_defects_count}/{r.major_defects_count}/{r.minor_defects_count}</td>
      <td>{r.corrective_action_status if r.corrective_action_required else 'None'}</td>
    </tr>
"""

    html_content += f"""
  </tbody>
</table>

<div class="hash-box">
  <strong>Cryptographic Integrity & Verification Hash:</strong><br>
  SHA256: {bundle_hash}<br>
  <small>This document is an immutable controlled quality record produced by Clothing ERP. Any alteration invalidates this record.</small>
</div>

</body>
</html>
"""

    pdf_bytes = None
    if as_pdf:
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        except Exception as e:
            frappe.logger("quality_erp").warning(f"Weasyprint PDF conversion failed, falling back to HTML bytes: {e}")
            pdf_bytes = html_content.encode("utf-8")
    else:
        pdf_bytes = html_content.encode("utf-8")

    record_security_audit_event(
        "Quality Report Bundle Exported",
        "Production Quality Cycle",
        cycle.name,
        {
            "user": user,
            "bundle_hash": bundle_hash,
            "format": "pdf" if as_pdf else "html",
            "stages_count": len(history["stage_groups"]),
        },
    )

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    filename = f"Quality_Report_Bundle_{cycle.name}_{now.strftime('%Y%m%d_%H%M%S')}.{'pdf' if as_pdf else 'html'}"

    return {
        "success": True,
        "cycle_name": cycle.name,
        "bundle_hash": bundle_hash,
        "filename": filename,
        "content_type": "application/pdf" if as_pdf else "text/html",
        "file_bytes_base64": pdf_b64,
        "size_bytes": len(pdf_bytes),
    }


@frappe.whitelist(methods=["POST"])
def recommend_return_disposition(
    quarantine_name: str,
    disposition: str,
    notes: str | None = None,
    photo_evidence: str | None = None,
) -> dict:
    """Recommend a failed-return disposition for business administrator approval."""
    check_rate_limit("recommend_return_disposition", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "Clothing Warehouse Manager"})
    user = get_current_user()

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    valid_dispositions = {
        "Restock (A-Grade)",
        "Refurbish",
        "Seconds Sale (B-Grade)",
        "Scrap",
        "Supplier Claim",
        "On Hold",
    }
    disposition = validate_string(disposition, "Disposition", allowed_values=valid_dispositions)

    rows = frappe.db.sql(
        "SELECT name, inspection_status, disposition_status FROM `tabReturn Quarantine` WHERE name = %s FOR UPDATE",
        (quarantine_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Return Quarantine", quarantine_name)
    doc.check_permission("write")
    doc.disposition = disposition
    doc.disposition_status = "Awaiting Business Approval"
    doc.disposition_recommended_by = user
    doc.disposition_recommended_on = now_datetime()
    doc.disposition_notes = notes

    if photo_evidence and not doc.photo_evidence:
        doc.photo_evidence = photo_evidence

    doc.flags.ignore_permissions = True
    doc.save()

    record_security_audit_event(
        "Return Disposition Recommended",
        "Return Quarantine",
        doc.name,
        {"disposition": disposition, "recommended_by": user, "notes": notes},
    )

    frappe.db.commit()

    return {
        "success": True,
        "quarantine_name": doc.name,
        "disposition": doc.disposition,
        "disposition_status": doc.disposition_status,
        "recommended_by": user,
    }


@frappe.whitelist(methods=["POST"])
def approve_return_disposition(
    quarantine_name: str,
    decision: str,
    approval_notes: str | None = None,
    target_warehouse: str | None = None,
    supplier_claim_amount: float | None = None,
) -> dict:
    """Approve or reject a failed-return disposition (Scrap, Seconds Sale, Supplier Claim, On Hold).
    
    Authority: Clothing Business Administrator or System Manager only.
    Does NOT post stock or GL entries without explicit authorization.
    """
    check_rate_limit("approve_return_disposition", limit=30, window_seconds=60)
    require_role({ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    decision = validate_string(decision, "Decision", allowed_values={"Scrap", "Seconds Sale", "Supplier Claim", "On Hold", "Reject Disposition"})

    rows = frappe.db.sql(
        """
        SELECT name, inspection_status, disposition, disposition_status, item_code, quantity,
               quarantine_warehouse, delivery_note, retailer
        FROM `tabReturn Quarantine`
        WHERE name = %s
        FOR UPDATE
        """,
        (quarantine_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    curr = rows[0]
    doc = frappe.get_doc("Return Quarantine", quarantine_name)
    now = now_datetime()

    doc.disposition_approved_by = user
    doc.disposition_approved_on = now
    doc.disposition_approval_notes = approval_notes

    linked_claim_name = None

    if decision == "Reject Disposition":
        doc.disposition_status = "Rejected"
    elif decision == "Scrap":
        doc.disposition = "Scrap"
        doc.disposition_status = "Approved by Business"
        doc.inspection_status = "Inspected - Scrapped"
        if target_warehouse:
            doc.scrap_warehouse = target_warehouse
    elif decision == "Seconds Sale":
        doc.disposition = "Seconds Sale (B-Grade)"
        doc.disposition_status = "Approved by Business"
        doc.inspection_status = "Inspected - Seconds Sale"
        if target_warehouse:
            doc.seconds_warehouse = target_warehouse
    elif decision == "Supplier Claim":
        doc.disposition = "Supplier Claim"
        doc.disposition_status = "Approved by Business"
        doc.inspection_status = "Disposed - Supplier Claim"

        # Resolve supplier from delivery note or item defaults
        supplier = None
        po = None
        if doc.delivery_note:
            po = frappe.db.get_value("Delivery Note", doc.delivery_note, "purchase_order")
        if not supplier:
            item_supp = frappe.get_all("Item Default", filters={"parent": doc.item_code}, pluck="default_supplier", limit=1)
            supplier = item_supp[0] if item_supp else None
        if not supplier:
            supps = frappe.get_all("Supplier", pluck="name", limit=1)
            supplier = supps[0] if supps else "Default Supplier"

        company = frappe.db.get_value("Warehouse", doc.quarantine_warehouse, "company") or frappe.db.get_single_value("Global Defaults", "default_company")
        claim_amt = flt(supplier_claim_amount) if supplier_claim_amount is not None else 0.0

        claim_doc = frappe.get_doc({
            "doctype": "Supplier Quality Claim",
            "company": company,
            "supplier": supplier,
            "item_code": doc.item_code,
            "claim_type": "Customer Return (Factory Fault)",
            "status": "Approved by Business",
            "claim_quantity": doc.quantity,
            "claim_amount": claim_amt,
            "return_quarantine": doc.name,
            "purchase_order": po,
            "defect_description": doc.inspection_notes or doc.return_reason,
            "approved_by": user,
            "approval_date": now,
            "approval_notes": f"Approved via return quarantine disposition: {approval_notes or 'Defect confirmed'}",
        })
        claim_doc.flags.ignore_permissions = True
        claim_doc.insert()
        doc.supplier_claim = claim_doc.name
        linked_claim_name = claim_doc.name
    elif decision == "On Hold":
        doc.disposition = "On Hold"
        doc.disposition_status = "Approved by Business"
        doc.inspection_status = "On Hold"

    doc.flags.ignore_permissions = True
    doc.save()

    record_security_audit_event(
        "Return Disposition Decided",
        "Return Quarantine",
        doc.name,
        {
            "decision": decision,
            "approved_by": user,
            "disposition_status": doc.disposition_status,
            "linked_claim": linked_claim_name,
        },
    )

    frappe.db.commit()

    return {
        "success": True,
        "quarantine_name": doc.name,
        "decision": decision,
        "disposition_status": doc.disposition_status,
        "inspection_status": doc.inspection_status,
        "approved_by": user,
        "linked_claim": linked_claim_name,
    }


@frappe.whitelist(methods=["POST"])
def create_supplier_claim(
    supplier: str,
    item_code: str,
    company: str | None = None,
    claim_type: str = "Customer Return (Factory Fault)",
    claim_amount: float = 0.0,
    claim_quantity: float = 1.0,
    return_quarantine: str | None = None,
    supplier_quality_inspection: str | None = None,
    purchase_order: str | None = None,
    defect_code: str | None = None,
    defect_description: str | None = None,
    evidence_photos: list[dict] | None = None,
) -> dict:
    """Create a new Supplier Quality Claim."""
    check_rate_limit("create_supplier_claim", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()

    supplier = validate_string(supplier, "Supplier", max_len=140, required=True)
    item_code = validate_string(item_code, "Item Code", max_len=140, required=True)

    if not company:
        company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            comps = frappe.get_all("Company", pluck="name", limit=1)
            company = comps[0] if comps else "Default Company"

    # Enforce multi-company / supplier isolation
    if not is_quality_admin(user):
        allowed_companies = frappe.get_all("User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value")
        if allowed_companies and company not in allowed_companies:
            frappe.throw(_("Access denied: You do not have permission for company {0}.").format(company), frappe.PermissionError)
        allowed_suppliers = frappe.get_all("User Permission", filters={"user": user, "allow": "Supplier"}, pluck="for_value")
        if allowed_suppliers and supplier not in allowed_suppliers:
            frappe.throw(_("Access denied: You do not have permission for supplier {0}.").format(supplier), frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype": "Supplier Quality Claim",
        "company": company,
        "supplier": supplier,
        "item_code": item_code,
        "claim_type": claim_type,
        "status": "Pending Business Approval",
        "claim_quantity": flt(claim_quantity),
        "claim_amount": flt(claim_amount),
        "return_quarantine": return_quarantine,
        "supplier_quality_inspection": supplier_quality_inspection,
        "purchase_order": purchase_order,
        "defect_code": defect_code,
        "defect_description": defect_description,
    })

    if evidence_photos and isinstance(evidence_photos, (list, tuple)):
        photo_rows = _build_evidence_photo_rows(evidence_photos, revision=1, user=user)
        for p in photo_rows:
            doc.append("evidence_photos", p)

    doc.insert()

    record_security_audit_event(
        "Supplier Quality Claim Created",
        "Supplier Quality Claim",
        doc.name,
        {"supplier": supplier, "claim_amount": doc.claim_amount, "created_by": user},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def decide_supplier_claim(
    claim_name: str,
    decision: str,
    settlement_type: str | None = None,
    settled_amount: float | None = None,
    debit_note: str | None = None,
    notes: str | None = None,
) -> dict:
    """Decide on a Supplier Quality Claim (Approve, Settle, Reject).
    
    Authority: Clothing Business Administrator or System Manager only.
    """
    check_rate_limit("decide_supplier_claim", limit=30, window_seconds=60)
    require_role({ROLE_BUSINESS_ADMIN, "System Manager"})
    user = get_current_user()

    claim_name = validate_string(claim_name, "Claim Name", max_len=140, required=True)
    decision = validate_string(decision, "Decision", allowed_values={"Approved by Business", "Settled", "Rejected", "Cancelled"})

    rows = frappe.db.sql(
        "SELECT name, status, supplier, claim_amount FROM `tabSupplier Quality Claim` WHERE name = %s FOR UPDATE",
        (claim_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Supplier Quality Claim {0} not found.").format(claim_name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Supplier Quality Claim", claim_name)
    now = now_datetime()
    doc.status = decision

    if decision in ("Approved by Business", "Settled"):
        doc.approved_by = user
        doc.approval_date = now
    if notes:
        doc.approval_notes = (doc.approval_notes or "") + f"\nDecision ({user}): {notes}"
    if settlement_type:
        doc.settlement_type = settlement_type
    if settled_amount is not None:
        doc.settled_amount = flt(settled_amount)
    if debit_note:
        doc.debit_note = debit_note

    doc.save()

    record_security_audit_event(
        "Supplier Quality Claim Decided",
        "Supplier Quality Claim",
        doc.name,
        {"decision": decision, "approved_by": user, "settled_amount": doc.settled_amount},
    )

    return doc.as_dict()

