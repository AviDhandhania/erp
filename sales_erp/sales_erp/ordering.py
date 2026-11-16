"""Create native draft Sales Orders from a validated clothing catalogue selection."""

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint, getdate, nowdate

from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from sales_erp.security import (
    assigned_documents,
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)

ORDER_ROLES = {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}
ORDER_REVIEW_ROLES = {ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}
MAX_ORDER_LINES = 100
MAX_LINE_QUANTITY = 100_000
MAX_ORDER_PAGE_SIZE = 50
ORDER_LIST_STATES = {"all", "draft", "submitted", "cancelled"}


def _request_id(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", value):
        frappe.throw(frappe._("The order request ID is invalid."))
    return value


def _items(value):
    value = frappe.parse_json(value) if isinstance(value, str) else value
    if not isinstance(value, list) or not value or len(value) > MAX_ORDER_LINES:
        frappe.throw(
            frappe._("Select between 1 and {0} item sizes.").format(MAX_ORDER_LINES)
        )
    quantities = defaultdict(int)
    for row in value:
        if not isinstance(row, dict):
            frappe.throw(frappe._("The order selection is invalid."))
        item_code = row.get("item_code")
        if (
            not isinstance(item_code, str)
            or not item_code.strip()
            or len(item_code.strip()) > 140
        ):
            frappe.throw(frappe._("Every order row requires an item code."))
        item_code = item_code.strip()
        try:
            quantity = Decimal(str(row.get("qty")))
        except InvalidOperation, ValueError:
            frappe.throw(frappe._("Quantities must be positive whole numbers."))
        if (
            not quantity.is_finite()
            or quantity != quantity.to_integral_value()
            or quantity <= 0
        ):
            frappe.throw(frappe._("Quantities must be positive whole numbers."))
        quantities[item_code] += int(quantity)
        if quantities[item_code] > MAX_LINE_QUANTITY:
            frappe.throw(
                frappe._("Quantity for {0} exceeds the per-size limit.").format(
                    item_code
                )
            )
    return [
        {"item_code": item_code, "qty": quantity}
        for item_code, quantity in sorted(quantities.items())
    ]


def _validate_customer(customer):
    if (
        not isinstance(customer, str)
        or not customer.strip()
        or len(customer.strip()) > 140
    ):
        frappe.throw(
            frappe._("The selected retailer is invalid."),
            frappe.PermissionError,
        )
    customer = customer.strip()
    if not customer or not has_retailer_access(customer):
        frappe.throw(
            frappe._("You do not have access to this retailer."),
            frappe.PermissionError,
        )
    disabled = frappe.db.get_value("Customer", customer, "disabled")
    if disabled is None:
        frappe.throw(frappe._("The selected retailer does not exist."))
    if disabled:
        frappe.throw(frappe._("The selected retailer is disabled."))
    return customer


def _validate_company():
    company = frappe.defaults.get_user_default(
        "Company"
    ) or frappe.defaults.get_global_default("company")
    if not company:
        frappe.throw(frappe._("Configure a default Company before creating an order."))
    permitted = frappe.get_list(
        "Company", filters={"name": company}, pluck="name", limit=1
    )
    if not permitted:
        frappe.throw(
            frappe._("You do not have access to the configured Company."),
            frappe.PermissionError,
        )
    return company


def _validate_catalogue_items(item_codes):
    rows = frappe.get_list(
        "Item",
        filters={
            "name": ["in", item_codes],
            "disabled": 0,
            "is_sales_item": 1,
        },
        fields=["name", "variant_of", "stock_uom"],
        limit=len(item_codes),
    )
    permitted = {row.name: row for row in rows if row.variant_of}
    if set(permitted) != set(item_codes):
        frappe.throw(
            frappe._(
                "One or more selected item sizes are unavailable or unauthorized."
            ),
            frappe.PermissionError,
        )
    attributes = frappe.get_all(
        "Item Variant Attribute",
        filters={"parent": ["in", item_codes], "parenttype": "Item"},
        fields=["parent", "attribute"],
    )
    by_item = defaultdict(set)
    for row in attributes:
        by_item[row.parent].add(row.attribute)
    if any(by_item[item_code] != {"Size"} for item_code in item_codes):
        frappe.throw(
            frappe._("Clothing orders accept variants whose only attribute is Size.")
        )


def _existing_order(request_id, customer):
    existing = frappe.db.get_value(
        "Sales Order",
        {"custom_clothing_request_id": request_id},
        ["name", "owner", "customer", "docstatus", "status", "currency", "grand_total"],
        as_dict=True,
    )
    if not existing:
        return None
    if existing.owner != get_current_user() or existing.customer != customer:
        frappe.throw(
            frappe._("That order request ID has already been used."),
            frappe.PermissionError,
        )
    return existing


def _result(order, replay=False):
    return {
        "name": order.name,
        "customer": order.customer,
        "docstatus": order.docstatus,
        "status": order.status,
        "currency": order.currency,
        "grand_total": order.grand_total,
        "idempotent_replay": replay,
    }


def _order_customer_scope():
    """Return explicit retailer names, or None for a trusted clothing administrator."""
    if is_clothing_admin():
        return None
    if ROLE_SALES_MANAGER in get_user_roles():
        territories = assigned_documents("Territory")
        if not territories:
            return []
        return frappe.get_all(
            "Customer",
            filters={"disabled": 0, "territory": ["in", territories]},
            pluck="name",
        )
    return assigned_documents("Customer")


def _order_scope_filters(customers):
    filters = {"custom_clothing_request_id": ["is", "set"]}
    if customers is not None:
        if not customers:
            return None
        filters["customer"] = ["in", customers]
    return filters


def _validate_order_access(name):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 140:
        frappe.throw(frappe._("The selected order is invalid."), frappe.PermissionError)
    name = name.strip()
    customers = _order_customer_scope()
    filters = {
        "name": name,
        "custom_clothing_request_id": ["is", "set"],
    }
    if customers is not None:
        if not customers:
            frappe.throw(
                frappe._("You do not have access to this order."),
                frappe.PermissionError,
            )
        filters["customer"] = ["in", customers]
    order = frappe.db.get_value(
        "Sales Order",
        filters,
        [
            "name",
            "customer",
            "customer_name",
            "company",
            "owner",
            "creation",
            "transaction_date",
            "delivery_date",
            "selling_price_list",
            "currency",
            "net_total",
            "total_taxes_and_charges",
            "grand_total",
            "rounded_total",
            "total_qty",
            "docstatus",
            "status",
            "custom_clothing_request_id",
        ],
        as_dict=True,
    )
    if not order:
        frappe.throw(
            frappe._("The Clothing ERP order is unavailable or unauthorized."),
            frappe.PermissionError,
        )
    return order


@frappe.whitelist()
def get_clothing_orders(search=None, state="all", page=1, page_size=20):
    """List catalogue-created orders with an explicit retailer scope."""
    require_role(ORDER_ROLES)
    search = str(search or "").strip()[:80]
    state = str(state or "all").strip().lower()
    if state not in ORDER_LIST_STATES:
        frappe.throw(frappe._("The order status filter is invalid."))
    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), MAX_ORDER_PAGE_SIZE)
    filters = _order_scope_filters(_order_customer_scope())
    if filters is None:
        return {
            "orders": [],
            "pagination": {"page": page, "page_size": page_size, "has_more": False},
        }
    if state == "draft":
        filters["docstatus"] = 0
    elif state == "submitted":
        filters["docstatus"] = 1
    elif state == "cancelled":
        filters["docstatus"] = 2
    query = {
        "doctype": "Sales Order",
        "filters": filters,
        "fields": [
            "name",
            "customer",
            "customer_name",
            "transaction_date",
            "delivery_date",
            "total_qty",
            "currency",
            "grand_total",
            "docstatus",
            "status",
        ],
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
    # Sales roles deliberately have no native Sales Order permission. This app-owned
    # endpoint uses the retailer/territory scope above before performing the query.
    rows = frappe.get_all(**query)
    return {
        "orders": rows[:page_size],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) > page_size,
        },
    }


