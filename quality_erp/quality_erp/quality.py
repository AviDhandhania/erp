"""Quality management services: 7-stage supplier quality lifecycle, return quarantine, and review bundles."""

import frappe
from frappe import _
from frappe.utils import now_datetime
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


def check_stage_prerequisites(stage, supplier, item_code, purchase_order=None, current_inspection=None):
    """Ensure all ordered preceding stages have an approved inspection."""
    if stage not in QUALITY_STAGES:
        frappe.throw(_("Invalid quality stage '{0}'").format(stage), frappe.ValidationError)

    stage_idx = QUALITY_STAGES.index(stage)
    if stage_idx == 0:
        return

    prereq_stages = QUALITY_STAGES[:stage_idx]
    filters = {
        "supplier": supplier,
        "item_code": item_code,
        "status": "Approved",
    }
    approved = frappe.get_all(
        "Supplier Quality Inspection",
        filters=filters,
        fields=["stage", "purchase_order"],
    )
    approved_set = set()
    for row in approved:
        if not purchase_order or not row.purchase_order or row.purchase_order == purchase_order:
            approved_set.add(row.stage)

    for req in prereq_stages:
        if req not in approved_set:
            frappe.throw(
                _(
                    "Cannot approve stage '{0}': prerequisite stage '{1}' has not been approved for {2}."
                ).format(stage, req, item_code),
                frappe.ValidationError,
            )


@frappe.whitelist(methods=["POST"])
def create_quality_inspection(
    supplier,
    item_code,
    stage,
    purchase_order=None,
    spec_notes=None,
    photo_evidence=None,
    revision=1,
    supersedes=None,
):
    """Create a new supplier quality inspection entry."""
    check_rate_limit("create_quality_inspection", limit=60, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    supplier = validate_string(supplier, "Supplier", max_len=140, required=True)
    item_code = validate_string(item_code, "Item Code", max_len=140, required=True)
    stage = validate_string(stage, "Stage", max_len=140, required=True, allowed_values=QUALITY_STAGES)
    purchase_order = validate_string(purchase_order, "Purchase Order", max_len=140)
    revision = validate_int(revision, "Revision", min_val=1, max_val=1000) or 1

    try:
        doc = frappe.get_doc(
            {
                "doctype": "Supplier Quality Inspection",
                "supplier": supplier,
                "item_code": item_code,
                "purchase_order": purchase_order,
                "stage": stage,
                "status": "Pending Review",
                "revision": int(revision or 1),
                "supersedes": supersedes,
                "inspector": user,
                "spec_measurements": spec_notes,
                "photo_evidence": photo_evidence,
            }
        ).insert()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Quality Inspection Created",
        "Supplier Quality Inspection",
        doc.name,
        {"stage": stage, "supplier": supplier, "item_code": item_code, "revision": doc.revision},
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def revise_quality_inspection(inspection_name, spec_notes=None, photo_evidence=None):
    """Create a new versioned revision of a rejected or pending inspection report."""
    check_rate_limit("revise_quality_inspection", limit=30, window_seconds=60)
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    inspection_name = validate_string(inspection_name, "Inspection Name", max_len=140, required=True)

    # Lock original inspection
    rows = frappe.db.sql(
        "SELECT name, supplier, item_code, purchase_order, stage, status, revision FROM `tabSupplier Quality Inspection` WHERE name = %s FOR UPDATE",
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
    try:
        new_doc = frappe.get_doc(
            {
                "doctype": "Supplier Quality Inspection",
                "supplier": curr.supplier,
                "item_code": curr.item_code,
                "purchase_order": curr.purchase_order,
                "stage": curr.stage,
                "status": "Pending Review",
                "revision": new_revision,
                "supersedes": inspection_name,
                "inspector": user,
                "spec_measurements": spec_notes or doc.spec_measurements,
                "photo_evidence": photo_evidence or doc.photo_evidence,
                "comments": f"Revision {new_revision} superseding {inspection_name}",
            }
        ).insert()
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
        },
    )

    return new_doc.as_dict()


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
    notes=None,
):
    """Record an item intake into the quarantine warehouse for quality inspection."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "Clothing Warehouse Manager"})
    user = get_current_user()

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
            "photo_evidence": photo_evidence,
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
        },
    )

    return doc.as_dict()


@frappe.whitelist(methods=["POST"])
def inspect_return_quarantine(quarantine_name, decision, notes=None, photo_evidence=None):
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
    if photo_evidence:
        doc.photo_evidence = photo_evidence
    doc.save()

    record_security_audit_event(
        "Return Quarantine Inspected",
        "Return Quarantine",
        doc.name,
        {"decision": decision, "status": doc.inspection_status},
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
