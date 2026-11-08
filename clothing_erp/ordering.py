"""Create native draft Sales Orders from a validated clothing catalogue selection."""

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import getdate, nowdate

from clothing_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from clothing_erp.security import get_current_user, has_retailer_access, require_role

ORDER_ROLES = {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}
MAX_ORDER_LINES = 100
MAX_LINE_QUANTITY = 100_000


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
