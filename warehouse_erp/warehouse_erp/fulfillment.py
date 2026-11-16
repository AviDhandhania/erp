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
    rows = []
    for row in child_rows[:200]:
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
            }
        )
    workflow_name = (
        _active_pick_list_workflow()
        if task_type == "pick" and document.docstatus == 0
        else None
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
            and is_warehouse_manager()
        ),
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
        if row.get("serial_and_batch_bundle"):
            frappe.throw(
                frappe._(
                    "This serialized row already uses a native Serial and Batch Bundle; "
                    "incremental scanning cannot safely rewrite that allocation."
                )
            )
        if not scan.get("serial_no"):
            frappe.throw(frappe._("Scan a Serial No for this serialized item."))
        if quantity != 1:
            frappe.throw(frappe._("Serialized items must be scanned one at a time."))
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

    if apply and not row.get("serial_and_batch_bundle"):
        if scan.get("serial_no"):
            serials = (
                _serial_numbers(row.get("serial_no"))
                if flt(row.get("picked_qty")) > 0
                else []
            )
            serials.append(scan.serial_no)
            row.serial_no = "\n".join(serials)
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
