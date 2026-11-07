"""Authenticated APIs. All data is queried with native document permissions."""
import frappe
from frappe.utils import today, get_first_day
from clothing_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN, ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_WAREHOUSE_MANAGER, ROLE_WAREHOUSE_OPERATOR
from clothing_erp.security import get_current_user, get_user_roles, get_active_operational_role, require_role, is_salesperson, is_warehouse_operator, is_clothing_admin
from clothing_erp.erpnext_client import get_sales_orders, get_pick_lists, get_delivery_notes

@frappe.whitelist()
def get_user_context():
    require_role({r["role_name"] for r in ALL_ROLES})
    return {"user": get_current_user(), "active_role": get_active_operational_role(),
            "roles": sorted(get_user_roles()),
            "permissions": {"salesperson_portal": is_salesperson(), "warehouse_operations": is_warehouse_operator(), "business_admin": is_clothing_admin()},
            "app_version": "0.2.0"}

@frappe.whitelist(methods=["POST"])
def switch_preview_role(role=None):
    # Reject requests from obsolete preview clients. Roles are assigned through User settings.
    frappe.throw(frappe._("Preview role switching has been removed. Ask your administrator to assign roles."), frappe.PermissionError)

def _count(doctype, filters=None):
    return frappe.get_list(doctype, filters=filters or {}, fields=[{"COUNT": "name", "as": "total"}])[0].total or 0

@frappe.whitelist()
def get_salesperson_dashboard():
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    date = today()
    monthly_sales = frappe.get_list("Sales Order", filters={"docstatus": 1, "transaction_date": ["between", [str(get_first_day(date)), date]]}, fields=["currency", {"SUM": "grand_total", "as": "total"}], group_by="currency")
    return {"metrics": {"today_orders_count": _count("Sales Order", {"transaction_date": date, "docstatus": ["!=", 2]}), "assigned_retailers_count": _count("Customer", {"disabled": 0})},
            "monthly_sales": monthly_sales, "recent_orders": get_sales_orders(),
            "shortcuts": [{"label": "Sales Orders", "url": "/desk/sales-order"}, {"label": "Retailers", "url": "/desk/customer"}, {"label": "Catalogue", "url": "/desk/item"}]}

@frappe.whitelist()
def get_warehouse_dashboard():
    require_role({ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN})
    return {"metrics": {"open_pick_lists": _count("Pick List", {"docstatus": ["!=", 2], "status": ["!=", "Completed"]}), "draft_delivery_notes": _count("Delivery Note", {"docstatus": 0})},
            "pick_tasks": get_pick_lists(), "delivery_notes": get_delivery_notes(),
            "shortcuts": [{"label": "Pick Lists", "url": "/desk/pick-list"}, {"label": "Delivery Notes", "url": "/desk/delivery-note"}]}
