"""Permission-aware Clothing ERP views over native fulfillment documents."""

import frappe
from frappe.utils import cint

from clothing_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)
from clothing_erp.security import require_role

FULFILLMENT_ROLES = {
    ROLE_WAREHOUSE_OPERATOR,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_BUSINESS_ADMIN,
}
TASK_TYPES = {"pick": "Pick List", "delivery": "Delivery Note"}
TASK_STATES = {"all", "draft", "submitted", "cancelled"}
MAX_TASK_PAGE_SIZE = 50


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
                "picked_qty": row.get("picked_qty"),
                "stock_uom": row.stock_uom,
                "batch_no": row.get("batch_no"),
                "serial_no": row.get("serial_no"),
                "sales_order": row.get("sales_order") or row.get("against_sales_order"),
            }
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
    }