@frappe.whitelist()
def get_clothing_order(name):
    """Return a safe detail projection for one authorized catalogue-created order."""
    require_role(ORDER_ROLES)
    order = _validate_order_access(name)
    items = frappe.get_all(
        "Sales Order Item",
        filters={"parent": order.name, "parenttype": "Sales Order"},
        fields=[
            "item_code",
            "item_name",
            "qty",
            "stock_uom",
            "rate",
            "amount",
            "delivery_date",
        ],
        order_by="idx asc",
    )
    result = dict(order)
    result.pop("custom_clothing_request_id", None)
    result["items"] = items
    workflow_name = _active_sales_order_workflow()
    result["review"] = {
        "can_submit": bool(
            is_sales_manager() and order.docstatus == 0 and not workflow_name
        ),
        "can_cancel": bool(
            is_sales_manager() and order.docstatus == 1 and not workflow_name
        ),
        "can_edit": bool(is_clothing_admin() and order.docstatus == 0),
        "workflow": workflow_name,
    }
    return result


def _active_sales_order_workflow():
    from frappe.model.workflow import get_workflow_name

    return get_workflow_name("Sales Order")


@frappe.whitelist(methods=["POST"])
def submit_clothing_order(name):
    """Submit one authorized draft through ERPNext's native Sales Order controller."""
    require_role(ORDER_REVIEW_ROLES)
    order = _validate_order_access(name)
    if order.docstatus != 0:
        frappe.throw(frappe._("Only a draft Clothing ERP order can be submitted."))
    if workflow_name := _active_sales_order_workflow():
        frappe.throw(
            frappe._(
                "Sales Order Workflow {0} is active. Complete its configured approval "
                "actions before submission; Clothing ERP will not bypass the workflow."
            ).format(workflow_name)
        )

    # Serialize review against another submit/cancel request, then repeat every access
    # and lifecycle check after acquiring the row lock.
    frappe.db.sql(
        "select name from `tabSales Order` where name = %s for update", order.name
    )
    order = _validate_order_access(order.name)
    if order.docstatus != 0:
        frappe.throw(frappe._("This order changed while it was being reviewed. Refresh."))

    document = frappe.get_doc("Sales Order", order.name)
    document.flags.ignore_permissions = True
    # Native submit owns credit-limit, authorization, commission, stock-reservation,
    # taxes, linked-document and status behavior on the pinned ERPNext release.
    document.submit()
    return _result(document)


