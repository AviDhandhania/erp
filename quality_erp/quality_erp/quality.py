"""Quality management services: 7-stage supplier quality lifecycle, return quarantine, and review bundles."""

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
                "status": "Pending Review",
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
               production_quality_cycle, production_lot, season, visit_number, visit_type, location_details
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
    if curr.status == "Approved":
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
            "comments": f"Revision {new_revision} superseding {inspection_name}",
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
        "SELECT name, status, stage, supplier, item_code, purchase_order FROM `tabSupplier Quality Inspection` WHERE name = %s FOR UPDATE",
        (inspection_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Inspection {0} does not exist.").format(inspection_name), frappe.DoesNotExistError)

    current = rows[0]
    if current.status == "Approved":
        return frappe.get_doc("Supplier Quality Inspection", inspection_name).as_dict()

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
