"""Idempotent app-owned role and read-permission provisioning."""
import frappe
from frappe.permissions import add_permission
from clothing_erp.roles import ALL_ROLES, ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN


def after_install():
    for role in ALL_ROLES:
        if not frappe.db.exists("Role", role["role_name"]):
            frappe.get_doc({"doctype": "Role", "role_name": role["role_name"], "desk_access": 1, "is_custom": 1}).insert(ignore_permissions=True)
    # Workflow writes will be granted with their respective implementation stages.
    for role in ALL_ROLES:
        name = role["role_name"]
        doctypes = {"Item", "Item Group", "Brand", "UOM"}
        if name in {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}:
            doctypes |= {"Customer", "Sales Order"}
        if name in {ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}:
            doctypes |= {"Warehouse", "Pick List", "Delivery Note"}
        for doctype in sorted(doctypes):
            if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": name, "permlevel": 0}):
                add_permission(doctype, name, ptype="read")
    frappe.clear_cache()


def configure_launcher():
    """Explicit initial deployment setting; migrations preserve subsequent admin choices."""
    frappe.db.set_single_value("Website Settings", "home_page", "clothing")
    if frappe.get_meta("Desktop Settings").has_field("desktop_page"):
        frappe.db.set_single_value("Desktop Settings", "desktop_page", "Apps")
    frappe.clear_cache()


def after_migrate():
    after_install()
