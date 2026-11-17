"""Permission-aware Clothing ERP views over native fulfillment documents."""

from datetime import date
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint, escape_html, flt, getdate

from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
)
from warehouse_erp.api_security import (
    check_rate_limit,
    clear_idempotency,
    record_security_audit_event,
    save_idempotency_result,
    validate_bounded_list,
    validate_float,
    validate_idempotency,
    validate_int,
    validate_string,
)
from warehouse_erp.security import (
    assigned_warehouses,
    get_current_user,
    is_warehouse_admin,
    is_warehouse_manager,
    require_role,
)

FULFILLMENT_ROLES = {
    ROLE_WAREHOUSE_MANAGER,
    ROLE_BUSINESS_ADMIN,
}
SHORTAGE_RESOLUTION_ROLES = {ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}
TASK_TYPES = {"pick": "Pick List", "delivery": "Delivery Note"}
TASK_STATES = {"all", "draft", "submitted", "cancelled"}
MAX_TASK_PAGE_SIZE = 50
MAX_PICK_SCAN_QUANTITY = 100_000


def _task_type(value):
    value = str(value or "pick").strip().lower()
    if value not in TASK_TYPES:
        frappe.throw(frappe._("The fulfillment task type is invalid."))
    return value, TASK_TYPES[value]


def _task_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 140:
        frappe.throw(frappe._("The fulfillment task is invalid."), frappe.PermissionError)
    return value.strip()


@frappe.whitelist()
def get_fulfillment_tasks(task_type="pick", state="all", search=None, page=1, page_size=20):
    """Return native tasks using existing DocType and row-level permission hooks."""
    require_role(FULFILLMENT_ROLES)
    task_type, doctype = _task_type(task_type)
    state = str(state or "all").strip().lower()
    if state not in TASK_STATES:
        frappe.throw(frappe._("The fulfillment status filter is invalid."))
    search = str(search or "").strip()[:80]
    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), MAX_TASK_PAGE_SIZE)
    filters = {}
    if state == "draft":
        filters["docstatus"] = 0
    elif state == "submitted":
        filters["docstatus"] = 1
    elif state == "cancelled":
        filters["docstatus"] = 2
    fields = ["name", "customer", "customer_name", "status", "docstatus", "modified"]
    fields.extend(
        ["purpose", "parent_warehouse"]
        if task_type == "pick"
        else ["posting_date", "total_qty"]
    )
    query = {
        "doctype": doctype,
        "filters": filters,
        "fields": fields,
        "order_by": "modified desc, name desc",
        "start": (page - 1) * page_size,
        "limit": page_size + 1,
    }
    if search:
        pattern = f"%{search}%"
        query["or_filters"] = {
            "name": ["like", pattern],
            "customer": ["like", pattern],
            "customer_name": ["like", pattern],
        }
    # get_list is deliberate: Pick List/Delivery Note permission hooks enforce assigned
    # warehouses, mixed-warehouse rejection and the operator's open ToDo assignment.
    rows = frappe.get_list(**query)
    return {
        "tasks": rows[:page_size],
        "task_type": task_type,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) > page_size,
        },
    }


@frappe.whitelist()
def get_fulfillment_task(task_type, name):
    """Return a bounded projection after native document permission validation."""
    require_role(FULFILLMENT_ROLES)
    task_type, doctype = _task_type(task_type)
    name = _task_name(name)
    document = frappe.get_doc(doctype, name)
    document.check_permission("read")
    child_rows = (document.get("locations") or []) if task_type == "pick" else (document.get("items") or [])
    workflow_name = (
        _active_pick_list_workflow()
        if task_type == "pick" and document.docstatus == 0
        else None
    )
    is_mgr = is_warehouse_manager()
    rows = []
    for row in child_rows[:200]:
        can_split = bool(
            task_type == "pick"
            and document.docstatus == 0
            and 0 < flt(row.get("picked_qty"), 6) < flt(row.get("stock_qty"), 6)
            and is_mgr
            and not workflow_name
        )
        rows.append(
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "warehouse": row.warehouse,
                "qty": row.qty,
                "stock_qty": row.stock_qty,
                "picked_qty": row.get("picked_qty"),
                "stock_uom": row.stock_uom,
                "batch_no": row.get("batch_no"),
                "serial_no": row.get("serial_no"),
                "sales_order": row.get("sales_order") or row.get("against_sales_order"),
                "location": row.name,
                "can_split": can_split,
            }
        )
    pick_complete = bool(child_rows) and all(
        flt(row.get("picked_qty"), 6) >= flt(row.get("stock_qty"), 6)
        for row in child_rows
    )
    has_unpicked_rows = any(
        flt(row.get("picked_qty"), 6) == 0
        and flt(row.get("stock_qty"), 6) > 0
        for row in child_rows
    )
    packing_slips = []
    if task_type == "delivery":
        packing_slips = frappe.get_all(
            "Packing Slip",
            filters={"delivery_note": document.name, "docstatus": ["<", 2]},
            fields=[
                "name",
                "from_case_no",
                "to_case_no",
                "gross_weight_pkg",
                "net_weight_pkg",
                "gross_weight_uom",
                "docstatus",
                "custom_package_barcode",
                "custom_length",
                "custom_width",
                "custom_height",
                "custom_dimension_uom",
            ],
            order_by="from_case_no asc",
        )
    return {
        "name": document.name,
        "task_type": task_type,
        "customer": document.get("customer"),
        "customer_name": document.get("customer_name"),
        "company": document.company,
        "status": document.status,
        "docstatus": document.docstatus,
        "purpose": document.get("purpose"),
        "posting_date": document.get("posting_date"),
        "parent_warehouse": document.get("parent_warehouse"),
        "rows": rows,
        "rows_truncated": len(child_rows) > len(rows),
        "can_verify_items": task_type == "pick" and document.docstatus == 0,
        "can_complete_pick": bool(
            task_type == "pick"
            and document.docstatus == 0
            and pick_complete
            and not workflow_name
        ),
        "workflow": workflow_name,
        "can_resolve_shortage": bool(
            task_type == "pick"
            and document.docstatus == 0
            and has_unpicked_rows
            and not workflow_name
            and is_mgr
        ),
        "can_split_shortage": any(r.get("can_split") for r in rows),
        "can_create_delivery_note": bool(task_type == "pick" and document.docstatus == 1),
        "can_pack": bool(task_type == "delivery" and document.docstatus == 0 and is_mgr),
        "packing_slips": packing_slips,
        "can_dispatch_delivery": bool(
            task_type == "delivery" and document.docstatus == 0 and is_mgr
        ),
        "can_prepare_billing": bool(
            task_type == "delivery" and document.docstatus == 1 and not document.get("custom_billing_invoice")
        ),
        "can_record_handoff": bool(
            task_type == "delivery" and document.docstatus == 1 and not document.get("custom_delivery_handoff")
        ),
        "custom_wave_id": document.get("custom_wave_id"),
        "custom_route_id": document.get("custom_route_id"),
        "custom_delivery_handoff": document.get("custom_delivery_handoff"),
        "custom_billing_invoice": document.get("custom_billing_invoice"),
        "transporter_name": document.get("transporter_name"),
        "vehicle_no": document.get("vehicle_no"),
        "lr_no": document.get("lr_no"),
        "lr_date": str(document.get("lr_date")) if document.get("lr_date") else None,
    }


def _scan_quantity(value):
    try:
        quantity = Decimal(str(value))
    except InvalidOperation, ValueError:
        frappe.throw(frappe._("Scan quantity must be a positive whole number."))
    if (
        not quantity.is_finite()
        or quantity != quantity.to_integral_value()
        or quantity <= 0
        or quantity > MAX_PICK_SCAN_QUANTITY
    ):
        frappe.throw(frappe._("Scan quantity must be a positive whole number."))
    return int(quantity)


def _pick_location(document, location):
    location = str(location or "").strip()[:140]
    row = next((row for row in document.locations if row.name == location), None)
    if not row:
        frappe.throw(frappe._("The selected Pick List row is unavailable."))
    return row


