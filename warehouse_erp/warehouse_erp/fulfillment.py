"""Permission-aware Clothing ERP views over native fulfillment documents."""

from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint, escape_html, flt

from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)
from warehouse_erp.security import is_warehouse_manager, require_role

FULFILLMENT_ROLES = {
    ROLE_WAREHOUSE_OPERATOR,
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
    child_rows = document.locations if task_type == "pick" else document.items
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
            fields=["name", "from_case_no", "to_case_no", "gross_weight_pkg", "docstatus"],
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
    bundle_names = [
        row.serial_and_batch_bundle
        for row in getattr(document, "locations", [])
        if row.get("serial_and_batch_bundle")
    ]
    if bundle_names:
        escaped = ", ".join(frappe.db.escape(b) for b in set(bundle_names))
        frappe.db.sql(
            f"SELECT name FROM `tabSerial and Batch Bundle` WHERE name IN ({escaped}) FOR UPDATE"
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
def verify_pick_item(pick_list, location, barcode, quantity=1):
    """Increment native picked quantity after exact row and barcode verification."""
    require_role(FULFILLMENT_ROLES)
    pick_list = _task_name(pick_list)
    quantity = _scan_quantity(quantity)
    document = frappe.get_doc("Pick List", pick_list)
    document.check_permission("read")
    if document.docstatus != 0:
        frappe.throw(frappe._("Only a draft Pick List can be verified."))
    row = _pick_location(document, location)
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
    document.save(ignore_permissions=True)
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
    require_role(FULFILLMENT_ROLES)
    pick_list = _task_name(pick_list)
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
    document.save(ignore_permissions=True)
    frappe.db.commit()

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
    finally:
        if previous_bundle_context is None:
            frappe.flags.pop("clothing_pick_bundle", None)
        else:
            frappe.flags.clothing_pick_bundle = previous_bundle_context

    _close_pick_assignments(document.name)
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

    result = create_delivery_note(pick_list)
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
):
    """Create and save a native Packing Slip for an unpacked draft Delivery Note."""
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

    packing_slip.flags.ignore_permissions = True
    packing_slip.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "packing_slip": packing_slip.name,
        "delivery_note": document.name,
        "from_case_no": packing_slip.from_case_no,
        "to_case_no": packing_slip.to_case_no,
        "gross_weight_pkg": packing_slip.gross_weight_pkg,
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
    require_role(SHORTAGE_RESOLUTION_ROLES)
    delivery_note = _task_name(delivery_note)
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
        document.transporter_name = str(transporter_name).strip()[:140]
    if vehicle_no:
        document.vehicle_no = str(vehicle_no).strip()[:140]
    if lr_no:
        document.lr_no = str(lr_no).strip()[:140]
    if lr_date:
        from frappe.utils import getdate
        document.lr_date = getdate(lr_date)

    document.flags.ignore_permissions = True
    document.submit()
    frappe.db.commit()

    return {
        "delivery_note": document.name,
        "docstatus": document.docstatus,
        "status": document.status,
    }


@frappe.whitelist(methods=["POST"])
def bulk_create_delivery_notes_from_picks(pick_lists):
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

    results = []
    succeeded = 0
    failed = 0

    for name in pick_lists:
        task_name = str(name).strip()
        try:
            res = create_delivery_note_from_pick(task_name)
            results.append({
                "pick_list": task_name,
                "success": True,
                "delivery_note": res.get("delivery_note"),
                "customer": res.get("customer"),
            })
            succeeded += 1
        except Exception as e:
            results.append({
                "pick_list": task_name,
                "success": False,
                "error": str(getattr(e, "message", None) or e),
            })
            failed += 1

    return {
        "total": len(pick_lists),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@frappe.whitelist(methods=["POST"])
def bulk_dispatch_delivery_notes(
    delivery_notes,
    transporter_name=None,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
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

    results = []
    succeeded = 0
    failed = 0

    for name in delivery_notes:
        dn_name = str(name).strip()
        try:
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
            results.append({
                "delivery_note": dn_name,
                "success": False,
                "error": str(getattr(e, "message", None) or e),
            })
            failed += 1

    return {
        "total": len(delivery_notes),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


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
        qty = flt(row.get("stock_qty") or row.get("qty"), 2)
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
