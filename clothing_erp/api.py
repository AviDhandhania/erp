"""Authenticated APIs. All data is queried with native document permissions."""
import frappe
from clothing_erp import __version__
from frappe.utils import cint, today, get_first_day
from clothing_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN, ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_WAREHOUSE_MANAGER, ROLE_WAREHOUSE_OPERATOR
from clothing_erp.security import assigned_documents, get_current_user, get_user_roles, get_active_operational_role, require_role, is_salesperson, is_warehouse_operator, is_clothing_admin, has_retailer_access
from clothing_erp.erpnext_client import get_pick_lists, get_delivery_notes

@frappe.whitelist()
def get_user_context():
    require_role({r["role_name"] for r in ALL_ROLES})
    return {"user": get_current_user(), "active_role": get_active_operational_role(),
            "roles": sorted(get_user_roles()),
            "permissions": {"salesperson_portal": is_salesperson(), "warehouse_operations": is_warehouse_operator(), "business_admin": is_clothing_admin()},
            "app_version": __version__}

@frappe.whitelist(methods=["POST"])
def switch_preview_role(role=None):
    # Reject requests from obsolete preview clients. Roles are assigned through User settings.
    frappe.throw(frappe._("Preview role switching has been removed. Ask your administrator to assign roles."), frappe.PermissionError)

def _count(doctype, filters=None):
    return frappe.get_list(doctype, filters=filters or {}, fields=[{"COUNT": "name", "as": "total"}])[0].total or 0


def _sales_customer_scope():
    """Return explicit retailer names, or None for a system/business administrator."""
    if is_clothing_admin():
        return None
    roles = get_user_roles()
    if ROLE_SALES_MANAGER in roles:
        territories = assigned_documents("Territory")
        if not territories:
            return []
        return frappe.get_all(
            "Customer",
            filters={"disabled": 0, "territory": ["in", territories]},
            pluck="name",
        )
    return assigned_documents("Customer")


def _scoped_sales_order_rows(customers, filters, fields, **kwargs):
    filters = dict(filters or {})
    if customers is not None:
        if not customers:
            return []
        filters["customer"] = ["in", customers]
    # Operational users intentionally have no native Sales Order permission.
    # This trusted endpoint uses an explicit assignment/territory scope instead.
    return frappe.get_all("Sales Order", filters=filters, fields=fields, **kwargs)

@frappe.whitelist()
def get_salesperson_dashboard():
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    date = today()
    customers = _sales_customer_scope()
    monthly_sales = _scoped_sales_order_rows(
        customers,
        {"docstatus": 1, "transaction_date": ["between", [str(get_first_day(date)), date]]},
        ["currency", {"SUM": "grand_total", "as": "total"}],
        group_by="currency",
    )
    today_count = _scoped_sales_order_rows(
        customers,
        {"transaction_date": date, "docstatus": ["!=", 2]},
        [{"COUNT": "name", "as": "total"}],
    )
    retailer_filters = {"disabled": 0}
    if customers is not None:
        if not customers:
            retailer_count = 0
        else:
            retailer_filters["name"] = ["in", customers]
            retailer_count = frappe.get_all(
                "Customer", filters=retailer_filters, fields=[{"COUNT": "name", "as": "total"}]
            )[0].total or 0
    else:
        retailer_count = frappe.get_all(
            "Customer", filters=retailer_filters, fields=[{"COUNT": "name", "as": "total"}]
        )[0].total or 0
    recent_orders = _scoped_sales_order_rows(
        customers,
        {"docstatus": ["!=", 2]},
        ["name", "customer", "transaction_date", "total_qty", "grand_total", "status"],
        order_by="modified desc",
        limit=20,
    )
    return {
        "metrics": {
            "today_orders_count": (today_count[0].total or 0) if today_count else 0,
            "assigned_retailers_count": retailer_count,
        },
        "monthly_sales": monthly_sales,
        "recent_orders": recent_orders,
        "shortcuts": [
            {"label": "Catalogue", "url": "/desk/clothing-erp/clothing-catalogue"},
            {"label": "Retailer Applications", "url": "/desk/clothing-erp/retailer-application"},
        ],
    }

@frappe.whitelist()
def get_warehouse_dashboard():
    require_role({ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN})
    return {"metrics": {"open_pick_lists": _count("Pick List", {"docstatus": ["!=", 2], "status": ["!=", "Completed"]}), "draft_delivery_notes": _count("Delivery Note", {"docstatus": 0})},
            "pick_tasks": get_pick_lists(), "delivery_notes": get_delivery_notes(),
            "shortcuts": [{"label": "Pick Lists", "url": "/desk/pick-list"}, {"label": "Delivery Notes", "url": "/desk/delivery-note"}]}


@frappe.whitelist()
def get_retailer_directory(search=None, page=1, page_size=20):
    """Permission-aware retailer directory for the salesperson application."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    search = (search or "").strip()[:80]
    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), 50)
    query = {
        "doctype": "Customer",
        "filters": {"disabled": 0},
        "fields": ["name", "customer_name", "territory", "customer_group", "mobile_no", "email_id"],
        "order_by": "customer_name asc, name asc",
        "start": (page - 1) * page_size,
        "limit": page_size + 1,
    }
    if search:
        pattern = f"%{search}%"
        query["or_filters"] = {"name": ["like", pattern], "customer_name": ["like", pattern], "mobile_no": ["like", pattern]}
    rows = frappe.get_list(**query)
    return {"retailers": rows[:page_size], "page": page, "has_more": len(rows) > page_size}


@frappe.whitelist()
def get_retailer_detail(customer):
    """Return one assigned retailer and authorized recent order history."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    if not has_retailer_access(customer):
        frappe.throw(frappe._("You do not have access to this retailer."), frappe.PermissionError)
    retailer = frappe.get_doc("Customer", customer).as_dict(
        no_nulls=True
    )
    allowed = {"name", "customer_name", "territory", "customer_group", "mobile_no", "email_id", "primary_address"}
    return {
        "retailer": {key: retailer[key] for key in allowed if key in retailer},
        "recent_orders": frappe.get_all(
            "Sales Order",
            filters={"customer": customer, "docstatus": ["!=", 2]},
            fields=["name", "transaction_date", "status", "currency", "grand_total"],
            order_by="transaction_date desc, modified desc",
            limit=10,
        ),
    }