def _scan_barcode(barcode):
    from erpnext.stock.utils import scan_barcode

    return frappe._dict(scan_barcode(barcode) or {})


def _resolve_pick_scan(barcode, item_code):
    barcode = str(barcode or "").strip()[:140]
    if not barcode:
        frappe.throw(frappe._("Scan or enter an item, batch or serial barcode."))
    scan = (
        frappe._dict(item_code=item_code)
        if barcode == item_code
        else _scan_barcode(barcode)
    )
    if scan.get("item_code") != item_code:
        frappe.throw(
            frappe._("The scan does not match the selected Pick List item.")
        )
    return scan


def _item_tracking(item_code):
    return frappe._dict(
        frappe.get_cached_value(
            "Item", item_code, ("has_serial_no", "has_batch_no"), as_dict=True
        )
        or {}
    )


def _serial_numbers(value):
    from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

    return get_serial_nos(value)


def _serial_already_scanned(document, serial_no):
    for row in document.locations:
        if (
            flt(row.get("picked_qty")) > 0
            and serial_no in _serial_numbers(row.get("serial_no"))
        ):
            return True
    return False


def _bundle_contains(row, scan):
    bundle = row.get("serial_and_batch_bundle")
    if not bundle:
        return False
    filters = {"parent": bundle}
    if scan.get("serial_no"):
        filters["serial_no"] = scan.serial_no
    elif scan.get("batch_no"):
        filters["batch_no"] = scan.batch_no
    return bool(frappe.db.exists("Serial and Batch Entry", filters))


def _validate_pick_scan(document, row, barcode, quantity, apply=False):
    scan = _resolve_pick_scan(barcode, row.item_code)
    tracking = _item_tracking(row.item_code)
    has_serial = bool(tracking.get("has_serial_no"))
    has_batch = bool(tracking.get("has_batch_no"))

    if has_serial:
        if not scan.get("serial_no"):
            frappe.throw(frappe._("Scan a Serial No for this serialized item."))
        if quantity != 1:
            frappe.throw(frappe._("Serialized items must be scanned one at a time."))
        if row.get("serial_and_batch_bundle") and not _bundle_contains(row, scan):
            frappe.throw(
                frappe._("The scanned serial is not allocated to this Pick List row bundle.")
            )
        if _serial_already_scanned(document, scan.serial_no):
            frappe.throw(frappe._("This Serial No has already been scanned."))
    elif has_batch and not scan.get("batch_no"):
        frappe.throw(frappe._("Scan a Batch No for this batched item."))

    if scan.get("batch_no"):
        expiry = frappe.db.get_value("Batch", scan.batch_no, "expiry_date")
        if expiry and getdate(expiry) < date.today():
            frappe.throw(
                frappe._("Batch {0} expired on {1} and cannot be picked.").format(scan.batch_no, expiry),
                frappe.ValidationError,
            )

    if has_batch and row.get("batch_no") and scan.get("batch_no") != row.batch_no:
        frappe.throw(
            frappe._("The scanned batch does not match this Pick List row.")
        )
    if row.get("serial_and_batch_bundle") and not _bundle_contains(row, scan):
        frappe.throw(
            frappe._("The scanned serial or batch is not allocated to this Pick List row.")
        )

    if apply:
        if scan.get("serial_no"):
            serials = (
                _serial_numbers(row.get("serial_no"))
                if flt(row.get("picked_qty")) > 0
                else []
            )
            serials.append(scan.serial_no)
            row.serial_no = "\n".join(serials)
        if not row.get("serial_and_batch_bundle"):
            if scan.get("batch_no"):
                row.batch_no = scan.batch_no
            if has_serial or has_batch:
                row.use_serial_batch_fields = 1

    return frappe._dict(
        scan_type=(
            "serial"
            if scan.get("serial_no")
            else "batch"
            if scan.get("batch_no")
            else "item"
        ),
        serial_no=scan.get("serial_no"),
        batch_no=scan.get("batch_no"),
    )


def _active_pick_list_workflow():
    from frappe.model.workflow import get_workflow_name

    return get_workflow_name("Pick List")


def _require_complete_pick(document):
    if not document.locations or any(
        flt(row.get("picked_qty"), 6) < flt(row.get("stock_qty"), 6)
        for row in document.locations
    ):
        frappe.throw(
            frappe._(
                "Verify every required item quantity before completing this Pick List."
            )
        )


def _require_no_pick_workflow():
    if workflow_name := _active_pick_list_workflow():
        frappe.throw(
            frappe._(
                "Pick List Workflow {0} is active. Complete its configured approval "
                "actions; Clothing ERP will not bypass the workflow."
            ).format(workflow_name)
        )


def _lock_pick_list(pick_list):
    frappe.db.sql(
        "select name from `tabPick List` where name = %s for update", pick_list
    )


def _lock_pick_bundles(document):
    bundle_names = sorted({
        row.serial_and_batch_bundle
        for row in getattr(document, "locations", [])
        if row.get("serial_and_batch_bundle")
    })
    if bundle_names:
        placeholders = ", ".join(["%s"] * len(bundle_names))
        frappe.db.sql(
            f"SELECT name FROM `tabSerial and Batch Bundle` WHERE name IN ({placeholders}) FOR UPDATE",
            tuple(bundle_names),
        )


def _close_pick_assignments(pick_list):
    from frappe.desk.form.assign_to import close_all_assignments

    close_all_assignments("Pick List", pick_list, ignore_permissions=True)


def _shortage_reason(value):
    value = " ".join(str(value or "").split())
    if len(value) < 5 or len(value) > 500:
        frappe.throw(frappe._("Shortage reason must be between 5 and 500 characters."))
    return value


def _unpicked_quantity(document):
    return sum(
        flt(row.get("stock_qty"))
        for row in document.locations
        if flt(row.get("picked_qty")) == 0
    )


def _picked_rows(document):
    return {
        row.name: (
            row.item_code,
            row.warehouse,
            flt(row.get("picked_qty"), 6),
            flt(row.get("stock_qty"), 6),
            row.get("batch_no"),
            row.get("serial_no"),
        )
        for row in document.locations
        if flt(row.get("picked_qty")) > 0
    }


def _require_unpicked_rows(document):
    if not any(
        flt(row.get("picked_qty"), 6) == 0
        and flt(row.get("stock_qty"), 6) > 0
        for row in document.locations
    ):
        frappe.throw(
            frappe._(
                "Only completely unpicked rows can be reallocated. "
                "This Pick List has no eligible shortage rows."
            )
        )


def _require_picked_rows_preserved(document, snapshot):
    current = _picked_rows(document)
    if any(current.get(name) != values for name, values in snapshot.items()):
        frappe.throw(
            frappe._(
                "ERPNext changed an already-scanned row during reallocation; "
                "the shortage update was rolled back."
            )
        )


@frappe.whitelist(methods=["POST"])
def verify_pick_item(pick_list, location, barcode, quantity=1, warehouse=None):
    """Increment native picked quantity after exact row and barcode verification."""
    check_rate_limit("verify_pick_item", limit=120, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    pick_list = _task_name(pick_list)
    location = validate_string(location, "Location", max_len=140, required=True)
    barcode = validate_string(barcode, "Barcode", max_len=140, required=True)
    quantity = _scan_quantity(quantity)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Pick List can be verified."))
    row = _pick_location(document, location)

    user = get_current_user()
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if row.warehouse and row.warehouse not in allowed:
            frappe.throw(
                frappe._("You do not have permission for warehouse {0}.").format(row.warehouse),
                frappe.PermissionError,
            )

    if warehouse and str(warehouse).strip() != row.warehouse:
        frappe.throw(
            frappe._("Item scanned from warehouse {0} does not match required location warehouse {1}.").format(
                warehouse, row.warehouse
            ),
            frappe.ValidationError,
        )

    _validate_pick_scan(document, row, barcode, quantity)

    _lock_pick_list(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("This Pick List changed while scanning. Refresh it."))
    row = _pick_location(document, location)
    scan = _validate_pick_scan(document, row, barcode, quantity, apply=True)
    required = flt(row.stock_qty)
    picked = flt(row.picked_qty)
    if picked + quantity > required:
        frappe.throw(
            frappe._(
                "This scan would exceed the required quantity of {0} {1}."
            ).format(required, row.stock_uom)
        )
    document.scan_mode = 1
    row.picked_qty = picked + quantity
    try:
        document.save(ignore_permissions=True)
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Pick Item Verified",
        "Pick List",
        document.name,
        {
            "location": row.name,
            "item_code": row.item_code,
            "quantity": quantity,
            "picked_qty": row.picked_qty,
        },
    )

    return {
        "pick_list": document.name,
        "location": row.name,
        "item_code": row.item_code,
        "warehouse": row.warehouse,
        "picked_qty": row.picked_qty,
        "required_qty": row.stock_qty,
        "complete": flt(row.picked_qty) == flt(row.stock_qty),
        "scan_type": scan.scan_type,
        "serial_no": scan.serial_no,
        "batch_no": scan.batch_no,
    }


