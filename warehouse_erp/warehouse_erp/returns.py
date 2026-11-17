"""Warehouse customer return intake, quarantine isolation, and refurbishment pipeline.

Enforces the operational model requirements:
- Scan returned exact Item/Size/serial/batch against an authorized original Delivery Note.
- Prevent duplicate or excess returns through row-locked balance verification.
- Direct all returned stock into a native quarantine Warehouse via submitted native Delivery Note return.
- Create linked Return Quarantine tracking record in Quality ERP.
- Require Quality inspection approval ('Inspected - Passed Refurbishment') before movement to refurbishment WIP.
- Move refurbished stock back to saleable inventory only through submitted native ERPNext Stock Entry documents.
- Strictly enforce warehouse user permissions and server-side role validation on all state transitions.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
)
from warehouse_erp.api_security import check_rate_limit, record_security_audit_event
from warehouse_erp.security import (
    assigned_warehouses,
    get_current_user,
    is_warehouse_admin,
    require_role,
)

RETURN_INTAKE_ROLES = {ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"}
VALID_RETURN_REASONS = {
    "Defective Stitching",
    "Fabric Fault",
    "Size Mismatch",
    "Customer Return",
    "Other Quality Issue",
}


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
) -> dict:
    """Atomically validate, return, and isolate garments into native quarantine."""
    check_rate_limit("intake_customer_return", limit=60, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)
    user = get_current_user()

    delivery_note = str(delivery_note or "").strip()
    item_code = str(item_code or "").strip()
    quarantine_warehouse = str(quarantine_warehouse or "").strip()
    return_reason = str(return_reason or "").strip()
    return_qty = _validate_return_quantity(quantity)

    if return_reason not in VALID_RETURN_REASONS:
        frappe.throw(
            _("Invalid return reason. Must be one of: {0}").format(", ".join(VALID_RETURN_REASONS)),
            frappe.ValidationError,
        )

    # Warehouse authorization
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if quarantine_warehouse not in allowed:
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

    return {
        "return_delivery_note": return_dn.name,
        "return_quarantine": quarantine_doc.get("name"),
        "customer": orig_dn.customer,
        "item_code": item_code,
        "quantity": return_qty,
        "quarantine_warehouse": quarantine_warehouse,
        "status": "Quarantined",
    }


@frappe.whitelist(methods=["POST"])
def move_to_refurbishment(quarantine_name: str, refurbishment_warehouse: str) -> dict:
    """Move quality-cleared returned stock to refurbishment WIP via native Stock Entry."""
    check_rate_limit("move_to_refurbishment", limit=30, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)
    user = get_current_user()

    quarantine_name = str(quarantine_name or "").strip()
    refurbishment_warehouse = str(refurbishment_warehouse or "").strip()

    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if refurbishment_warehouse not in allowed:
            frappe.throw(
                _("You do not have permission for refurbishment warehouse {0}.").format(refurbishment_warehouse),
                frappe.PermissionError,
            )

    rows = frappe.db.sql(
        "SELECT name, inspection_status, item_code, quantity, quarantine_warehouse FROM `tabReturn Quarantine` WHERE name = %s FOR UPDATE",
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

    return {
        "return_quarantine": rq.name,
        "stock_entry": se.name,
        "status": rq.inspection_status,
        "refurbishment_warehouse": refurbishment_warehouse,
    }


@frappe.whitelist(methods=["POST"])
def complete_refurbishment(
    quarantine_name: str,
    target_saleable_warehouse: str,
    notes: str | None = None,
) -> dict:
    """Restock successfully refurbished stock back into saleable inventory via native Stock Entry."""
    check_rate_limit("complete_refurbishment", limit=30, window_seconds=60)
    require_role(RETURN_INTAKE_ROLES)
    user = get_current_user()

    quarantine_name = str(quarantine_name or "").strip()
    target_saleable_warehouse = str(target_saleable_warehouse or "").strip()

    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if target_saleable_warehouse not in allowed:
            frappe.throw(
                _("You do not have permission for saleable warehouse {0}.").format(target_saleable_warehouse),
                frappe.PermissionError,
            )

    rows = frappe.db.sql(
        "SELECT name, inspection_status, item_code, quantity, refurbishment_warehouse FROM `tabReturn Quarantine` WHERE name = %s FOR UPDATE",
        (quarantine_name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Return Quarantine {0} not found.").format(quarantine_name), frappe.DoesNotExistError)

    curr = rows[0]
    curr_status = curr.get("inspection_status") if isinstance(curr, dict) else curr.inspection_status
    if curr_status != "In Refurbishment":
        frappe.throw(
            _(
                "Cannot complete refurbishment: Return Quarantine {0} status is '{1}'. "
                "Only goods currently in refurbishment can be restocked."
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

    return {
        "return_quarantine": rq.name,
        "restock_entry": se.name,
        "status": rq.inspection_status,
        "target_warehouse": target_saleable_warehouse,
    }
