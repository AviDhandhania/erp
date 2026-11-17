"""Idempotent role and permission provisioning for Warehouse ERP."""

import os
import frappe
from warehouse_erp.roles import (
    ALL_ROLES,
    LEGACY_ROLE_WAREHOUSE_OPERATOR,
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
)


def _ensure_custom_docperm(doctype, role, actions):
    if not frappe.db.exists("DocType", doctype) or not frappe.db.exists("Role", role):
        return
    existing = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype, "role": role, "permlevel": 0},
        fields=["name"] + [f"{a}" for a in actions if a in {
            "read", "write", "create", "submit", "cancel", "amend", "delete", "export", "report"
        }],
    )
    if existing:
        doc = frappe.get_doc("Custom DocPerm", existing[0].name)
        changed = False
        for action in actions:
            if hasattr(doc, action) and not getattr(doc, action):
                setattr(doc, action, 1)
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
        return
    values = {
        "doctype": "Custom DocPerm",
        "parent": doctype,
        "parenttype": "DocType",
        "parentfield": "permissions",
        "role": role,
        "permlevel": 0,
    }
    for action in actions:
        values[action] = 1
    frappe.get_doc(values).insert(ignore_permissions=True)


def ensure_warehouse_erp_sidebar():
    """Ensure standard Warehouse ERP sidebar is imported and up-to-date."""
    sidebar_file = os.path.join(
        os.path.dirname(__file__),
        "warehouse_erp",
        "sidebar",
        "warehouse_erp",
        "warehouse_erp.json",
    )
    if os.path.exists(sidebar_file):
        frappe.modules.import_file.import_file_by_path(sidebar_file, force=True, ignore_version=True)


def ensure_custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(
        {
            "Pick List": [
                {
                    "fieldname": "custom_wave_id",
                    "label": "Wave ID",
                    "fieldtype": "Data",
                    "insert_after": "parent_warehouse",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "description": "Identifier for the picking wave batch.",
                },
                {
                    "fieldname": "custom_route_id",
                    "label": "Route ID",
                    "fieldtype": "Data",
                    "insert_after": "custom_wave_id",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "description": "Destination route / geographical delivery run.",
                },
            ],
            "Delivery Note": [
                {
                    "fieldname": "custom_wave_id",
                    "label": "Wave ID",
                    "fieldtype": "Data",
                    "insert_after": "customer",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_route_id",
                    "label": "Route ID",
                    "fieldtype": "Data",
                    "insert_after": "custom_wave_id",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_delivery_handoff",
                    "label": "Delivery Handoff",
                    "fieldtype": "Link",
                    "options": "Delivery Handoff",
                    "insert_after": "transporter_name",
                    "read_only": 1,
                    "no_copy": 1,
                },
                {
                    "fieldname": "custom_billing_invoice",
                    "label": "Prepared Billing Invoice",
                    "fieldtype": "Link",
                    "options": "Sales Invoice",
                    "insert_after": "custom_delivery_handoff",
                    "read_only": 1,
                    "no_copy": 1,
                },
            ],
            "Packing Slip": [
                {
                    "fieldname": "custom_package_barcode",
                    "label": "Package Barcode",
                    "fieldtype": "Data",
                    "insert_after": "to_case_no",
                    "in_list_view": 1,
                },
                {
                    "fieldname": "custom_length",
                    "label": "Length (cm)",
                    "fieldtype": "Float",
                    "insert_after": "gross_weight_uom",
                },
                {
                    "fieldname": "custom_width",
                    "label": "Width (cm)",
                    "fieldtype": "Float",
                    "insert_after": "custom_length",
                },
                {
                    "fieldname": "custom_height",
                    "label": "Height (cm)",
                    "fieldtype": "Float",
                    "insert_after": "custom_width",
                },
                {
                    "fieldname": "custom_dimension_uom",
                    "label": "Dimension UOM",
                    "fieldtype": "Data",
                    "default": "cm",
                    "insert_after": "custom_height",
                },
            ],
        }
    )


def after_install():
    ensure_custom_fields()
    for role in ALL_ROLES:
        if not frappe.db.exists("Role", role["role_name"]):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role["role_name"],
                    "desk_access": 1,
                    "is_custom": 1,
                }
            ).insert(ignore_permissions=True)

    for role in ALL_ROLES:
        name = role["role_name"]
        for dt in ("Warehouse", "Pick List", "Delivery Note", "Stock Entry", "Packing Slip", "Delivery Handoff"):
            _ensure_custom_docperm(dt, name, ["read"])

        _ensure_custom_docperm("Serial and Batch Bundle", name, ["read", "write", "create", "submit"])
        _ensure_custom_docperm("Packing Slip", name, ["read", "write", "create", "submit"])
        _ensure_custom_docperm("Delivery Handoff", name, ["read", "write", "create"])

    remove_legacy_operator_permissions()
    ensure_warehouse_erp_sidebar()
    frappe.clear_cache()


def remove_legacy_operator_permissions():
    """Remove active custom permissions and role records for the legacy Clothing Warehouse Operator."""
    for dt in ("Warehouse", "Pick List", "Delivery Note", "Stock Entry", "Packing Slip", "Serial and Batch Bundle"):
        perm_names = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": dt, "role": LEGACY_ROLE_WAREHOUSE_OPERATOR},
            pluck="name",
        )
        for perm in perm_names:
            frappe.delete_doc("Custom DocPerm", perm, ignore_permissions=True, force=True)

    for has_role_name in frappe.get_all(
        "Has Role",
        filters={"role": LEGACY_ROLE_WAREHOUSE_OPERATOR},
        pluck="name",
    ):
        frappe.delete_doc("Has Role", has_role_name, ignore_permissions=True, force=True)

    if frappe.db.exists("Role", LEGACY_ROLE_WAREHOUSE_OPERATOR):
        frappe.delete_doc("Role", LEGACY_ROLE_WAREHOUSE_OPERATOR, ignore_permissions=True, force=True)


def migrate_warehouse_operators_to_managers():
    """Migrate legacy Clothing Warehouse Operator users to Clothing Warehouse Manager and revoke operator role."""
    operator_users = frappe.get_all(
        "Has Role",
        filters={"role": LEGACY_ROLE_WAREHOUSE_OPERATOR, "parenttype": "User"},
        pluck="parent",
    )
    for user in set(operator_users):
        if user in {"Administrator", "Guest"} or not frappe.db.exists("User", user):
            continue
        user_roles = set(frappe.get_roles(user))
        user_doc = frappe.get_doc("User", user)
        if ROLE_WAREHOUSE_MANAGER not in user_roles:
            user_doc.add_roles(ROLE_WAREHOUSE_MANAGER)
            frappe.logger("warehouse_erp").info(
                f"Migrated user {user} from {LEGACY_ROLE_WAREHOUSE_OPERATOR} to {ROLE_WAREHOUSE_MANAGER}."
            )
        if LEGACY_ROLE_WAREHOUSE_OPERATOR in user_roles:
            user_doc.remove_roles(LEGACY_ROLE_WAREHOUSE_OPERATOR)
            frappe.logger("warehouse_erp").info(
                f"Removed legacy role {LEGACY_ROLE_WAREHOUSE_OPERATOR} from user {user}."
            )

    remove_legacy_operator_permissions()
    frappe.clear_cache()


def after_migrate():
    after_install()
    migrate_warehouse_operators_to_managers()
    ensure_warehouse_erp_sidebar()