@frappe.whitelist(methods=["POST"])
def undo_pick_item_scan(pick_list, location, barcode=None, quantity=1):
    """Undo the last unsubmitted scan on a draft Pick List row with an audit comment."""
    check_rate_limit("undo_pick_item_scan", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    pick_list = _task_name(pick_list)
    location = validate_string(location, "Location", max_len=140, required=True)
    quantity = _scan_quantity(quantity)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Pick List scan can be undone."))
    _require_no_pick_workflow()

    _lock_pick_list(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("This Pick List changed. Refresh it."))
    _require_no_pick_workflow()

    row = _pick_location(document, location)
    current_picked = flt(row.picked_qty)
    if current_picked <= 0:
        frappe.throw(frappe._("This row has no picked items to undo."))

    undo_qty = min(quantity, int(current_picked))
    tracking = _item_tracking(row.item_code)
    has_serial = bool(tracking.get("has_serial_no"))

    undone_serial = None
    if has_serial and row.get("serial_no"):
        serials = _serial_numbers(row.get("serial_no"))
        if barcode and str(barcode).strip() in serials:
            undone_serial = str(barcode).strip()
            serials.remove(undone_serial)
        elif serials:
            undone_serial = serials.pop()
        row.serial_no = "\n".join(serials)

    new_picked = max(0.0, current_picked - undo_qty)
    row.picked_qty = new_picked

    document.add_comment(
        "Comment",
        frappe._(
            "<strong>Clothing ERP scan undone</strong><br>"
            "Item: {0}<br>Location: {1}<br>Quantity undone: {2}<br>Undone serial: {3}<br>Remaining picked: {4} of {5}"
        ).format(
            escape_html(row.item_code),
            escape_html(row.name),
            undo_qty,
            escape_html(undone_serial or "—"),
            flt(new_picked),
            flt(row.stock_qty),
        ),
    )
    document.flags.ignore_permissions = True
    try:
        document.save(ignore_permissions=True)
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Pick Item Scan Undone",
        "Pick List",
        document.name,
        {
            "location": row.name,
            "item_code": row.item_code,
            "undo_qty": undo_qty,
            "undone_serial": undone_serial,
        },
    )

    return {
        "pick_list": document.name,
        "location": row.name,
        "item_code": row.item_code,
        "picked_qty": row.picked_qty,
        "required_qty": row.stock_qty,
        "undone_serial": undone_serial,
        "complete": flt(row.picked_qty) >= flt(row.stock_qty),
    }


