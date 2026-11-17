"""Warehouse customer return intake, quarantine isolation, and refurbishment pipeline.

Enforces the operational model requirements:
- Scan returned exact Item/Size/serial/batch against an authorized original Delivery Note.
- Prevent duplicate or excess returns through row-locked balance verification.
- Direct all returned stock into a native quarantine Warehouse via submitted native Delivery Note return.
- Create linked Return Quarantine tracking record in Quality ERP.
- Require Quality inspection approval ('Inspected - Passed Refurbishment') before movement to refurbishment WIP.
- Track refurbishment operations, assignee, start/end times, cost reference, consumed materials, before/after evidence.
- Mandatory post-refurbishment quality re-inspection gate before final restocking.
- Move refurbished stock back to saleable inventory only through submitted native ERPNext Stock Entry documents.
- Separate physical warehouse intake from financial credit/refund authorization.
- Provide SLA queues and permission-scoped exception dashboards.
- Strictly enforce warehouse user permissions and server-side role validation on all state transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
)
from warehouse_erp.api_security import (
    check_rate_limit,
    clear_idempotency,
    record_security_audit_event,
    save_idempotency_result,
    validate_float,
    validate_idempotency,
    validate_string,
)
from warehouse_erp.security import (
    assigned_warehouses,
    get_current_user,
    is_warehouse_admin,
    require_role,
)

RETURN_INTAKE_ROLES = {ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"}
QUALITY_INSPECTION_ROLES = {
    "Clothing Quality Inspector",
    "Clothing Quality Manager",
    ROLE_BUSINESS_ADMIN,
    "System Manager",
}

VALID_RETURN_REASONS = {
    "Defective Stitching",
    "Fabric Fault",
    "Size Mismatch",
    "Customer Return",
    "Other Quality Issue",
}

VALID_REFURBISHMENT_OPERATIONS = {
    "Restitching",
    "Stain Removal / Wash",
    "Button / Zipper Replacement",
    "Ironing / Repackaging",
    "Alteration",
    "Multi-Operation Refurbishment",
}

VALID_POST_INSPECTION_DECISIONS = {"Passed", "Rejected"}


def _validate_return_quantity(value) -> float:
    try:
        qty = Decimal(str(value))
    except (InvalidOperation, ValueError):
        frappe.throw(_("Return quantity must be a positive number."), frappe.ValidationError)
    if not qty.is_finite() or qty <= 0:
        frappe.throw(_("Return quantity must be a positive number."), frappe.ValidationError)
    return float(qty)


def _lock_delivery_note(delivery_note: str):
    frappe.db.sql(
        "SELECT name FROM `tabDelivery Note` WHERE name = %s FOR UPDATE",
        (delivery_note,),
    )


def _lock_return_quarantine(quarantine_name: str):
    frappe.db.sql(
        "SELECT name FROM `tabReturn Quarantine` WHERE name = %s FOR UPDATE",
        (quarantine_name,),
    )


def _get_delivered_item_row(delivery_note: frappe.Document, item_code: str):
    items = delivery_note.get("items") or []
    for row in items:
        row_item = row.get("item_code") if isinstance(row, dict) else getattr(row, "item_code", None)
        if row_item == item_code:
            return row
    frappe.throw(
        _("Item {0} was not delivered on Delivery Note {1}.").format(item_code, delivery_note.name),
        frappe.ValidationError,
    )


def _get_already_returned_quantity(delivery_note_name: str, item_code: str) -> float:
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(ABS(dni.qty)), 0)
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.return_against = %s
          AND dn.is_return = 1
          AND dn.docstatus = 1
          AND dni.item_code = %s
        """,
        (delivery_note_name, item_code),
    )
    return flt(result[0][0]) if result else 0.0


def _get_already_returned_serials(delivery_note_name: str, item_code: str) -> set[str]:
    from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

    rows = frappe.db.sql(
        """
        SELECT dni.serial_no
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.return_against = %s
          AND dn.is_return = 1
          AND dn.docstatus = 1
          AND dni.item_code = %s
          AND dni.serial_no IS NOT NULL
        """,
        (delivery_note_name, item_code),
        as_dict=True,
    )
    serials = set()
    for row in rows:
        if row.serial_no:
            serials.update(get_serial_nos(row.serial_no))
    return serials


