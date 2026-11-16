"""Quality management services: 7-stage supplier quality lifecycle and return quarantine."""

import frappe
from frappe.utils import now_datetime
from quality_erp.security import (
    assert_can_approve_quality_gate,
    get_current_user,
    is_quality_admin,
    require_role,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
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


@frappe.whitelist()
def create_quality_inspection(supplier, item_code, stage, purchase_order=None, spec_notes=None, photo_evidence=None):
    """Create a new supplier quality inspection entry."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    if stage not in QUALITY_STAGES:
        frappe.throw(frappe._("Invalid quality stage '{0}'").format(stage), frappe.ValidationError)

    doc = frappe.get_doc(
        {
            "doctype": "Supplier Quality Inspection",
            "supplier": supplier,
            "item_code": item_code,
            "purchase_order": purchase_order,
            "stage": stage,
            "status": "Pending Review",
            "inspector": user,
            "spec_measurements": spec_notes,
            "photo_evidence": photo_evidence,
        }
    ).insert()
    return doc.as_dict()


@frappe.whitelist()
def approve_quality_gate(inspection_name, notes=None):
    """Approve a quality inspection gate. Critical gates require Administrator approval."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    if doc.status == "Approved":
        return doc.as_dict()

    # High-security enforcement: Gate 4 (Production Go Ahead) & Gate 7 (Final Inspection)
    # require Administrator role.
    if "Production Go Ahead" in doc.stage:
        assert_can_approve_quality_gate("Production Go Ahead", user)
    elif "Final Inspection" in doc.stage:
        assert_can_approve_quality_gate("Final Inspection", user)

    doc.status = "Approved"
    doc.approved_by = user
    doc.approval_date = now_datetime()
    if notes:
        doc.comments = (doc.comments or "") + f"\nApproval notes ({user}): {notes}"
    doc.save()
    return doc.as_dict()


@frappe.whitelist()
def reject_quality_gate(inspection_name, reason):
    """Reject a quality inspection gate with mandatory reason."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    if not reason or not reason.strip():
        frappe.throw(frappe._("Rejection requires a documented reason."), frappe.ValidationError)

    doc = frappe.get_doc("Supplier Quality Inspection", inspection_name)
    doc.status = "Rejected"
    doc.approved_by = user
    doc.approval_date = now_datetime()
    doc.comments = (doc.comments or "") + f"\nRejection ({user}): {reason.strip()}"
    doc.save()
    return doc.as_dict()


@frappe.whitelist()
def record_return_quarantine(retailer, delivery_note, item_code, quantity, return_reason, photo_evidence=None):
    """Record an item intake into the quarantine warehouse for quality inspection."""
    require_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    doc = frappe.get_doc(
        {
            "doctype": "Return Quarantine",
            "retailer": retailer,
            "delivery_note": delivery_note,
            "item_code": item_code,
            "quantity": float(quantity),
            "return_reason": return_reason,
            "inspection_status": "Quarantined",
            "photo_evidence": photo_evidence,
            "inspected_by": user,
            "inspected_on": now_datetime(),
        }
    ).insert()
    return doc.as_dict()