@frappe.whitelist(methods=["POST"])
def resolve_pick_shortage(pick_list, reason):
    """Reallocate completely unpicked rows with ERPNext's native stock selection."""
    require_role(SHORTAGE_RESOLUTION_ROLES)
    pick_list = _task_name(pick_list)
    reason = _shortage_reason(reason)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Pick List shortage can be resolved."))
    _require_no_pick_workflow()
    _require_unpicked_rows(document)

    _lock_pick_list(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(
            frappe._("This Pick List changed during shortage resolution. Refresh it.")
        )
    _require_no_pick_workflow()
    _require_unpicked_rows(document)

    before_unpicked = _unpicked_quantity(document)
    picked_snapshot = _picked_rows(document)
    document.flags.ignore_permissions = True
    # ERPNext removes only zero-picked rows, recalculates available warehouse/batch/
    # serial locations, retains picked rows and validates the resulting Pick List.
    document.set_item_locations(save=True)
    _require_picked_rows_preserved(document, picked_snapshot)
    after_unpicked = _unpicked_quantity(document)
    unallocated = max(before_unpicked - after_unpicked, 0)
    document.add_comment(
        "Comment",
        frappe._(
            "<strong>Clothing ERP shortage resolution</strong><br>"
            "Reason: {0}<br>Unpicked quantity before: {1}; allocated after refresh: "
            "{2}; still unallocated: {3}."
        ).format(
            escape_html(reason),
            flt(before_unpicked),
            flt(after_unpicked),
            flt(unallocated),
        ),
    )
    return {
        "pick_list": document.name,
        "unpicked_before": before_unpicked,
        "allocated_after": after_unpicked,
        "unallocated_qty": unallocated,
        "row_count": len(document.locations),
    }


@frappe.whitelist(methods=["POST"])
def split_pick_shortage_row(pick_list, location, reason):
    """Split a partially picked row into a completed picked row and a new shortage row."""
    require_role(SHORTAGE_RESOLUTION_ROLES)
    pick_list = _task_name(pick_list)
    reason = _shortage_reason(reason)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Pick List shortage can be split."))
    _require_no_pick_workflow()

    row = _pick_location(document, location)
    picked_stock = flt(row.get("picked_qty"), 6)
    required_stock = flt(row.get("stock_qty"), 6)
    if picked_stock <= 0:
        frappe.throw(
            frappe._("Only partially picked rows can be split. Use shortage reallocation for unpicked rows.")
        )
    if picked_stock >= required_stock:
        frappe.throw(frappe._("This row is already completely picked."))

    _lock_pick_list(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(
            frappe._("This Pick List changed during shortage splitting. Refresh it.")
        )
    _require_no_pick_workflow()

    row = _pick_location(document, location)
    picked_stock = flt(row.get("picked_qty"), 6)
    required_stock = flt(row.get("stock_qty"), 6)
    if picked_stock <= 0 or picked_stock >= required_stock:
        frappe.throw(
            frappe._("This row's picked state changed. Refresh the Pick List.")
        )

    shortage_stock = required_stock - picked_stock
    conversion_factor = flt(row.get("conversion_factor")) or 1.0
    picked_qty = picked_stock / conversion_factor
    shortage_qty = shortage_stock / conversion_factor

    # Adjust the existing row to represent the completed portion
    row.stock_qty = picked_stock
    row.qty = picked_qty

    # Append the new shortage row with picked_qty = 0
    new_row = document.append(
        "locations",
        {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "item_group": row.get("item_group"),
            "description": row.get("description"),
            "warehouse": row.warehouse,
            "qty": shortage_qty,
            "stock_qty": shortage_stock,
            "picked_qty": 0.0,
            "stock_uom": row.stock_uom,
            "uom": row.uom,
            "conversion_factor": row.conversion_factor,
            "sales_order": row.get("sales_order"),
            "sales_order_item": row.get("sales_order_item"),
            "against_sales_order": row.get("against_sales_order"),
            "material_request": row.get("material_request"),
            "material_request_item": row.get("material_request_item"),
        },
    )

    document.add_comment(
        "Comment",
        frappe._(
            "<strong>Clothing ERP partial shortage split</strong><br>"
            "Item: {0}<br>Location: {1}<br>Picked: {2} {3}<br>Split shortage: {4} {3}<br>Reason: {5}"
        ).format(
            escape_html(row.item_code),
            escape_html(row.name),
            flt(picked_stock),
            escape_html(row.stock_uom or ""),
            flt(shortage_stock),
            escape_html(reason),
        ),
    )
    document.flags.ignore_permissions = True
    document.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "pick_list": document.name,
        "location": row.name,
        "new_location": new_row.name,
        "picked_qty": picked_stock,
        "shortage_qty": shortage_stock,
    }


@frappe.whitelist(methods=["POST"])
def complete_pick_list(pick_list):
    """Submit a fully verified Pick List through ERPNext's native controller."""
    check_rate_limit("complete_pick_list", limit=30, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    pick_list = _task_name(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Pick List can be completed."))
    _require_no_pick_workflow()
    _require_complete_pick(document)

    _lock_pick_list(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(
            frappe._("This Pick List changed while being completed. Refresh it.")
        )
    _require_no_pick_workflow()
    _require_complete_pick(document)
    _lock_pick_bundles(document)

    document.flags.ignore_permissions = True
    # Native submit owns stock availability, serial/batch, reservation, reference
    # quantity, previous-document and final status behavior.
    previous_bundle_context = frappe.flags.get("clothing_pick_bundle")
    frappe.flags.clothing_pick_bundle = document.name
    try:
        document.submit()
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        if previous_bundle_context is None:
            frappe.flags.pop("clothing_pick_bundle", None)
        else:
            frappe.flags.clothing_pick_bundle = previous_bundle_context

    _close_pick_assignments(document.name)

    record_security_audit_event(
        "Pick List Completed",
        "Pick List",
        document.name,
        {"status": document.status, "docstatus": document.docstatus},
    )

    return {
        "pick_list": document.name,
        "docstatus": document.docstatus,
        "status": document.status,
    }


def _lock_delivery_note(delivery_note):
    frappe.db.sql(
        "select name from `tabDelivery Note` where name = %s for update", delivery_note
    )


@frappe.whitelist(methods=["POST"])
def create_delivery_note_from_pick(pick_list):
    """Create a native draft Delivery Note from a submitted Pick List."""
    check_rate_limit("create_delivery_note_from_pick", limit=30, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    pick_list = _task_name(pick_list)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 1:
        frappe.throw(
            frappe._("Only a completed (submitted) Pick List can be converted to a Delivery Note.")
        )

    from warehouse_erp.security import assigned_warehouses, is_warehouse_admin

    user = frappe.session.user
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        for row in document.locations:
            if row.warehouse and row.warehouse not in allowed:
                frappe.throw(
                    frappe._("You do not have permission for warehouse {0}.").format(row.warehouse),
                    frappe.PermissionError,
                )

    # Return existing draft Delivery Note if already generated for this Pick List
    existing = frappe.db.sql(
        """
        SELECT DISTINCT dn.name, dn.customer, dn.docstatus
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dni.against_pick_list = %s AND dn.docstatus = 0
        """,
        (pick_list,),
        as_dict=True,
    )
    if existing:
        record = existing[0]
        return {
            "delivery_note": record.get("name") if isinstance(record, dict) else record.name,
            "customer": record.get("customer") if isinstance(record, dict) else record.customer,
            "docstatus": record.get("docstatus") if isinstance(record, dict) else record.docstatus,
        }

    from erpnext.stock.doctype.pick_list.pick_list import create_delivery_note

    try:
        result = create_delivery_note(pick_list)
    except Exception:
        frappe.db.rollback()
        raise

    if isinstance(result, list):
        if not result:
            frappe.throw(
                frappe._("No Delivery Note could be generated from Pick List {0}.").format(pick_list)
            )
        dn = result[0]
    else:
        dn = result

    if not dn or not getattr(dn, "name", None):
        frappe.throw(
            frappe._("No Delivery Note could be generated from Pick List {0}.").format(pick_list)
        )

    record_security_audit_event(
        "Delivery Note Created",
        "Delivery Note",
        dn.name,
        {"pick_list": pick_list, "customer": dn.customer},
    )

    frappe.db.commit()
    return {
        "delivery_note": dn.name,
        "customer": dn.customer,
        "docstatus": dn.docstatus,
    }


@frappe.whitelist(methods=["POST"])
def create_packing_slip(
    delivery_note,
    from_case_no=None,
    to_case_no=None,
    gross_weight_pkg=0.0,
    net_weight_pkg=0.0,
    package_barcode=None,
    length=None,
    width=None,
    height=None,
    dimension_uom="cm",
):
    """Create and save a native Packing Slip with package identity and dimensions."""
    require_role(FULFILLMENT_ROLES)
    delivery_note = _task_name(delivery_note)
    document = frappe.get_doc("Delivery Note", delivery_note)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(
            frappe._("A Packing Slip can only be created for a draft Delivery Note.")
        )

    from warehouse_erp.security import assigned_warehouses, is_warehouse_admin

    user = frappe.session.user
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        for item in (document.get("items") or []):
            item_wh = item.get("warehouse") if isinstance(item, dict) else getattr(item, "warehouse", None)
            if item_wh and item_wh not in allowed:
                frappe.throw(
                    frappe._("You do not have permission for warehouse {0}.").format(item_wh),
                    frappe.PermissionError,
                )

    from erpnext.stock.doctype.delivery_note.delivery_note import make_packing_slip

    packing_slip = make_packing_slip(delivery_note)
    if not packing_slip.get("items"):
        frappe.throw(
            frappe._("All items in Delivery Note {0} are already packed.").format(delivery_note)
        )

    # Determine case numbering if not provided
    if from_case_no is None:
        last_case = frappe.db.sql(
            """
            SELECT MAX(to_case_no) FROM `tabPacking Slip`
            WHERE delivery_note = %s AND docstatus < 2
            """,
            (delivery_note,),
        )[0][0]
        from_case_no = cint(last_case) + 1 if last_case else 1
    else:
        from_case_no = max(cint(from_case_no), 1)

    if to_case_no is None:
        to_case_no = from_case_no
    else:
        to_case_no = max(cint(to_case_no), from_case_no)

    packing_slip.from_case_no = from_case_no
    packing_slip.to_case_no = to_case_no
    if flt(gross_weight_pkg) > 0:
        packing_slip.gross_weight_pkg = flt(gross_weight_pkg)
    if flt(net_weight_pkg) > 0:
        packing_slip.net_weight_pkg = flt(net_weight_pkg)

    if package_barcode:
        packing_slip.custom_package_barcode = validate_string(package_barcode, "Package Barcode", max_len=140)
    else:
        packing_slip.custom_package_barcode = f"PKG-{delivery_note}-{packing_slip.from_case_no}"

    if length is not None:
        packing_slip.custom_length = flt(length)
    if width is not None:
        packing_slip.custom_width = flt(width)
    if height is not None:
        packing_slip.custom_height = flt(height)
    if dimension_uom:
        packing_slip.custom_dimension_uom = str(dimension_uom).strip()

    packing_slip.flags.ignore_permissions = True
    packing_slip.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "packing_slip": packing_slip.name,
        "delivery_note": document.name,
        "from_case_no": packing_slip.from_case_no,
        "to_case_no": packing_slip.to_case_no,
        "gross_weight_pkg": packing_slip.gross_weight_pkg,
        "net_weight_pkg": packing_slip.net_weight_pkg,
        "package_barcode": packing_slip.get("custom_package_barcode"),
        "dimensions": {
            "length": flt(packing_slip.get("custom_length")),
            "width": flt(packing_slip.get("custom_width")),
            "height": flt(packing_slip.get("custom_height")),
            "uom": packing_slip.get("custom_dimension_uom") or "cm",
        },
        "item_count": len(packing_slip.get("items") or []),
    }


@frappe.whitelist(methods=["POST"])
def dispatch_delivery_note(
    delivery_note,
    transporter_name=None,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
):
    """Submit and dispatch a native Delivery Note with carrier handoff metadata."""
    check_rate_limit("dispatch_delivery_note", limit=30, window_seconds=60)
    require_role(SHORTAGE_RESOLUTION_ROLES)
    delivery_note = _task_name(delivery_note)
    transporter_name = validate_string(transporter_name, "Transporter Name", max_len=140)
    vehicle_no = validate_string(vehicle_no, "Vehicle No", max_len=140)
    lr_no = validate_string(lr_no, "LR No", max_len=140)
    document = frappe.get_doc("Delivery Note", delivery_note)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Delivery Note can be dispatched."))

    _lock_delivery_note(delivery_note)
    document = frappe.get_doc("Delivery Note", delivery_note)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(
            frappe._("This Delivery Note changed while being dispatched. Refresh it.")
        )

    from warehouse_erp.security import assigned_warehouses, is_warehouse_admin

    user = frappe.session.user
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        for item in (document.get("items") or []):
            item_wh = item.get("warehouse") if isinstance(item, dict) else getattr(item, "warehouse", None)
            if item_wh and item_wh not in allowed:
                frappe.throw(
                    frappe._("You do not have permission for warehouse {0}.").format(item_wh),
                    frappe.PermissionError,
                )

    if transporter_name:
        document.transporter_name = transporter_name
    if vehicle_no:
        document.vehicle_no = vehicle_no
    if lr_no:
        document.lr_no = lr_no
    if lr_date:
        from frappe.utils import getdate
        document.lr_date = getdate(lr_date)

    document.flags.ignore_permissions = True
    try:
        document.submit()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Delivery Note Dispatched",
        "Delivery Note",
        document.name,
        {
            "customer": document.customer,
            "transporter": transporter_name,
            "lr_no": lr_no,
        },
    )

    frappe.db.commit()

    return {
        "delivery_note": document.name,
        "docstatus": document.docstatus,
        "status": document.status,
    }


@frappe.whitelist(methods=["POST"])
def bulk_create_delivery_notes_from_picks(pick_lists, request_id=None):
    """Bounded bulk creation of Delivery Notes from submitted Pick Lists with per-document error reporting."""
    require_role(FULFILLMENT_ROLES)
    if isinstance(pick_lists, str):
        import json
        try:
            pick_lists = json.loads(pick_lists)
        except Exception:
            pick_lists = [p.strip() for p in pick_lists.split(",") if p.strip()]

    if not isinstance(pick_lists, (list, tuple)) or not pick_lists:
        frappe.throw(frappe._("Please provide a list of Pick Lists."))

    if len(pick_lists) > 25:
        frappe.throw(frappe._("Bulk operations are limited to 25 documents at a time."))

    if request_id:
        request_id = validate_string(request_id, "Request ID", max_len=140)
        cached, is_replay = validate_idempotency(
            "bulk_create_delivery_notes_from_picks",
            request_id,
            {"pick_lists": sorted([str(p).strip() for p in pick_lists])},
        )
        if is_replay:
            return cached

    results = []
    succeeded = 0
    failed = 0

    for idx, name in enumerate(pick_lists):
        task_name = str(name).strip()
        sp = f"sp_bcdn_{idx}"
        try:
            frappe.db.savepoint(sp)
            res = create_delivery_note_from_pick(task_name)
            results.append({
                "pick_list": task_name,
                "success": True,
                "delivery_note": res.get("delivery_note"),
                "customer": res.get("customer"),
            })
            succeeded += 1
        except Exception as e:
            frappe.db.rollback(save_point=sp)
            results.append({
                "pick_list": task_name,
                "success": False,
                "error": str(getattr(e, "message", None) or e),
            })
            failed += 1

    payload = {
        "total": len(pick_lists),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }

    if request_id:
        save_idempotency_result(
            "bulk_create_delivery_notes_from_picks",
            request_id,
            payload,
            {"pick_lists": sorted([str(p).strip() for p in pick_lists])},
        )
    return payload


@frappe.whitelist(methods=["POST"])
def bulk_dispatch_delivery_notes(
    delivery_notes,
    transporter_name=None,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
    request_id=None,
):
    """Bounded bulk dispatch of draft Delivery Notes with per-document failure reporting."""
    require_role(SHORTAGE_RESOLUTION_ROLES)
    if isinstance(delivery_notes, str):
        import json
        try:
            delivery_notes = json.loads(delivery_notes)
        except Exception:
            delivery_notes = [d.strip() for d in delivery_notes.split(",") if d.strip()]

    if not isinstance(delivery_notes, (list, tuple)) or not delivery_notes:
        frappe.throw(frappe._("Please provide a list of Delivery Notes."))

    if len(delivery_notes) > 25:
        frappe.throw(frappe._("Bulk operations are limited to 25 documents at a time."))

    if request_id:
        request_id = validate_string(request_id, "Request ID", max_len=140)
        cached, is_replay = validate_idempotency(
            "bulk_dispatch_delivery_notes",
            request_id,
            {"delivery_notes": sorted([str(d).strip() for d in delivery_notes])},
        )
        if is_replay:
            return cached

    results = []
    succeeded = 0
    failed = 0

    for idx, name in enumerate(delivery_notes):
        dn_name = str(name).strip()
        sp = f"sp_bddn_{idx}"
        try:
            frappe.db.savepoint(sp)
            res = dispatch_delivery_note(
                delivery_note=dn_name,
                transporter_name=transporter_name,
                vehicle_no=vehicle_no,
                lr_no=lr_no,
                lr_date=lr_date,
            )
            results.append({
                "delivery_note": dn_name,
                "success": True,
                "status": res.get("status"),
            })
            succeeded += 1
        except Exception as e:
            frappe.db.rollback(save_point=sp)
            results.append({
                "delivery_note": dn_name,
                "success": False,
                "error": str(getattr(e, "message", None) or e),
            })
            failed += 1

    payload = {
        "total": len(delivery_notes),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }

    if request_id:
        save_idempotency_result(
            "bulk_dispatch_delivery_notes",
            request_id,
            payload,
            {"delivery_notes": sorted([str(d).strip() for d in delivery_notes])},
        )
    return payload


@frappe.whitelist(methods=["POST"])
def create_pick_list_from_sales_orders(
    sales_orders,
    parent_warehouse=None,
    purpose="Delivery",
    wave_id=None,
    route_id=None,
    request_id=None,
):
    """Create a draft native Pick List from one or more submitted Sales Orders."""
    check_rate_limit("create_pick_list_from_sales_orders", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    if isinstance(sales_orders, str):
        sales_orders = [s.strip() for s in sales_orders.split(",") if s.strip()]
    sales_orders = validate_bounded_list(sales_orders, "Sales Orders", max_len=50, min_len=1)

    if request_id:
        request_id = validate_string(request_id, "Request ID", max_len=140)
        cached, is_replay = validate_idempotency(
            "create_pick_list_from_sales_orders",
            request_id,
            {"sales_orders": sorted(sales_orders), "parent_warehouse": parent_warehouse or "", "purpose": purpose},
        )
        if is_replay:
            return cached

    user = get_current_user()
    allowed_wh = assigned_warehouses(user) if not is_warehouse_admin(user) else None

    from erpnext.selling.doctype.sales_order.sales_order import create_pick_list as erpnext_create_pick_list

    # Row-lock Sales Orders
    for so_name in sales_orders:
        frappe.db.sql("SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE", so_name)

    pick_list_doc = None
    for so_name in sales_orders:
        so = frappe.get_doc("Sales Order", so_name)
        if so.docstatus != 1:
            if request_id:
                clear_idempotency("create_pick_list_from_sales_orders", request_id)
            frappe.throw(
                frappe._("Sales Order {0} must be submitted to create a Pick List.").format(so_name),
                frappe.ValidationError,
            )
        pick_list_doc = erpnext_create_pick_list(so_name, target_doc=pick_list_doc)

    if not pick_list_doc or not pick_list_doc.get("locations"):
        if request_id:
            clear_idempotency("create_pick_list_from_sales_orders", request_id)
        frappe.throw(frappe._("No items available to pick from the selected Sales Orders."), frappe.ValidationError)

    if parent_warehouse:
        parent_warehouse = validate_string(parent_warehouse, "Parent Warehouse", max_len=140)
        pick_list_doc.parent_warehouse = parent_warehouse

    if wave_id:
        pick_list_doc.custom_wave_id = validate_string(wave_id, "Wave ID", max_len=140)
    if route_id:
        pick_list_doc.custom_route_id = validate_string(route_id, "Route ID", max_len=140)

    # Validate that every location warehouse is permitted
    if allowed_wh is not None:
        for loc in pick_list_doc.locations:
            if loc.warehouse and loc.warehouse not in allowed_wh:
                if request_id:
                    clear_idempotency("create_pick_list_from_sales_orders", request_id)
                frappe.throw(
                    frappe._("Pick location warehouse {0} is outside your assigned warehouses.").format(loc.warehouse),
                    frappe.PermissionError,
                )

    pick_list_doc.flags.ignore_permissions = True
    pick_list_doc.insert(ignore_permissions=True)

    res = {
        "name": pick_list_doc.name,
        "docstatus": pick_list_doc.docstatus,
        "status": pick_list_doc.status,
        "item_count": len(pick_list_doc.locations),
        "total_qty": sum(flt(loc.qty) for loc in pick_list_doc.locations),
        "custom_wave_id": pick_list_doc.get("custom_wave_id"),
        "custom_route_id": pick_list_doc.get("custom_route_id"),
    }

    record_security_audit_event(
        "Pick List Created",
        "Pick List",
        pick_list_doc.name,
        {"sales_orders": sales_orders, "wave_id": wave_id, "route_id": route_id, "total_qty": res["total_qty"]},
    )
    if request_id:
        save_idempotency_result(
            "create_pick_list_from_sales_orders",
            request_id,
            res,
            {"sales_orders": sorted(sales_orders), "parent_warehouse": parent_warehouse or "", "purpose": purpose},
        )
    return res


@frappe.whitelist(methods=["POST"])
def prepare_billing_from_delivery_note(delivery_note, request_id=None):
    """Prepare a draft Sales Invoice from a submitted Delivery Note.
    Warehouse managers can prepare draft billing, but cannot submit invoices or alter commercial pricing/tax terms.
    """
    check_rate_limit("prepare_billing_from_delivery_note", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    delivery_note = _task_name(delivery_note)

    if request_id:
        request_id = validate_string(request_id, "Request ID", max_len=140)
        cached, is_replay = validate_idempotency(
            "prepare_billing_from_delivery_note",
            request_id,
            {"delivery_note": delivery_note},
        )
        if is_replay:
            return cached

    frappe.db.sql("SELECT name FROM `tabDelivery Note` WHERE name = %s FOR UPDATE", delivery_note)
    dn = frappe.get_doc("Delivery Note", delivery_note)
    dn.check_permission("read")

    if dn.docstatus != 1:
        frappe.throw(
            frappe._("Delivery Note {0} must be submitted before preparing billing.").format(delivery_note),
            frappe.ValidationError,
        )

    # Check warehouse permissions
    from warehouse_erp.security import assigned_warehouses, is_warehouse_admin
    user = get_current_user()
    if not is_warehouse_admin(user):
        allowed = set(assigned_warehouses(user))
        for item in (dn.get("items") or []):
            if item.warehouse and item.warehouse not in allowed:
                frappe.throw(
                    frappe._("You do not have permission for warehouse {0}.").format(item.warehouse),
                    frappe.PermissionError,
                )

    # Check if existing invoice already prepared
    existing_inv = None
    if dn.get("custom_billing_invoice"):
        existing_inv = dn.custom_billing_invoice
    else:
        existing_draft = frappe.db.get_value(
            "Sales Invoice Item",
            {"delivery_note": delivery_note, "docstatus": 0},
            "parent",
        )
        if existing_draft:
            existing_inv = existing_draft

    if existing_inv and frappe.db.exists("Sales Invoice", existing_inv):
        res = {
            "sales_invoice": existing_inv,
            "delivery_note": delivery_note,
            "status": "Draft",
            "docstatus": 0,
            "already_prepared": True,
        }
        if request_id:
            save_idempotency_result("prepare_billing_from_delivery_note", request_id, res, {"delivery_note": delivery_note})
        return res

    from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
    inv = make_sales_invoice(delivery_note)
    inv.docstatus = 0
    inv.flags.ignore_permissions = True
    inv.insert(ignore_permissions=True)

    if frappe.db.has_column("Delivery Note", "custom_billing_invoice"):
        frappe.db.set_value(
            "Delivery Note",
            delivery_note,
            "custom_billing_invoice",
            inv.name,
            update_modified=False,
        )

    res = {
        "sales_invoice": inv.name,
        "delivery_note": delivery_note,
        "customer": inv.customer,
        "grand_total": flt(inv.grand_total),
        "status": "Draft",
        "docstatus": 0,
        "already_prepared": False,
    }

    record_security_audit_event(
        "Draft Billing Prepared",
        "Delivery Note",
        delivery_note,
        {"sales_invoice": inv.name, "customer": inv.customer, "grand_total": flt(inv.grand_total)},
    )
    if request_id:
        save_idempotency_result("prepare_billing_from_delivery_note", request_id, res, {"delivery_note": delivery_note})
    return res


@frappe.whitelist()
def get_ewaybill_readiness(delivery_note):
    """Evaluate whether Delivery Note has all mandatory transport fields for India Compliance e-Waybill."""
    require_role(FULFILLMENT_ROLES)
    delivery_note = _task_name(delivery_note)
    dn = frappe.get_doc("Delivery Note", delivery_note)
    dn.check_permission("read")

    missing = []
    if not (dn.get("transporter_name") or dn.get("transporter") or dn.get("gst_transporter_id")):
        missing.append("Transporter / Transporter ID")
    if not dn.get("mode_of_transport"):
        missing.append("Mode of Transport")
    if dn.get("mode_of_transport") == "Road" and not dn.get("vehicle_no") and not dn.get("lr_no"):
        missing.append("Vehicle Number or LR Number")
    if flt(dn.get("distance")) <= 0:
        missing.append("Transport Distance (Km)")

    threshold = 50000.0
    exceeds_threshold = flt(dn.grand_total) >= threshold

    return {
        "delivery_note": dn.name,
        "docstatus": dn.docstatus,
        "grand_total": flt(dn.grand_total),
        "ewaybill_applicable": exceeds_threshold,
        "ready_for_ewaybill": len(missing) == 0,
        "missing_fields": missing,
        "existing_ewaybill": dn.get("ewaybill"),
        "transporter_name": dn.get("transporter_name"),
        "vehicle_no": dn.get("vehicle_no"),
        "lr_no": dn.get("lr_no"),
        "lr_date": str(dn.get("lr_date")) if dn.get("lr_date") else None,
        "mode_of_transport": dn.get("mode_of_transport"),
        "distance": flt(dn.get("distance")),
    }


@frappe.whitelist(methods=["POST"])
def update_transport_metadata(
    delivery_note,
    transporter_name=None,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
    mode_of_transport=None,
    distance=None,
    driver_name=None,
):
    """Update carrier transport fields for e-Waybill readiness."""
    check_rate_limit("update_transport_metadata", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    delivery_note = _task_name(delivery_note)

    frappe.db.sql("SELECT name FROM `tabDelivery Note` WHERE name = %s FOR UPDATE", delivery_note)
    dn = frappe.get_doc("Delivery Note", delivery_note)
    dn.check_permission("write")

    if transporter_name:
        dn.transporter_name = validate_string(transporter_name, "Transporter Name", max_len=140)
    if vehicle_no:
        dn.vehicle_no = validate_string(vehicle_no, "Vehicle Number", max_len=140)
    if lr_no:
        dn.lr_no = validate_string(lr_no, "LR Number", max_len=140)
    if lr_date:
        dn.lr_date = lr_date
    if mode_of_transport:
        dn.mode_of_transport = validate_string(mode_of_transport, "Mode of Transport", allowed_values={"Road", "Rail", "Air", "Ship"})
    if distance is not None:
        dn.distance = validate_float(distance, "Distance", min_val=0.0)
    if driver_name:
        dn.driver_name = validate_string(driver_name, "Driver Name", max_len=140)

    dn.flags.ignore_permissions = True
    dn.save(ignore_permissions=True)

    record_security_audit_event(
        "Transport Metadata Updated",
        "Delivery Note",
        dn.name,
        {
            "transporter_name": dn.transporter_name,
            "vehicle_no": dn.vehicle_no,
            "lr_no": dn.lr_no,
            "mode_of_transport": dn.mode_of_transport,
            "distance": dn.distance,
        },
    )
    return get_ewaybill_readiness(delivery_note)


@frappe.whitelist()
def get_warehouse_work_queues(warehouse=None, queue_type="wave"):
    """Return wave or route work queues scoped to the manager's assigned warehouses."""
    require_role(FULFILLMENT_ROLES)
    queue_type = validate_string(queue_type, "Queue Type", allowed_values={"wave", "route"})
    user = get_current_user()
    allowed_wh = assigned_warehouses(user) if not is_warehouse_admin(user) else None

    if allowed_wh is not None and not allowed_wh:
        return {"queue_type": queue_type, "queues": []}

    if warehouse:
        warehouse = validate_string(warehouse, "Warehouse", max_len=140)
        if allowed_wh is not None and warehouse not in allowed_wh:
            frappe.throw(frappe._("You do not have access to warehouse {0}.").format(warehouse), frappe.PermissionError)
        warehouses = [warehouse]
    else:
        warehouses = allowed_wh

    if queue_type == "wave":
        conditions = ["pl.docstatus IN (0, 1)"]
        params = []
        if warehouses:
            wh_cond = f"pli.warehouse IN ({', '.join(['%s']*len(warehouses))})"
            conditions.append(f"EXISTS (SELECT 1 FROM `tabPick List Item` pli WHERE pli.parent = pl.name AND {wh_cond})")
            params.extend(warehouses)

        rows = frappe.db.sql(
            f"""
            SELECT COALESCE(pl.custom_wave_id, 'Unassigned Wave') AS queue_id,
                   COUNT(DISTINCT pl.name) AS task_count,
                   SUM(pli.stock_qty) AS total_qty,
                   SUM(pli.picked_qty) AS picked_qty,
                   MIN(pl.creation) AS earliest_creation
            FROM `tabPick List` pl
            JOIN `tabPick List Item` pli ON pli.parent = pl.name
            WHERE {' AND '.join(conditions)}
            GROUP BY queue_id
            ORDER BY queue_id ASC
            """,
            params,
            as_dict=True,
        )
        queues = []
        for r in rows:
            tot = flt(r.total_qty)
            picked = flt(r.picked_qty)
            pct = round((picked / tot * 100), 1) if tot > 0 else 0.0
            queues.append({
                "queue_id": r.queue_id,
                "task_count": cint(r.task_count),
                "total_qty": tot,
                "picked_qty": picked,
                "progress_percent": pct,
                "status": "Completed" if picked >= tot and tot > 0 else ("In Progress" if picked > 0 else "Pending"),
            })
        return {"queue_type": "wave", "queues": queues}

    else:
        conditions = ["dn.docstatus IN (0, 1)"]
        params = []
        if warehouses:
            wh_cond = f"dni.warehouse IN ({', '.join(['%s']*len(warehouses))})"
            conditions.append(f"EXISTS (SELECT 1 FROM `tabDelivery Note Item` dni WHERE dni.parent = dn.name AND {wh_cond})")
            params.extend(warehouses)

        rows = frappe.db.sql(
            f"""
            SELECT COALESCE(dn.custom_route_id, 'Unassigned Route') AS queue_id,
                   COUNT(DISTINCT dn.name) AS task_count,
                   COUNT(DISTINCT dn.customer) AS customer_count,
                   SUM(dni.qty) AS total_qty,
                   SUM(CASE WHEN dn.docstatus = 1 THEN 1 ELSE 0 END) AS dispatched_count
            FROM `tabDelivery Note` dn
            JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
            WHERE {' AND '.join(conditions)}
            GROUP BY queue_id
            ORDER BY queue_id ASC
            """,
            params,
            as_dict=True,
        )
        queues = []
        for r in rows:
            queues.append({
                "queue_id": r.queue_id,
                "task_count": cint(r.task_count),
                "customer_count": cint(r.customer_count),
                "total_qty": flt(r.total_qty),
                "dispatched_count": cint(r.dispatched_count),
            })
        return {"queue_type": "route", "queues": queues}


@frappe.whitelist(methods=["POST"])
def assign_to_wave(pick_lists, wave_id):
    """Assign multiple Pick Lists to a picking wave."""
    check_rate_limit("assign_to_wave", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    wave_id = validate_string(wave_id, "Wave ID", max_len=140, required=True)
    pick_lists = validate_bounded_list(pick_lists, "Pick Lists", max_len=100)

    updated = []
    for pl_name in pick_lists:
        pl_name = _task_name(pl_name)
        frappe.db.sql("SELECT name FROM `tabPick List` WHERE name = %s FOR UPDATE", pl_name)
        pl = frappe.get_doc("Pick List", pl_name)
        pl.check_permission("write")
        pl.custom_wave_id = wave_id
        if getattr(pl, "flags", None) is None:
            pl.flags = frappe._dict()
        pl.flags.ignore_permissions = True
        pl.save(ignore_permissions=True)
        updated.append(pl_name)

    record_security_audit_event("Wave Assigned", "Pick List", wave_id, {"pick_lists": updated})
    return {"wave_id": wave_id, "updated": updated, "count": len(updated)}


@frappe.whitelist(methods=["POST"])
def assign_to_route(delivery_notes, route_id):
    """Assign multiple Delivery Notes to a delivery route."""
    check_rate_limit("assign_to_route", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    route_id = validate_string(route_id, "Route ID", max_len=140, required=True)
    delivery_notes = validate_bounded_list(delivery_notes, "Delivery Notes", max_len=100)

    updated = []
    for dn_name in delivery_notes:
        dn_name = _task_name(dn_name)
        frappe.db.sql("SELECT name FROM `tabDelivery Note` WHERE name = %s FOR UPDATE", dn_name)
        dn = frappe.get_doc("Delivery Note", dn_name)
        dn.check_permission("write")
        dn.custom_route_id = route_id
        if getattr(dn, "flags", None) is None:
            dn.flags = frappe._dict()
        dn.flags.ignore_permissions = True
        dn.save(ignore_permissions=True)
        updated.append(dn_name)

    record_security_audit_event("Route Assigned", "Delivery Note", route_id, {"delivery_notes": updated})
    return {"route_id": route_id, "updated": updated, "count": len(updated)}


@frappe.whitelist(methods=["POST"])
def preflight_fulfillment_bulk_action(action, docnames):
    """Preflight validation for bulk operations (max 50 documents).
    Checks locks, states, warehouse permissions, and package readiness without altering state.
    """
    require_role(FULFILLMENT_ROLES)
    action = validate_string(action, "Action", allowed_values={"create_delivery_notes", "dispatch_deliveries", "prepare_billing"})
    docnames = validate_bounded_list(docnames, "Documents", max_len=50, min_len=1)

    items = []
    valid_count = 0
    invalid_count = 0

    user = get_current_user()
    allowed_wh = set(assigned_warehouses(user)) if not is_warehouse_admin(user) else None

    for name in docnames:
        name = str(name).strip()
        errors = []
        if action == "create_delivery_notes":
            if not frappe.db.exists("Pick List", name):
                errors.append(f"Pick List {name} does not exist")
            else:
                pl = frappe.get_doc("Pick List", name)
                if pl.docstatus != 1:
                    errors.append(f"Pick List {name} is not submitted (docstatus={pl.docstatus})")
                if allowed_wh is not None:
                    for loc in pl.locations:
                        if loc.warehouse and loc.warehouse not in allowed_wh:
                            errors.append(f"Location warehouse {loc.warehouse} is outside permitted warehouses")
                            break
        elif action == "dispatch_deliveries":
            if not frappe.db.exists("Delivery Note", name):
                errors.append(f"Delivery Note {name} does not exist")
            else:
                dn = frappe.get_doc("Delivery Note", name)
                if dn.docstatus != 0:
                    errors.append(f"Delivery Note {name} is not draft (docstatus={dn.docstatus})")
                if allowed_wh is not None:
                    for item in (dn.get("items") or []):
                        wh = item.get("warehouse")
                        if wh and wh not in allowed_wh:
                            errors.append(f"Item warehouse {wh} is outside permitted warehouses")
                            break
        elif action == "prepare_billing":
            if not frappe.db.exists("Delivery Note", name):
                errors.append(f"Delivery Note {name} does not exist")
            else:
                dn = frappe.get_doc("Delivery Note", name)
                if dn.docstatus != 1:
                    errors.append(f"Delivery Note {name} is not submitted (docstatus={dn.docstatus})")
                if dn.get("custom_billing_invoice"):
                    errors.append(f"Delivery Note {name} already has billing invoice {dn.custom_billing_invoice}")

        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        items.append({
            "name": name,
            "valid": is_valid,
            "errors": errors,
        })

    return {
        "action": action,
        "total": len(docnames),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "can_proceed": invalid_count == 0,
        "items": items,
    }


@frappe.whitelist()
def get_order_fulfillment_status(sales_order):
    """Return fulfillment, delivered, and backorder status for a Sales Order."""
    require_role(FULFILLMENT_ROLES)
    sales_order = _task_name(sales_order)
    so = frappe.get_doc("Sales Order", sales_order)
    so.check_permission("read")

    lines = []
    total_ordered = 0.0
    total_delivered = 0.0

    for item in (so.get("items") or []):
        ordered = flt(item.get("qty"))
        delivered = flt(item.get("delivered_qty"))
        pending = max(0.0, ordered - delivered)
        total_ordered += ordered
        total_delivered += delivered
        lines.append({
            "item_code": item.get("item_code"),
            "item_name": item.get("item_name"),
            "ordered_qty": ordered,
            "delivered_qty": delivered,
            "pending_qty": pending,
            "backorder_needed": pending > 0,
            "warehouse": item.get("warehouse"),
        })

    if total_delivered == 0:
        fulfillment_status = "Unfulfilled"
    elif total_delivered >= total_ordered:
        fulfillment_status = "Fully Fulfilled"
    else:
        fulfillment_status = "Partially Fulfilled"

    return {
        "sales_order": so.name,
        "customer": so.get("customer"),
        "customer_name": so.get("customer_name"),
        "delivery_date": str(so.get("delivery_date") or ""),
        "total_ordered": total_ordered,
        "total_delivered": total_delivered,
        "total_pending": max(0.0, total_ordered - total_delivered),
        "is_backorder": any(line["backorder_needed"] for line in lines),
        "fulfillment_status": fulfillment_status,
        "lines": lines,
    }


@frappe.whitelist(methods=["POST"])
def record_delivery_handoff(
    delivery_note,
    transporter_name,
    accepted_by_handler,
    packages_count=1,
    gross_weight=0.0,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
    driver_name=None,
    driver_phone=None,
    proof_photo=None,
    notes=None,
    request_id=None,
):
    """Record an immutable Delivery Handoff capturing physical custody transfer to carrier."""
    check_rate_limit("record_delivery_handoff", limit=60, window_seconds=60)
    require_role(FULFILLMENT_ROLES)
    delivery_note = _task_name(delivery_note)

    if request_id:
        request_id = validate_string(request_id, "Request ID", max_len=140)
        cached, is_replay = validate_idempotency(
            "record_delivery_handoff",
            request_id,
            {"delivery_note": delivery_note, "transporter_name": transporter_name, "accepted_by_handler": accepted_by_handler},
        )
        if is_replay:
            return cached

    frappe.db.sql("SELECT name FROM `tabDelivery Note` WHERE name = %s FOR UPDATE", delivery_note)
    existing_handoff = frappe.db.get_value("Delivery Handoff", {"delivery_note": delivery_note}, "name")
    if existing_handoff:
        if request_id:
            clear_idempotency("record_delivery_handoff", request_id)
        frappe.throw(
            frappe._("Delivery Note {0} has already been handed over (Record: {1}).").format(
                delivery_note, existing_handoff
            ),
            frappe.ValidationError,
        )

    handoff = frappe.get_doc({
        "doctype": "Delivery Handoff",
        "delivery_note": delivery_note,
        "transporter_name": transporter_name,
        "accepted_by_handler": accepted_by_handler,
        "packages_count": cint(packages_count) or 1,
        "gross_weight": flt(gross_weight),
        "vehicle_no": vehicle_no,
        "lr_no": lr_no,
        "lr_date": lr_date,
        "driver_name": driver_name,
        "driver_phone": driver_phone,
        "proof_photo": proof_photo,
        "notes": notes,
    })
    handoff.flags.ignore_permissions = True
    handoff.insert(ignore_permissions=True)

    res = {
        "name": handoff.name,
        "delivery_note": handoff.delivery_note,
        "customer": handoff.customer,
        "transporter_name": handoff.transporter_name,
        "accepted_by_handler": handoff.accepted_by_handler,
        "handed_over_by": handoff.handed_over_by,
        "handed_over_on": str(handoff.handed_over_on),
        "packages_count": handoff.packages_count,
        "gross_weight": handoff.gross_weight,
    }

    if request_id:
        save_idempotency_result(
            "record_delivery_handoff",
            request_id,
            res,
            {"delivery_note": delivery_note, "transporter_name": transporter_name, "accepted_by_handler": accepted_by_handler},
        )
    return res


@frappe.whitelist()
def get_task_manifest(task_type, name):
    """Return an authorized printable manifest projection for Pick List or Delivery Note."""
    require_role(FULFILLMENT_ROLES)
    task_type, doctype = _task_type(task_type)
    name = _task_name(name)
    document = frappe.get_doc(doctype, name)
    document.check_permission("read")

    from warehouse_erp.security import assigned_warehouses, is_warehouse_admin

    user = frappe.session.user
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        child_rows = document.locations if task_type == "pick" else document.items
        for row in child_rows:
            wh = row.get("warehouse")
            if wh and wh not in allowed:
                frappe.throw(
                    frappe._("You do not have permission for warehouse {0}.").format(wh),
                    frappe.PermissionError,
                )

    items = []
    total_qty = 0.0
    child_rows = document.locations if task_type == "pick" else document.items
    for row in child_rows:
        qty = flt(row.get("stock_qty") or row.get("qty"))
        total_qty += qty
        items.append({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "warehouse": row.warehouse,
            "qty": qty,
            "uom": row.stock_uom,
            "batch_no": row.get("batch_no"),
            "serial_no": row.get("serial_no"),
        })

    packing_slips = []
    total_packages = 1
    total_gross_weight = 0.0
    if task_type == "delivery":
        ps_records = frappe.get_all(
            "Packing Slip",
            filters={"delivery_note": document.name, "docstatus": ["<", 2]},
            fields=["name", "from_case_no", "to_case_no", "gross_weight_pkg", "net_weight_pkg"],
            order_by="from_case_no asc",
        )
        for ps in ps_records:
            total_packages = max(total_packages, cint(ps.to_case_no))
            total_gross_weight += flt(ps.gross_weight_pkg)
            packing_slips.append(ps)

    return {
        "name": document.name,
        "doctype": doctype,
        "task_type": task_type,
        "customer": document.get("customer"),
        "customer_name": document.get("customer_name"),
        "company": document.company,
        "posting_date": str(document.get("posting_date") or document.get("transaction_date") or ""),
        "status": document.status,
        "docstatus": document.docstatus,
        "items": items,
        "total_items": len(items),
        "total_qty": total_qty,
        "total_packages": total_packages,
        "total_gross_weight": total_gross_weight,
        "packing_slips": packing_slips,
        "transporter_name": document.get("transporter_name"),
        "vehicle_no": document.get("vehicle_no"),
        "lr_no": document.get("lr_no"),
        "lr_date": str(document.get("lr_date")) if document.get("lr_date") else None,
    }