@frappe.whitelist(methods=["POST"])
def cancel_clothing_order(name):
    """Cancel one authorized submitted order through ERPNext's native controller."""
    require_role(ORDER_REVIEW_ROLES)
    order = _validate_order_access(name)
    if order.docstatus != 1:
        frappe.throw(frappe._("Only a submitted Clothing ERP order can be cancelled."))
    if workflow_name := _active_sales_order_workflow():
        frappe.throw(
            frappe._(
                "Sales Order Workflow {0} is active. Complete its configured cancellation "
                "actions; Clothing ERP will not bypass the workflow."
            ).format(workflow_name)
        )

    frappe.db.sql(
        "select name from `tabSales Order` where name = %s for update", order.name
    )
    order = _validate_order_access(order.name)
    if order.docstatus != 1:
        frappe.throw(frappe._("This order changed while it was being reviewed. Refresh."))

    document = frappe.get_doc("Sales Order", order.name)
    document.flags.ignore_permissions = True
    # Native cancellation owns linked-document checks, reserved-quantity and stock
    # reservation cleanup, previous-document updates and final status behavior.
    document.cancel()
    return _result(document)


@frappe.whitelist(methods=["POST"])
def create_draft_sales_order(customer, items, request_id, delivery_date=None):
    """Create a standard ERPNext draft; submission remains a separate native workflow."""
    require_role(ORDER_ROLES)
    customer = _validate_customer(customer)
    request_id = _request_id(request_id)
    if existing := _existing_order(request_id, customer):
        return _result(existing, replay=True)
    rows = _items(items)
    _validate_catalogue_items([row["item_code"] for row in rows])
    try:
        delivery_date = getdate(delivery_date or nowdate())
    except TypeError, ValueError:
        frappe.throw(frappe._("Delivery Date is invalid."))
    if delivery_date < getdate(nowdate()):
        frappe.throw(frappe._("Delivery Date cannot be in the past."))
    company = _validate_company()
    order = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "customer": customer,
            "company": company,
            "transaction_date": nowdate(),
            "delivery_date": delivery_date,
            "order_type": "Sales",
            "custom_clothing_request_id": request_id,
            "items": [
                {
                    "item_code": row["item_code"],
                    "qty": row["qty"],
                    "delivery_date": delivery_date,
                }
                for row in rows
            ],
        }
    )
    try:
        order.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        if existing := _existing_order(request_id, customer):
            return _result(existing, replay=True)
        raise
    return _result(order)