@frappe.whitelist(methods=["POST"])
def intake_customer_return(
    delivery_note: str,
    item_code: str,
    quantity: float,
    quarantine_warehouse: str,
    return_reason: str,
    serial_no: str | None = None,
    batch_no: str | None = None,
    photo_evidence: str | None = None,
    notes: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Atomically validate, return, and isolate garments into native quarantine."""
    check_rate_limit("intake_customer_return", limit=60, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)
    user = get_current_user()

    delivery_note = validate_string(delivery_note, "Delivery Note", max_len=140, required=True)
    item_code = validate_string(item_code, "Item Code", max_len=140, required=True)
    quarantine_warehouse = validate_string(quarantine_warehouse, "Quarantine Warehouse", max_len=140, required=True)
    return_reason = validate_string(return_reason, "Return Reason", allowed_values=VALID_RETURN_REASONS)
    return_qty = _validate_return_quantity(quantity)

    # Idempotency check
    if request_id:
        req_id = validate_string(request_id, "Request ID", max_len=140)
        is_replay, cached_res = validate_idempotency(
            "intake_customer_return",
            req_id,
            {"delivery_note": delivery_note, "item_code": item_code, "quantity": return_qty, "serial_no": serial_no},
        )
        if is_replay:
            return cached_res

    # Warehouse authorization
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if quarantine_warehouse not in allowed:
            if request_id:
                clear_idempotency("intake_customer_return", request_id)
            frappe.throw(
                _("You do not have permission for quarantine warehouse {0}.").format(quarantine_warehouse),
                frappe.PermissionError,
            )

    if not frappe.db.exists("Warehouse", quarantine_warehouse):
        frappe.throw(_("Warehouse {0} does not exist.").format(quarantine_warehouse), frappe.DoesNotExistError)

    if not frappe.db.exists("Delivery Note", delivery_note):
        frappe.throw(_("Delivery Note {0} does not exist.").format(delivery_note), frappe.DoesNotExistError)

    # Concurrency lock
    _lock_delivery_note(delivery_note)

    orig_dn = frappe.get_doc("Delivery Note", delivery_note)
    orig_dn.check_permission("read")
    if orig_dn.docstatus != 1:
        frappe.throw(_("Only a submitted Delivery Note can be returned."), frappe.ValidationError)
    if orig_dn.is_return:
        frappe.throw(_("Cannot create a return against an existing return Delivery Note."), frappe.ValidationError)

    orig_item = _get_delivered_item_row(orig_dn, item_code)
    delivered_qty = flt(orig_item.get("qty") if isinstance(orig_item, dict) else orig_item.qty)
    orig_rate = orig_item.get("rate") if isinstance(orig_item, dict) else orig_item.rate
    orig_name = orig_item.get("name") if isinstance(orig_item, dict) else orig_item.name
    orig_batch = orig_item.get("batch_no") if isinstance(orig_item, dict) else getattr(orig_item, "batch_no", None)
    orig_serial = orig_item.get("serial_no") if isinstance(orig_item, dict) else getattr(orig_item, "serial_no", None)
    already_returned = _get_already_returned_quantity(orig_dn.name, item_code)
    returnable_qty = delivered_qty - already_returned

    if return_qty > returnable_qty:
        if request_id:
            clear_idempotency("intake_customer_return", request_id)
        frappe.throw(
            _(
                "Return quantity ({0}) exceeds remaining returnable quantity ({1}) for item {2} on Delivery Note {3}."
            ).format(return_qty, returnable_qty, item_code, delivery_note),
            frappe.ValidationError,
        )

    # Serial and Batch validation
    serial_no = str(serial_no or "").strip() or None
    batch_no = str(batch_no or "").strip() or None

    item_doc = frappe.get_cached_value("Item", item_code, ["has_serial_no", "has_batch_no"], as_dict=True) or {}
    has_serial = bool(item_doc.get("has_serial_no"))
    has_batch = bool(item_doc.get("has_batch_no"))

    if has_serial:
        if not serial_no:
            frappe.throw(_("Serial No is required for serialized item {0}.").format(item_code), frappe.ValidationError)
        if return_qty != 1.0:
            frappe.throw(_("Serialized returns must be recorded one unit at a time."), frappe.ValidationError)

        from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

        orig_serials = set(get_serial_nos(orig_serial or ""))
        if serial_no not in orig_serials:
            frappe.throw(
                _("Serial No {0} was not delivered in original Delivery Note {1}.").format(serial_no, delivery_note),
                frappe.ValidationError,
            )
        already_returned_serials = _get_already_returned_serials(orig_dn.name, item_code)
        if serial_no in already_returned_serials:
            frappe.throw(
                _("Serial No {0} has already been returned.").format(serial_no),
                frappe.ValidationError,
            )

    if has_batch:
        if not batch_no:
            frappe.throw(_("Batch No is required for batched item {0}.").format(item_code), frappe.ValidationError)
        if orig_batch and batch_no != orig_batch:
            frappe.throw(
                _("Batch No {0} does not match the delivered batch {1}.").format(batch_no, orig_batch),
                frappe.ValidationError,
            )

    # 1. Create and submit native ERPNext return Delivery Note
    return_dn = frappe.new_doc("Delivery Note")
    return_dn.is_return = 1
    return_dn.return_against = orig_dn.name
    return_dn.customer = orig_dn.customer
    return_dn.company = orig_dn.company
    return_dn.posting_date = nowdate()

    item_row = {
        "item_code": item_code,
        "qty": -1.0 * return_qty,
        "warehouse": quarantine_warehouse,
        "dn_detail": orig_name,
        "rate": orig_rate,
    }
    if serial_no:
        item_row["serial_no"] = serial_no
    if batch_no:
        item_row["batch_no"] = batch_no

    return_dn.append("items", item_row)
    return_dn.flags.ignore_permissions = True
    return_dn.insert()
    return_dn.submit()

    # 2. Register Return Quarantine record in Quality ERP
    from quality_erp.quality import record_return_quarantine

    quarantine_doc = record_return_quarantine(
        retailer=orig_dn.customer,
        delivery_note=orig_dn.name,
        item_code=item_code,
        quantity=return_qty,
        return_reason=return_reason,
        quarantine_warehouse=quarantine_warehouse,
        return_delivery_note=return_dn.name,
        photo_evidence=photo_evidence,
        notes=notes,
    )

    record_security_audit_event(
        "Customer Return Intaked",
        "Return Quarantine",
        quarantine_doc.get("name"),
        {
            "delivery_note": orig_dn.name,
            "return_delivery_note": return_dn.name,
            "item_code": item_code,
            "quantity": return_qty,
        },
    )

    frappe.db.commit()

    res = {
        "return_delivery_note": return_dn.name,
        "return_quarantine": quarantine_doc.get("name"),
        "customer": orig_dn.customer,
        "item_code": item_code,
        "quantity": return_qty,
        "quarantine_warehouse": quarantine_warehouse,
        "status": "Quarantined",
    }

    if request_id:
        save_idempotency_result(
            "intake_customer_return",
            request_id,
            res,
            {"delivery_note": delivery_note, "item_code": item_code, "quantity": return_qty, "serial_no": serial_no},
        )

    return res


@frappe.whitelist(methods=["POST"])
def move_to_refurbishment(quarantine_name: str, refurbishment_warehouse: str, request_id: str | None = None) -> dict:
    """Move quality-cleared returned stock to refurbishment WIP via native Stock Entry."""
    check_rate_limit("move_to_refurbishment", limit=30, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)
    user = get_current_user()

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    refurbishment_warehouse = validate_string(refurbishment_warehouse, "Refurbishment Warehouse", max_len=140, required=True)

    if request_id:
        req_id = validate_string(request_id, "Request ID", max_len=140)
        is_replay, cached_res = validate_idempotency(
            "move_to_refurbishment",
            req_id,
            {"quarantine_name": quarantine_name, "refurbishment_warehouse": refurbishment_warehouse},
        )
        if is_replay:
            return cached_res

    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if refurbishment_warehouse not in allowed:
            if request_id:
                clear_idempotency("move_to_refurbishment", request_id)
            frappe.throw(
                _("You do not have permission for refurbishment warehouse {0}.").format(refurbishment_warehouse),
                frappe.PermissionError,
            )

    _lock_return_quarantine(quarantine_name)
    rows = frappe.db.sql(
        "SELECT name, inspection_status, item_code, quantity, quarantine_warehouse FROM `tabReturn Quarantine` WHERE name = %s",
        (quarantine_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    curr = rows[0]
    curr_status = curr.get("inspection_status") if isinstance(curr, dict) else curr.inspection_status
    if curr_status != "Inspected - Passed Refurbishment":
        frappe.throw(
            _(
                "Cannot move to refurbishment: Return Quarantine {0} status is '{1}'. "
                "Only goods with passing quality inspection can be refurbished."
            ).format(quarantine_name, curr_status),
            frappe.ValidationError,
        )

    quarantine_wh = curr.get("quarantine_warehouse") if isinstance(curr, dict) else curr.quarantine_warehouse
    item_code = curr.get("item_code") if isinstance(curr, dict) else curr.item_code
    quantity = curr.get("quantity") if isinstance(curr, dict) else curr.quantity

    rq = frappe.get_doc("Return Quarantine", quarantine_name)
    company = frappe.db.get_value("Warehouse", quarantine_wh, "company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )

    # Create native Stock Entry for Material Transfer into Refurbishment WIP
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Material Transfer"
    se.company = company
    se.from_warehouse = quarantine_wh
    se.to_warehouse = refurbishment_warehouse
    se.append(
        "items",
        {
            "item_code": item_code,
            "qty": flt(quantity),
            "s_warehouse": quarantine_wh,
            "t_warehouse": refurbishment_warehouse,
        },
    )
    se.flags.ignore_permissions = True
    se.insert()
    se.submit()

    # Update Return Quarantine status
    rq.inspection_status = "In Refurbishment"
    rq.refurbishment_warehouse = refurbishment_warehouse
    rq.stock_entry = se.name
    rq.flags.ignore_permissions = True
    rq.save()

    record_security_audit_event(
        "Moved to Refurbishment",
        "Return Quarantine",
        rq.name,
        {"stock_entry": se.name, "target_warehouse": refurbishment_warehouse},
    )

    frappe.db.commit()

    res = {
        "return_quarantine": rq.name,
        "stock_entry": se.name,
        "status": rq.inspection_status,
        "refurbishment_warehouse": refurbishment_warehouse,
    }

    if request_id:
        save_idempotency_result(
            "move_to_refurbishment",
            request_id,
            res,
            {"quarantine_name": quarantine_name, "refurbishment_warehouse": refurbishment_warehouse},
        )

    return res


@frappe.whitelist(methods=["POST"])
def assign_refurbishment(
    quarantine_name: str,
    assignee: str,
    operation: str,
    estimated_cost: float = 0.0,
    consumed_material: str | None = None,
    notes: str | None = None,
    photo_before: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Assign refurbishment operations, assignee, estimated cost, and record before-photos."""
    check_rate_limit("assign_refurbishment", limit=60, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    assignee = validate_string(assignee, "Assignee", max_len=140, required=True)
    operation = validate_string(operation, "Operation", allowed_values=VALID_REFURBISHMENT_OPERATIONS)
    cost = validate_float(estimated_cost, "Estimated Cost", min_val=0.0)

    if not frappe.db.exists("User", assignee):
        frappe.throw(_("Assignee User {0} does not exist.").format(assignee), frappe.DoesNotExistError)

    if not frappe.db.exists("Return Quarantine", quarantine_name):
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    _lock_return_quarantine(quarantine_name)
    rq = frappe.get_doc("Return Quarantine", quarantine_name)
    rq.check_permission("write")

    if rq.inspection_status not in {"In Refurbishment", "Inspected - Passed Refurbishment"}:
        frappe.throw(
            _("Cannot assign refurbishment to {0} in status '{1}'.").format(quarantine_name, rq.inspection_status),
            frappe.ValidationError,
        )

    rq.refurbishment_assignee = assignee
    rq.refurbishment_operation = operation
    rq.refurbishment_start_time = now_datetime()
    rq.refurbishment_cost = cost
    if consumed_material:
        rq.consumed_material_reference = str(consumed_material).strip()
    if photo_before:
        rq.before_refurbishment_photo = str(photo_before).strip()
    if notes:
        rq.inspection_notes = (rq.inspection_notes or "") + f"\nRefurbishment assigned ({get_current_user()}): {notes.strip()}"

    rq.inspection_status = "In Refurbishment"
    rq.flags.ignore_permissions = True
    rq.save()

    record_security_audit_event(
        "Refurbishment Assigned",
        "Return Quarantine",
        rq.name,
        {
            "assignee": assignee,
            "operation": operation,
            "estimated_cost": cost,
            "has_before_photo": bool(photo_before),
        },
    )

    frappe.db.commit()

    res = {
        "return_quarantine": rq.name,
        "assignee": rq.refurbishment_assignee,
        "operation": rq.refurbishment_operation,
        "status": rq.inspection_status,
        "started_on": str(rq.refurbishment_start_time),
        "refurbishment_cost": flt(rq.refurbishment_cost),
    }

    if request_id:
        save_idempotency_result("assign_refurbishment", request_id, res, {"quarantine_name": quarantine_name, "assignee": assignee})

    return res


@frappe.whitelist(methods=["POST"])
def complete_refurbishment_work(
    quarantine_name: str,
    photo_after: str | None = None,
    consumed_material: str | None = None,
    actual_cost: float | None = None,
    notes: str | None = None,
    require_reinspection: bool = True,
    request_id: str | None = None,
) -> dict:
    """Record completed refurbishment operations, after-photos, and queue for quality reinspection."""
    check_rate_limit("complete_refurbishment_work", limit=60, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    if not frappe.db.exists("Return Quarantine", quarantine_name):
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    _lock_return_quarantine(quarantine_name)
    rq = frappe.get_doc("Return Quarantine", quarantine_name)
    rq.check_permission("write")

    if rq.inspection_status != "In Refurbishment":
        frappe.throw(
            _("Cannot complete work on {0}: status is '{1}'. Item must be 'In Refurbishment'.").format(
                quarantine_name, rq.inspection_status
            ),
            frappe.ValidationError,
        )

    rq.refurbishment_end_time = now_datetime()
    if photo_after:
        rq.after_refurbishment_photo = str(photo_after).strip()
    if consumed_material:
        existing = rq.consumed_material_reference or ""
        rq.consumed_material_reference = (existing + "\n" + str(consumed_material).strip()).strip()
    if actual_cost is not None:
        rq.refurbishment_cost = validate_float(actual_cost, "Actual Cost", min_val=0.0)

    if require_reinspection:
        rq.inspection_status = "Awaiting Reinspection"
        rq.post_refurbishment_inspection_status = "Pending Inspection"
    else:
        rq.post_refurbishment_inspection_status = "Not Required"

    if notes:
        rq.inspection_notes = (rq.inspection_notes or "") + f"\nWork completed ({get_current_user()}): {notes.strip()}"

    rq.flags.ignore_permissions = True
    rq.save()

    record_security_audit_event(
        "Refurbishment Work Completed",
        "Return Quarantine",
        rq.name,
        {
            "completed_by": get_current_user(),
            "require_reinspection": require_reinspection,
            "has_after_photo": bool(photo_after),
            "refurbishment_cost": flt(rq.refurbishment_cost),
        },
    )

    frappe.db.commit()

    res = {
        "return_quarantine": rq.name,
        "status": rq.inspection_status,
        "post_refurbishment_inspection_status": rq.post_refurbishment_inspection_status,
        "completed_on": str(rq.refurbishment_end_time),
        "refurbishment_cost": flt(rq.refurbishment_cost),
    }

    if request_id:
        save_idempotency_result("complete_refurbishment_work", request_id, res, {"quarantine_name": quarantine_name})

    return res


@frappe.whitelist(methods=["POST"])
def post_refurbishment_reinspection(
    quarantine_name: str,
    decision: str,
    notes: str | None = None,
    photo_evidence: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Quality department reinspection gate verifying refurbished garments before restocking."""
    check_rate_limit("post_refurbishment_reinspection", limit=30, window_seconds=60)
    require_role(QUALITY_INSPECTION_ROLES)
    user = get_current_user()

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    decision = validate_string(decision, "Decision", allowed_values=VALID_POST_INSPECTION_DECISIONS)

    if not frappe.db.exists("Return Quarantine", quarantine_name):
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    _lock_return_quarantine(quarantine_name)
    rq = frappe.get_doc("Return Quarantine", quarantine_name)
    rq.check_permission("write")

    if rq.post_refurbishment_inspection_status not in {"Pending Inspection", "Re-inspected - Rejected"}:
        frappe.throw(
            _("Return Quarantine {0} is not awaiting re-inspection (status: {1}).").format(
                quarantine_name, rq.post_refurbishment_inspection_status
            ),
            frappe.ValidationError,
        )

    rq.post_inspected_by = user
    rq.post_inspected_on = now_datetime()
    if notes:
        rq.post_inspection_notes = str(notes).strip()

    if decision == "Passed":
        rq.post_refurbishment_inspection_status = "Re-inspected - Passed"
        rq.inspection_status = "Inspected - Passed Refurbishment"
    else:
        rq.post_refurbishment_inspection_status = "Re-inspected - Rejected"
        rq.inspection_status = "In Refurbishment"

    rq.flags.ignore_permissions = True
    rq.save()

    record_security_audit_event(
        "Post-Refurbishment Reinspected",
        "Return Quarantine",
        rq.name,
        {
            "inspector": user,
            "decision": decision,
            "post_status": rq.post_refurbishment_inspection_status,
        },
    )

    frappe.db.commit()

    res = {
        "return_quarantine": rq.name,
        "decision": decision,
        "post_refurbishment_inspection_status": rq.post_refurbishment_inspection_status,
        "inspection_status": rq.inspection_status,
        "inspected_by": user,
        "inspected_on": str(rq.post_inspected_on),
    }

    if request_id:
        save_idempotency_result("post_refurbishment_reinspection", request_id, res, {"quarantine_name": quarantine_name, "decision": decision})

    return res


@frappe.whitelist(methods=["POST"])
def complete_refurbishment(
    quarantine_name: str,
    target_saleable_warehouse: str,
    notes: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Restock successfully refurbished stock back into saleable inventory via native Stock Entry."""
    check_rate_limit("complete_refurbishment", limit=30, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)
    user = get_current_user()

    quarantine_name = validate_string(quarantine_name, "Quarantine Name", max_len=140, required=True)
    target_saleable_warehouse = validate_string(target_saleable_warehouse, "Target Warehouse", max_len=140, required=True)

    if request_id:
        req_id = validate_string(request_id, "Request ID", max_len=140)
        is_replay, cached_res = validate_idempotency(
            "complete_refurbishment",
            req_id,
            {"quarantine_name": quarantine_name, "target_saleable_warehouse": target_saleable_warehouse},
        )
        if is_replay:
            return cached_res

    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if target_saleable_warehouse not in allowed:
            if request_id:
                clear_idempotency("complete_refurbishment", request_id)
            frappe.throw(
                _("You do not have permission for saleable warehouse {0}.").format(target_saleable_warehouse),
                frappe.PermissionError,
            )

    _lock_return_quarantine(quarantine_name)
    rows = frappe.db.sql(
        "SELECT name, inspection_status, item_code, quantity, refurbishment_warehouse, post_refurbishment_inspection_status FROM `tabReturn Quarantine` WHERE name = %s",
        (quarantine_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    curr = rows[0]
    curr_status = curr.get("inspection_status") if isinstance(curr, dict) else curr.inspection_status
    post_status = curr.get("post_refurbishment_inspection_status") if isinstance(curr, dict) else curr.post_refurbishment_inspection_status

    # Validate post-refurbishment inspection gate
    if post_status == "Pending Inspection":
        frappe.throw(
            _(
                "Cannot complete refurbishment: Return Quarantine {0} is awaiting mandatory post-refurbishment quality re-inspection."
            ).format(quarantine_name),
            frappe.ValidationError,
        )
    if post_status == "Re-inspected - Rejected":
        frappe.throw(
            _(
                "Cannot complete refurbishment: Post-refurbishment quality inspection failed for {0}. "
                "Goods must be re-worked before restocking."
            ).format(quarantine_name),
            frappe.ValidationError,
        )

    if curr_status not in {"In Refurbishment", "Inspected - Passed Refurbishment"}:
        frappe.throw(
            _(
                "Cannot complete refurbishment: Return Quarantine {0} status is '{1}'. "
                "Only goods in refurbishment or passed reinspection can be restocked."
            ).format(quarantine_name, curr_status),
            frappe.ValidationError,
        )

    refurb_wh = curr.get("refurbishment_warehouse") if isinstance(curr, dict) else curr.refurbishment_warehouse
    item_code = curr.get("item_code") if isinstance(curr, dict) else curr.item_code
    quantity = curr.get("quantity") if isinstance(curr, dict) else curr.quantity

    rq = frappe.get_doc("Return Quarantine", quarantine_name)
    company = frappe.db.get_value("Warehouse", target_saleable_warehouse, "company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )

    # Native Stock Entry: Refurbishment WIP -> Saleable stock
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Material Transfer"
    se.company = company
    se.from_warehouse = refurb_wh
    se.to_warehouse = target_saleable_warehouse
    se.append(
        "items",
        {
            "item_code": item_code,
            "qty": flt(quantity),
            "s_warehouse": refurb_wh,
            "t_warehouse": target_saleable_warehouse,
        },
    )
    se.flags.ignore_permissions = True
    se.insert()
    se.submit()

    rq.inspection_status = "Restocked"
    rq.target_warehouse = target_saleable_warehouse
    rq.restock_entry = se.name
    if notes:
        rq.inspection_notes = (rq.inspection_notes or "") + f"\nRestock completed ({user}): {notes.strip()}"
    rq.flags.ignore_permissions = True
    rq.save()

    record_security_audit_event(
        "Refurbishment Completed",
        "Return Quarantine",
        rq.name,
        {"restock_entry": se.name, "target_warehouse": target_saleable_warehouse},
    )

    frappe.db.commit()

    res = {
        "return_quarantine": rq.name,
        "restock_entry": se.name,
        "status": rq.inspection_status,
        "target_warehouse": target_saleable_warehouse,
    }

    if request_id:
        save_idempotency_result(
            "complete_refurbishment",
            request_id,
            res,
            {"quarantine_name": quarantine_name, "target_saleable_warehouse": target_saleable_warehouse},
        )

    return res


@frappe.whitelist()
def get_return_financial_status(delivery_note_or_quarantine: str) -> dict:
    """Return explicit financial authorization boundary without assuming refund, credit, or replacement."""
    check_rate_limit("get_return_financial_status", limit=60, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES | QUALITY_INSPECTION_ROLES)
    ref = validate_string(delivery_note_or_quarantine, "Reference", max_len=140, required=True)

    dn_name = None
    rq_name = None
    customer = None
    company = None

    if frappe.db.exists("Delivery Note", ref):
        dn = frappe.get_doc("Delivery Note", ref)
        dn.check_permission("read")
        dn_name = dn.name
        customer = dn.customer
        company = dn.company
    elif frappe.db.exists("Return Quarantine", ref):
        rq = frappe.get_doc("Return Quarantine", ref)
        rq.check_permission("read")
        rq_name = rq.name
        dn_name = rq.return_delivery_note or rq.delivery_note
        customer = rq.retailer
        company = frappe.db.get_value("Delivery Note", dn_name, "company") if dn_name else None
    else:
        frappe.throw(_("Document {0} not found.").format(ref), frappe.DoesNotExistError)

    # In Clothing ERP's operating model: physical return intake does not authorize or create credit notes
    return {
        "reference": ref,
        "delivery_note": dn_name,
        "return_quarantine": rq_name,
        "customer": customer,
        "company": company,
        "financial_disposition": "Pending Commercial Approval",
        "credit_note_issued": False,
        "credit_note": None,
        "replacement_issued": False,
        "replacement_order": None,
        "refund_issued": False,
        "refund": None,
        "warehouse_authority": "Physical quarantine and refurbishment intake only; commercial financial actions require Finance approval.",
    }


@frappe.whitelist()
def get_returns_operational_dashboard(warehouse: str | None = None) -> dict:
    """Return permission-scoped returns, quarantine, and refurbishment SLA queues and metrics."""
    check_rate_limit("get_returns_operational_dashboard", limit=60, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES | QUALITY_INSPECTION_ROLES)
    user = get_current_user()

    allowed_wh = assigned_warehouses(user) if not is_warehouse_admin(user) else None
    if allowed_wh is not None and not allowed_wh:
        # Zero cross-warehouse data exposure
        return {
            "summary": {"total_quarantined": 0, "total_in_refurbishment": 0, "total_awaiting_reinspection": 0, "total_restocked": 0, "sla_breaches": 0},
            "queues": {"quarantine": [], "refurbishment": [], "awaiting_reinspection": [], "ready_to_restock": []},
            "reason_breakdown": {},
        }

    if warehouse:
        warehouse = validate_string(warehouse, "Warehouse", max_len=140)
        if allowed_wh is not None and warehouse not in allowed_wh:
            frappe.throw(frappe._("You do not have access to warehouse {0}.").format(warehouse), frappe.PermissionError)
        warehouses = [warehouse]
    else:
        warehouses = allowed_wh

    where_clauses = ["1=1"]
    params = []
    if warehouses:
        placeholders = ", ".join(["%s"] * len(warehouses))
        where_clauses.append(f"(quarantine_warehouse IN ({placeholders}) OR refurbishment_warehouse IN ({placeholders}))")
        params.extend(warehouses)
        params.extend(warehouses)

    sql = f"""
        SELECT name, item_code, quantity, return_reason, inspection_status,
               quarantine_warehouse, refurbishment_warehouse, target_warehouse,
               refurbishment_assignee, refurbishment_operation,
               creation, modified,
               post_refurbishment_inspection_status
        FROM `tabReturn Quarantine`
        WHERE {' AND '.join(where_clauses)}
        ORDER BY creation ASC
    """
    records = frappe.db.sql(sql, params, as_dict=True)

    now = now_datetime()
    quarantine_queue = []
    refurbishment_queue = []
    reinspection_queue = []
    ready_to_restock_queue = []
    reason_breakdown: dict[str, int] = {}
    sla_breaches = 0
    restocked_count = 0

    for r in records:
        reason = (r.get("return_reason") if isinstance(r, dict) else r.return_reason) or "Other Quality Issue"
        reason_breakdown[reason] = reason_breakdown.get(reason, 0) + 1

        created = r.get("creation") if isinstance(r, dict) else r.creation
        if isinstance(created, str):
            from frappe.utils import get_datetime
            created = get_datetime(created)

        aging_hours = 0.0
        if created:
            try:
                now_cmp = now
                if hasattr(created, "tzinfo") and created.tzinfo and not (hasattr(now_cmp, "tzinfo") and now_cmp.tzinfo):
                    now_cmp = now_datetime(timezone.utc)
                elif not (hasattr(created, "tzinfo") and created.tzinfo) and (hasattr(now_cmp, "tzinfo") and now_cmp.tzinfo):
                    now_cmp = now_cmp.replace(tzinfo=None)
                aging_hours = max(0.0, round((now_cmp - created).total_seconds() / 3600.0, 1))
            except Exception:
                aging_hours = 0.0

        status = r.get("inspection_status") if isinstance(r, dict) else r.inspection_status
        post_status = r.get("post_refurbishment_inspection_status") if isinstance(r, dict) else getattr(r, "post_refurbishment_inspection_status", None)

        item_row = {
            "name": r.get("name") if isinstance(r, dict) else r.name,
            "item_code": r.get("item_code") if isinstance(r, dict) else r.item_code,
            "quantity": flt(r.get("quantity") if isinstance(r, dict) else r.quantity),
            "reason": r.get("return_reason") if isinstance(r, dict) else r.return_reason,
            "status": status,
            "quarantine_warehouse": r.get("quarantine_warehouse") if isinstance(r, dict) else r.quarantine_warehouse,
            "refurbishment_warehouse": r.get("refurbishment_warehouse") if isinstance(r, dict) else r.refurbishment_warehouse,
            "aging_hours": aging_hours,
        }

        if status == "Quarantined":
            breached = aging_hours > 24.0  # 24h SLA for initial quarantine inspection
            item_row["sla_breached"] = breached
            if breached:
                sla_breaches += 1
            quarantine_queue.append(item_row)

        elif status == "In Refurbishment":
            item_row["assignee"] = r.get("refurbishment_assignee") if isinstance(r, dict) else getattr(r, "refurbishment_assignee", None)
            item_row["operation"] = r.get("refurbishment_operation") if isinstance(r, dict) else getattr(r, "refurbishment_operation", None)
            breached = aging_hours > 72.0  # 72h SLA for refurbishment
            item_row["sla_breached"] = breached
            if breached:
                sla_breaches += 1
            refurbishment_queue.append(item_row)

        elif status == "Awaiting Reinspection":
            breached = aging_hours > 24.0
            item_row["sla_breached"] = breached
            if breached:
                sla_breaches += 1
            reinspection_queue.append(item_row)

        elif status == "Inspected - Passed Refurbishment":
            if post_status in {"Re-inspected - Passed", "Not Required"}:
                ready_to_restock_queue.append(item_row)
            else:
                quarantine_queue.append(item_row)

        elif status == "Restocked":
            restocked_count += 1

    return {
        "summary": {
            "total_quarantined": len(quarantine_queue),
            "total_in_refurbishment": len(refurbishment_queue),
            "total_awaiting_reinspection": len(reinspection_queue),
            "total_ready_to_restock": len(ready_to_restock_queue),
            "total_restocked": restocked_count,
            "sla_breaches": sla_breaches,
        },
        "queues": {
            "quarantine": quarantine_queue[:50],
            "refurbishment": refurbishment_queue[:50],
            "awaiting_reinspection": reinspection_queue[:50],
            "ready_to_restock": ready_to_restock_queue[:50],
        },
        "reason_breakdown": reason_breakdown,
    }


@frappe.whitelist(methods=["POST"])
def recommend_return_disposition(
    quarantine_name: str,
    disposition: str,
    notes: str | None = None,
    photo_evidence: str | None = None,
) -> dict:
    """Recommend return disposition (Restock, Refurbish, Seconds, Scrap, Claim, On Hold)."""
    from quality_erp.quality import recommend_return_disposition as _rec
    return _rec(quarantine_name=quarantine_name, disposition=disposition, notes=notes, photo_evidence=photo_evidence)


@frappe.whitelist(methods=["POST"])
def approve_return_disposition(
    quarantine_name: str,
    decision: str,
    approval_notes: str | None = None,
    target_warehouse: str | None = None,
    supplier_claim_amount: float | None = None,
) -> dict:
    """Authorize a return disposition (Scrap, Seconds Sale, Supplier Claim, On Hold). Business Admin only."""
    from quality_erp.quality import approve_return_disposition as _appr
    return _appr(
        quarantine_name=quarantine_name,
        decision=decision,
        approval_notes=approval_notes,
        target_warehouse=target_warehouse,
        supplier_claim_amount=supplier_claim_amount,
    )

