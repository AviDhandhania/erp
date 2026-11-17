"""Create native draft Sales Orders from a validated clothing catalogue selection."""

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from sales_erp.api_security import (
    check_rate_limit,
    clear_idempotency,
    record_security_audit_event,
    save_idempotency_result,
    validate_idempotency,
)
from sales_erp.security import (
    assigned_sales_territories,
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


def _validate_company(company=None):
    if not company:
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
    fields = [
        "name",
        "owner",
        "customer",
        "company",
        "docstatus",
        "status",
        "currency",
        "conversion_rate",
        "net_total",
        "grand_total",
        "base_grand_total",
        "amended_from",
    ]
    existing = frappe.db.get_value(
        "Sales Order",
        {"custom_clothing_request_id": request_id},
        fields,
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
    company = getattr(order, "company", None)
    if isinstance(company, str):
        company_str = company
    elif company and not hasattr(company, "_mock_return_value"):
        company_str = str(company)
    else:
        company_str = None

    amended_from = getattr(order, "amended_from", None)
    if isinstance(amended_from, str):
        amended_str = amended_from
    elif amended_from and not hasattr(amended_from, "_mock_return_value"):
        amended_str = str(amended_from)
    else:
        amended_str = None

    return {
        "name": str(order.name),
        "customer": str(order.customer),
        "company": company_str,
        "docstatus": int(order.docstatus),
        "status": str(order.status),
        "currency": str(order.currency),
        "conversion_rate": flt(getattr(order, "conversion_rate", 1.0)),
        "net_total": flt(getattr(order, "net_total", 0.0)),
        "grand_total": flt(order.grand_total),
        "base_grand_total": flt(getattr(order, "base_grand_total", order.grand_total)),
        "amended_from": amended_str,
        "idempotent_replay": replay,
    }


def _order_customer_scope():
    """Return explicit retailer names, or None for a trusted clothing administrator."""
    if is_clothing_admin():
        return None
    territories = assigned_sales_territories()
    if not territories:
        return []
    return frappe.get_all(
        "Customer",
        filters={"disabled": 0, "territory": ["in", territories]},
        pluck="name",
    )


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
def get_retailer_stock_exposure(customer, company=None):
    """Calculate the retailer's physical store-stock exposure:
    - stock_held_at_shop: value of delivered goods less returns from submitted Delivery Notes.
    - pending_orders_value: value of undelivered submitted Sales Orders.
    - approved_limit: current approved credit/exposure limit from Customer Credit Limit.
    - total_exposure: stock_held_at_shop + pending_orders_value.
    - available_exposure: max(0.0, approved_limit - total_exposure) if approved_limit > 0 else None.
    """
    require_role(ORDER_ROLES)
    customer = _validate_customer(customer)
    if not company:
        company = _validate_company()

    from sales_erp.sales_erp.doctype.retailer_credit_limit_request.retailer_credit_limit_request import (
        get_customer_current_credit_limit,
    )
    approved_limit = flt(get_customer_current_credit_limit(customer, company))

    # 1. Physical stock held at shop (delivered less returns)
    outward_dn = frappe.db.sql(
        """
        SELECT COALESCE(SUM(dni.amount), 0.0) AS total_delivered
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.customer = %s
          AND dn.company = %s
          AND dn.docstatus = 1
          AND (dn.is_return = 0 OR dn.is_return IS NULL)
        """,
        (customer, company),
        as_dict=True,
    )
    total_delivered = flt(outward_dn[0].total_delivered) if outward_dn else 0.0

    return_dn = frappe.db.sql(
        """
        SELECT COALESCE(SUM(ABS(dni.amount)), 0.0) AS total_returned
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.customer = %s
          AND dn.company = %s
          AND dn.docstatus = 1
          AND dn.is_return = 1
        """,
        (customer, company),
        as_dict=True,
    )
    total_returned = flt(return_dn[0].total_returned) if return_dn else 0.0
    stock_held_at_shop = max(0.0, total_delivered - total_returned)

    # 2. Pending incoming orders value (submitted Sales Orders not yet delivered)
    pending_orders = frappe.db.sql(
        """
        SELECT COALESCE(SUM(GREATEST(0, soi.qty - soi.delivered_qty) * soi.rate), 0.0) AS pending_value
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE so.customer = %s
          AND so.company = %s
          AND so.docstatus = 1
          AND so.status NOT IN ('Completed', 'Cancelled', 'Closed')
        """,
        (customer, company),
        as_dict=True,
    )
    pending_orders_value = flt(pending_orders[0].pending_value) if pending_orders else 0.0

    total_exposure = stock_held_at_shop + pending_orders_value
    available_exposure = max(0.0, approved_limit - total_exposure) if approved_limit > 0 else None
    currency = frappe.get_cached_value("Company", company, "default_currency") or "INR"

    return {
        "customer": customer,
        "company": company,
        "currency": currency,
        "approved_limit": approved_limit,
        "stock_held_at_shop": stock_held_at_shop,
        "pending_orders_value": pending_orders_value,
        "total_exposure": total_exposure,
        "available_exposure": available_exposure,
        "exceeds_limit": bool(approved_limit > 0 and total_exposure > approved_limit),
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
        "can_reject": bool(is_sales_manager() and order.docstatus == 0),
        "can_resubmit": bool(order.docstatus == 0),
        "can_amend": bool(order.docstatus == 2),
        "can_edit": bool(is_clothing_admin() and order.docstatus == 0),
        "workflow": workflow_name,
    }
    rejection = (
        frappe.db.get_value("Sales Order", order.name, "custom_clothing_rejection_reason")
        if frappe.db.has_column("Sales Order", "custom_clothing_rejection_reason")
        else None
    )
    result["rejection_reason"] = rejection
    result["exposure"] = get_retailer_stock_exposure(order.customer, order.company)
    return result


def _active_sales_order_workflow():
    from frappe.model.workflow import get_workflow_name

    return get_workflow_name("Sales Order")


@frappe.whitelist(methods=["POST"])
def submit_clothing_order(name):
    """Submit one authorized draft through ERPNext's native Sales Order controller."""
    check_rate_limit("submit_clothing_order", limit=60, window_seconds=60)
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

    # Shop-stock exposure validation: verify stock at shop + pending incoming orders <= approved limit
    customer = getattr(order, "customer", None) or getattr(document, "customer", None)
    company = getattr(order, "company", None) or getattr(document, "company", None)
    exposure = get_retailer_stock_exposure(customer, company)
    new_total_exposure = exposure["total_exposure"] + flt(document.grand_total)
    if exposure["approved_limit"] > 0 and new_total_exposure > exposure["approved_limit"]:
        if not is_clothing_admin():
            frappe.throw(
                frappe._(
                    "Cannot submit order {0}: combined shop-stock exposure ({1} {2:,.2f}) exceeds approved limit of {1} {3:,.2f} "
                    "(Stock at shop: {1} {4:,.2f}, pending orders: {1} {5:,.2f}, this order: {1} {6:,.2f})."
                ).format(
                    order.name,
                    exposure["currency"],
                    new_total_exposure,
                    exposure["approved_limit"],
                    exposure["stock_held_at_shop"],
                    exposure["pending_orders_value"],
                    flt(document.grand_total),
                ),
                frappe.ValidationError,
            )

    # Native submit owns credit-limit, authorization, commission, stock-reservation,
    # taxes, linked-document and status behavior on the pinned ERPNext release.
    try:
        document.submit()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Sales Order Submitted",
        "Sales Order",
        document.name,
        {"customer": customer, "grand_total": flt(document.grand_total)},
    )
    return _result(document)


@frappe.whitelist(methods=["POST"])
def cancel_clothing_order(name):
    """Cancel one authorized submitted order through ERPNext's native controller."""
    check_rate_limit("cancel_clothing_order", limit=60, window_seconds=60)
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
    try:
        document.cancel()
    except Exception:
        frappe.db.rollback()
        raise

    record_security_audit_event(
        "Sales Order Cancelled",
        "Sales Order",
        document.name,
        {"customer": getattr(document, "customer", None)},
    )
    return _result(document)


@frappe.whitelist(methods=["POST"])
def reject_clothing_order(name, reason):
    """Reject or return a draft Clothing ERP order for amendment."""
    check_rate_limit("reject_clothing_order", limit=60, window_seconds=60)
    require_role(ORDER_REVIEW_ROLES)
    if not isinstance(reason, str) or len(reason.strip()) < 5:
        frappe.throw(frappe._("A rejection reason of at least 5 characters is required."))
    reason = reason.strip()

    order = _validate_order_access(name)
    if order.docstatus != 0:
        frappe.throw(frappe._("Only a draft Clothing ERP order can be rejected or returned."))

    frappe.db.sql(
        "SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE", order.name
    )
    order = _validate_order_access(order.name)
    if order.docstatus != 0:
        frappe.throw(frappe._("This order changed while it was being reviewed. Refresh."))

    document = frappe.get_doc("Sales Order", order.name)
    document.flags.ignore_permissions = True

    # If workflow active, try transition
    if workflow_name := _active_sales_order_workflow():
        from frappe.model.workflow import get_transitions, apply_workflow
        transitions = get_transitions(document)
        reject_action = None
        for t in transitions:
            if t.action.lower() in ("reject", "return", "send back"):
                reject_action = t.action
                break
        if reject_action:
            apply_workflow(document, reject_action)

    if hasattr(document, "custom_clothing_rejection_reason"):
        document.custom_clothing_rejection_reason = reason
    document.add_comment(
        "Workflow",
        frappe._("Order rejected by {0}. Reason: {1}").format(get_current_user(), reason),
    )
    document.save(ignore_permissions=True)

    record_security_audit_event(
        "Sales Order Rejected",
        "Sales Order",
        document.name,
        {"customer": document.customer, "reason": reason, "reviewer": get_current_user()},
    )
    res = _result(document)
    res["rejection_reason"] = reason
    return res


@frappe.whitelist(methods=["POST"])
def resubmit_clothing_order(name, items=None, delivery_date=None, notes=None):
    """Update and resubmit a draft order for supervisory review."""
    check_rate_limit("resubmit_clothing_order", limit=60, window_seconds=60)
    require_role(ORDER_ROLES)
    order = _validate_order_access(name)
    if order.docstatus != 0:
        frappe.throw(frappe._("Only a draft order can be resubmitted for review."))

    frappe.db.sql(
        "SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE", order.name
    )
    order = _validate_order_access(order.name)
    if order.docstatus != 0:
        frappe.throw(frappe._("This order changed while it was being edited. Refresh."))

    document = frappe.get_doc("Sales Order", order.name)
    document.flags.ignore_permissions = True

    from sales_erp.cadence import is_retailer_order_blocked_by_collection
    blocked, block_reason = is_retailer_order_blocked_by_collection(document.customer)
    if blocked:
        frappe.throw(block_reason, frappe.ValidationError)

    if items:
        rows = _items(items)
        _validate_catalogue_items([row["item_code"] for row in rows])
        target_delivery = getdate(delivery_date) if delivery_date else document.delivery_date
        document.items = []
        for row in rows:
            document.append("items", {
                "item_code": row["item_code"],
                "qty": row["qty"],
                "delivery_date": target_delivery,
            })

    if delivery_date:
        try:
            d_date = getdate(delivery_date)
            if d_date < getdate(nowdate()):
                frappe.throw(frappe._("Delivery Date cannot be in the past."))
            document.delivery_date = d_date
            for item in document.items:
                item.delivery_date = d_date
        except (TypeError, ValueError):
            frappe.throw(frappe._("Delivery Date is invalid."))

    if not getattr(document, "selling_price_list", None):
        document.selling_price_list = (
            frappe.db.get_value("Customer", document.customer, "default_price_list")
            or frappe.db.get_single_value("Selling Settings", "selling_price_list")
            or "Standard Selling"
        )
    document.set_missing_values()
    document.calculate_taxes_and_totals()

    exposure = get_retailer_stock_exposure(document.customer, document.company)
    if exposure["approved_limit"] > 0 and (exposure["total_exposure"] + flt(document.grand_total)) > exposure["approved_limit"]:
        if not is_clothing_admin():
            frappe.throw(
                frappe._(
                    "The combined shop-stock exposure ({0} {1:,.2f}) exceeds the retailer's approved limit of {0} {2:,.2f}."
                ).format(
                    exposure["currency"],
                    exposure["total_exposure"] + flt(document.grand_total),
                    exposure["approved_limit"],
                ),
                frappe.ValidationError,
            )

    if hasattr(document, "custom_clothing_rejection_reason"):
        document.custom_clothing_rejection_reason = ""

    if workflow_name := _active_sales_order_workflow():
        from frappe.model.workflow import get_transitions, apply_workflow
        transitions = get_transitions(document)
        resubmit_action = None
        for t in transitions:
            if t.action.lower() in ("resubmit", "submit for review", "submit"):
                resubmit_action = t.action
                break
        if resubmit_action:
            apply_workflow(document, resubmit_action)

    if notes:
        document.add_comment(
            "Workflow",
            frappe._("Order resubmitted by {0}. Notes: {1}").format(get_current_user(), notes),
        )

    document.save(ignore_permissions=True)

    record_security_audit_event(
        "Sales Order Resubmitted",
        "Sales Order",
        document.name,
        {"customer": document.customer, "grand_total": flt(document.grand_total), "notes": notes},
    )
    return _result(document)


@frappe.whitelist(methods=["POST"])
def apply_order_workflow_action(name, action, notes=None):
    """Execute a native ERPNext Workflow action on an authorized Sales Order."""
    check_rate_limit("apply_order_workflow_action", limit=60, window_seconds=60)
    require_role(ORDER_ROLES)
    action = str(action or "").strip()
    if not action:
        frappe.throw(frappe._("A workflow action is required."))

    order = _validate_order_access(name)
    workflow_name = _active_sales_order_workflow()
    if not workflow_name:
        frappe.throw(frappe._("No active Workflow configured on Sales Order."))

    frappe.db.sql(
        "SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE", order.name
    )
    order = _validate_order_access(order.name)
    document = frappe.get_doc("Sales Order", order.name)
    document.flags.ignore_permissions = True

    from frappe.model.workflow import get_transitions, apply_workflow
    transitions = get_transitions(document)
    matching = [t for t in transitions if t.action.lower() == action.lower()]
    if not matching:
        frappe.throw(
            frappe._("Workflow action '{0}' is not available in the current state for your role.").format(action),
            frappe.PermissionError,
        )

    target_transition = matching[0]

    target_state = frappe.db.get_value(
        "Workflow Document State",
        {"parent": workflow_name, "state": target_transition.next_state},
        "doc_status",
    )
    if cint(target_state) == 1:
        from sales_erp.cadence import is_retailer_order_blocked_by_collection
        blocked, block_reason = is_retailer_order_blocked_by_collection(document.customer)
        if blocked:
            frappe.throw(block_reason, frappe.ValidationError)

        exposure = get_retailer_stock_exposure(document.customer, document.company)
        new_total_exposure = exposure["total_exposure"] + flt(document.grand_total)
        if exposure["approved_limit"] > 0 and new_total_exposure > exposure["approved_limit"]:
            if not is_clothing_admin():
                frappe.throw(
                    frappe._("Cannot approve order: combined shop-stock exposure exceeds approved limit."),
                    frappe.ValidationError,
                )

    apply_workflow(document, target_transition.action)
    if notes:
        document.add_comment("Workflow", notes)

    record_security_audit_event(
        "Sales Order Workflow Action",
        "Sales Order",
        document.name,
        {"action": target_transition.action, "next_state": target_transition.next_state, "notes": notes},
    )
    return _result(document)


@frappe.whitelist(methods=["POST"])
def amend_clothing_order(name, request_id):
    """Amend a cancelled Clothing ERP order using native Frappe amendment conventions."""
    check_rate_limit("amend_clothing_order", limit=60, window_seconds=60)
    require_role(ORDER_ROLES)
    order = _validate_order_access(name)
    if order.docstatus != 2:
        frappe.throw(frappe._("Only a cancelled order can be amended."))

    request_id = _request_id(request_id)
    if existing := _existing_order(request_id, order.customer):
        return _result(existing, replay=True)

    cached, is_replay = validate_idempotency(
        "amend_clothing_order",
        request_id,
        {"cancelled_order": name, "customer": order.customer},
    )
    if is_replay:
        return cached

    frappe.db.sql(
        "SELECT name FROM `tabSales Order` WHERE name = %s FOR UPDATE", order.name
    )
    order = _validate_order_access(order.name)
    if order.docstatus != 2:
        frappe.throw(frappe._("This order changed while being amended. Refresh."))

    original_doc = frappe.get_doc("Sales Order", order.name)

    from sales_erp.cadence import is_retailer_order_blocked_by_collection
    blocked, block_reason = is_retailer_order_blocked_by_collection(original_doc.customer)
    if blocked:
        frappe.throw(block_reason, frappe.ValidationError)

    new_doc = frappe.copy_doc(original_doc)
    new_doc.docstatus = 0
    new_doc.amended_from = original_doc.name
    new_doc.custom_clothing_request_id = request_id
    if hasattr(new_doc, "custom_clothing_rejection_reason"):
        new_doc.custom_clothing_rejection_reason = ""
    new_doc.delivery_date = max(getdate(original_doc.delivery_date), getdate(nowdate()))
    for item in new_doc.items:
        item.delivery_date = new_doc.delivery_date

    new_doc.set_missing_values()
    new_doc.calculate_taxes_and_totals()

    exposure = get_retailer_stock_exposure(new_doc.customer, new_doc.company)
    if exposure["approved_limit"] > 0 and (exposure["total_exposure"] + flt(new_doc.grand_total)) > exposure["approved_limit"]:
        if not is_clothing_admin():
            clear_idempotency("amend_clothing_order", request_id)
            frappe.throw(
                frappe._("Cannot amend order: combined shop-stock exposure exceeds approved limit."),
                frappe.ValidationError,
            )

    try:
        new_doc.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        if existing := _existing_order(request_id, new_doc.customer):
            return _result(existing, replay=True)
        clear_idempotency("amend_clothing_order", request_id)
        frappe.db.rollback()
        raise
    except Exception:
        clear_idempotency("amend_clothing_order", request_id)
        frappe.db.rollback()
        raise

    res = _result(new_doc)
    res["amended_from"] = original_doc.name
    record_security_audit_event(
        "Sales Order Amended",
        "Sales Order",
        new_doc.name,
        {"amended_from": original_doc.name, "grand_total": flt(new_doc.grand_total), "request_id": request_id},
    )
    save_idempotency_result(
        "amend_clothing_order",
        request_id,
        res,
        {"cancelled_order": name, "customer": order.customer},
    )
    return res


@frappe.whitelist(methods=["POST"])
def create_draft_sales_order(customer, items, request_id, delivery_date=None, company=None):
    """Create a standard ERPNext draft; submission remains a separate native workflow."""
    check_rate_limit("create_draft_sales_order", limit=60, window_seconds=60)
    require_role(ORDER_ROLES)
    customer = _validate_customer(customer)
    from sales_erp.cadence import is_retailer_order_blocked_by_collection
    blocked, block_reason = is_retailer_order_blocked_by_collection(customer)
    if blocked:
        frappe.throw(block_reason, frappe.ValidationError)
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

    cached, is_replay = validate_idempotency(
        "create_draft_sales_order",
        request_id,
        {"customer": customer, "items": rows, "delivery_date": str(delivery_date), "company": company or ""},
    )
    if is_replay:
        return cached

    # Row-lock Customer to serialize concurrent orders for the same retailer
    frappe.db.sql(
        "SELECT name FROM `tabCustomer` WHERE name = %s FOR UPDATE", customer
    )

    company = _validate_company(company)

    exposure = get_retailer_stock_exposure(customer, company)

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
    order.flags.ignore_permissions = True
    if not getattr(order, "selling_price_list", None):
        order.selling_price_list = (
            frappe.db.get_value("Customer", customer, "default_price_list")
            or frappe.db.get_single_value("Selling Settings", "selling_price_list")
            or "Standard Selling"
        )
    order.set_missing_values()
    order.calculate_taxes_and_totals()

    # Shop-stock exposure rule: stock already held at shop + new incoming stock <= approved limit
    if exposure["approved_limit"] > 0 and (exposure["total_exposure"] + flt(order.grand_total)) > exposure["approved_limit"]:
        if not is_clothing_admin():
            clear_idempotency("create_draft_sales_order", request_id)
            frappe.throw(
                frappe._(
                    "The combined shop-stock exposure ({0} {1:,.2f}) exceeds the retailer's approved limit of {0} {2:,.2f} "
                    "(Stock held at shop: {0} {3:,.2f}, pending orders: {0} {4:,.2f}, this order: {0} {5:,.2f})."
                ).format(
                    exposure["currency"],
                    exposure["total_exposure"] + flt(order.grand_total),
                    exposure["approved_limit"],
                    exposure["stock_held_at_shop"],
                    exposure["pending_orders_value"],
                    flt(order.grand_total),
                ),
                frappe.ValidationError,
            )

    try:
        order.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        if existing := _existing_order(request_id, customer):
            return _result(existing, replay=True)
        clear_idempotency("create_draft_sales_order", request_id)
        frappe.db.rollback()
        raise
    except Exception:
        clear_idempotency("create_draft_sales_order", request_id)
        frappe.db.rollback()
        raise

    res = _result(order)
    record_security_audit_event(
        "Sales Order Draft Created",
        "Sales Order",
        order.name,
        {"customer": customer, "grand_total": flt(order.grand_total), "request_id": request_id},
    )
    save_idempotency_result(
        "create_draft_sales_order",
        request_id,
        res,
        {"customer": customer, "items": rows, "delivery_date": str(delivery_date), "company": company or ""},
    )
    return res
