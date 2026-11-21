"""Idempotent app-owned role, custom fields, and permissions provisioning for Sales ERP."""

import os
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from sales_erp.boot import ensure_module_app_mapped
from sales_erp.erpnext_compat import ensure_erpnext_contact_fields
from sales_erp.retailer_defaults import ensure_retailer_defaults
from sales_erp.roles import (
    ALL_ROLES,
    LEGACY_ROLE_SALES_MANAGER,
    LEGACY_ROLE_SALESPERSON,
    ROLE_ASM,
    ROLE_BUSINESS_ADMIN,
    ROLE_RSM,
    ROLE_SALES_MANAGER,
    ROLE_SALESPERSON,
)
from sales_erp.supervision import migrate_existing_assignments


LEGACY_SALES_ROLE_MAP = {
    LEGACY_ROLE_SALESPERSON: ROLE_SALESPERSON,
    LEGACY_ROLE_SALES_MANAGER: ROLE_SALES_MANAGER,
}


def remove_legacy_roles():
    """Ensure legacy Clothing Salesperson and Clothing Sales Manager roles and artifacts are completely removed."""
    for old_role in (LEGACY_ROLE_SALESPERSON, LEGACY_ROLE_SALES_MANAGER):
        for doctype in {
            "Item", "Item Group", "Brand", "UOM", "Company", "Customer",
            "Account", "Price List", "Territory", "Customer Group", "Sales Order",
            "ASM Supervision", "Retailer Application", "Retailer Visit",
        }:
            _remove_custom_docperm(doctype, old_role)
        for name in frappe.get_all("Has Role", filters={"role": old_role}, pluck="name"):
            frappe.delete_doc("Has Role", name, ignore_permissions=True, force=True)
        if frappe.db.exists("Role Profile", old_role):
            frappe.delete_doc("Role Profile", old_role, ignore_permissions=True, force=True)
        if frappe.db.exists("Role", old_role):
            frappe.delete_doc("Role", old_role, ignore_permissions=True, force=True)


def _ensure_user_permission(user, allow, for_value):
    if not for_value or frappe.db.exists(
        "User Permission",
        {"user": user, "allow": allow, "for_value": for_value},
    ):
        return
    frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": user,
            "allow": allow,
            "for_value": for_value,
            "apply_to_all_doctypes": 1,
        }
    ).insert(ignore_permissions=True)


def migrate_legacy_sales_roles():
    """Move legacy salesperson/manager users onto the ASM/RSM role model."""
    for old_role, new_role in LEGACY_SALES_ROLE_MAP.items():
        if frappe.db.exists("Role Profile", old_role):
            if not frappe.db.exists("Role Profile", new_role):
                frappe.rename_doc("Role Profile", old_role, new_role, force=True)
            else:
                frappe.db.set_value(
                    "User", {"role_profile_name": old_role}, "role_profile_name", new_role
                )
        profile_names = frappe.get_all(
            "Has Role",
            filters={
                "role": old_role,
                "parenttype": "Role Profile",
                "parentfield": "roles",
            },
            pluck="parent",
        )
        for profile_name in set(profile_names):
            profile = frappe.get_doc("Role Profile", profile_name)
            for row in profile.roles:
                if row.role == old_role:
                    row.role = new_role
            profile.save(ignore_permissions=True)

        users = frappe.get_all(
            "Has Role", filters={"role": old_role, "parenttype": "User"}, pluck="parent"
        )
        for user_name in sorted(set(users)):
            user = frappe.get_doc("User", user_name)
            user.add_roles(new_role)
            user.remove_roles(old_role)


def _role_doctypes(role_name):
    shared = {
        "Item",
        "Item Group",
        "Brand",
        "UOM",
        "Company",
        "Customer",
        "Account",
        "Price List",
        "Customer Group",
        "Retailer Application",
        "Retailer Visit",
        "Retailer Assignment History",
        "Delivery Follow-Up Obligation",
    }
    if role_name == ROLE_SALESPERSON:
        return shared
    if role_name in {ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}:
        shared = shared | {"Territory", "ASM Supervision"}
    if role_name == ROLE_BUSINESS_ADMIN:
        shared = shared | {"Sales Order"}
    return shared if role_name in {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN} else set()


def _sync_standard_docperms(doctype):
    """If Custom DocPerm is used for a DocType, ensure all standard DocPerms from
    doctype metadata are present so native roles (Sales User, Sales Manager,
    System Manager, Accounts User, Stock User, etc.) never lose baseline permissions."""
    if not frappe.db.exists("DocType", doctype):
        return
    standard_perms = frappe.get_all(
        "DocPerm",
        filters={"parent": doctype},
        fields=[
            "role", "permlevel", "read", "write", "create", "delete",
            "submit", "cancel", "amend", "report", "export", "import",
            "share", "print", "email", "select", "if_owner"
        ],
    )
    if not standard_perms:
        return

    existing_custom = {
        (d.role, d.permlevel, d.if_owner)
        for d in frappe.get_all(
            "Custom DocPerm",
            filters={"parent": doctype},
            fields=["role", "permlevel", "if_owner"],
        )
    }

    for sp in standard_perms:
        key = (sp.role, sp.permlevel, sp.if_owner)
        if key not in existing_custom:
            cd = frappe.new_doc("Custom DocPerm")
            cd.parent = doctype
            cd.parenttype = "DocType"
            cd.parentfield = "permissions"
            for field, val in sp.items():
                if hasattr(cd, field):
                    setattr(cd, field, val)
            cd.insert(ignore_permissions=True)
            existing_custom.add(key)
        else:
            existing_name = frappe.db.get_value(
                "Custom DocPerm",
                {"parent": doctype, "role": sp.role, "permlevel": sp.permlevel, "if_owner": sp.if_owner},
            )
            if existing_name:
                doc = frappe.get_doc("Custom DocPerm", existing_name)
                changed = False
                for field, val in sp.items():
                    if val and hasattr(doc, field) and not getattr(doc, field):
                        setattr(doc, field, 1)
                        changed = True
                if changed:
                    doc.save(ignore_permissions=True)


def _ensure_custom_docperm(doctype, role, actions, permlevel=0):
    if not frappe.db.exists("DocType", doctype) or not frappe.db.exists("Role", role):
        return
    _sync_standard_docperms(doctype)
    existing = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0},
        fields=["name"] + [f"{a}" for a in actions if a in {
            "read", "write", "create", "submit", "cancel", "amend", "delete", "export", "report", "print", "email", "share"
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
        "permlevel": permlevel,
        "if_owner": 0,
    }
    for action in actions:
        values[action] = 1
    frappe.get_doc(values).insert(ignore_permissions=True)


def _remove_custom_docperm(doctype, role):
    if not frappe.db.exists("DocType", doctype):
        return
    for name in frappe.get_all(
        "Custom DocPerm", filters={"parent": doctype, "role": role}, pluck="name"
    ):
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)


def ensure_sales_erp_sidebar():
    """Ensure standard Sales ERP sidebar is imported and up-to-date."""
    sidebar_file = os.path.join(
        os.path.dirname(__file__),
        "sales_erp",
        "sidebar",
        "sales_erp",
        "sales_erp.json",
    )
    if os.path.exists(sidebar_file):
        frappe.modules.import_file.import_file_by_path(sidebar_file, force=True, ignore_version=True)


def after_install():
    ensure_module_app_mapped()
    ensure_retailer_defaults()
    ensure_erpnext_contact_fields()
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_clothing_product_images",
                    "label": "Clothing Product Images",
                    "fieldtype": "Table",
                    "options": "Clothing Product Image",
                    "insert_after": "image",
                    "read_only": 0,
                    "description": "Gallery of product photographs with colour assignments.",
                },
                {
                    "fieldname": "custom_clothing_metadata_section",
                    "label": "Clothing Metadata",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_clothing_product_images",
                    "collapsible": 1,
                },
                {
                    "fieldname": "custom_clothing_style_code",
                    "label": "Style Code",
                    "fieldtype": "Data",
                    "insert_after": "custom_clothing_metadata_section",
                },
                {
                    "fieldname": "custom_clothing_collection",
                    "label": "Collection",
                    "fieldtype": "Data",
                    "insert_after": "custom_clothing_style_code",
                },
                {
                    "fieldname": "custom_clothing_fabric",
                    "label": "Fabric",
                    "fieldtype": "Data",
                    "insert_after": "custom_clothing_collection",
                },
                {
                    "fieldname": "custom_clothing_fit",
                    "label": "Fit",
                    "fieldtype": "Data",
                    "insert_after": "custom_clothing_fabric",
                },
                {
                    "fieldname": "custom_clothing_season",
                    "label": "Season",
                    "fieldtype": "Data",
                    "insert_after": "custom_clothing_fit",
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_clothing_request_id",
                    "label": "Clothing Request ID",
                    "fieldtype": "Data",
                    "insert_after": "customer",
                    "read_only": 1,
                    "unique": 1,
                    "no_copy": 1,
                    "description": "Idempotency key for Sales Orders created from the catalogue.",
                },
                {
                    "fieldname": "custom_clothing_rejection_reason",
                    "label": "Clothing Rejection Reason",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_clothing_request_id",
                    "read_only": 1,
                    "no_copy": 1,
                    "description": "Reason recorded when an order was rejected or returned for amendment.",
                },
            ],
        }
    )
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
    migrate_legacy_sales_roles()
    for dt in ("Sales Order", "Item", "Item Group", "Brand", "UOM", "Company", "Customer", "Account", "Price List", "Customer Group", "Territory"):
        _sync_standard_docperms(dt)
        _ensure_custom_docperm(
            dt,
            "System Manager",
            ["read", "write", "create", "submit", "cancel", "amend", "delete", "export", "report", "print", "email", "share"],
        )
        _ensure_custom_docperm(
            dt,
            ROLE_BUSINESS_ADMIN,
            ["read", "write", "create", "submit", "cancel", "amend", "delete", "export", "report", "print", "email", "share"],
        )

    for role in ALL_ROLES:
        name = role["role_name"]
        for doctype in sorted(_role_doctypes(name)):
            if doctype == "Sales Order":
                _ensure_custom_docperm(
                    doctype,
                    name,
                    ["read", "write", "create", "submit", "cancel", "amend", "delete", "export", "report", "print", "email", "share"],
                )
            elif doctype == "ASM Supervision" and name == ROLE_BUSINESS_ADMIN:
                _ensure_custom_docperm(
                    doctype,
                    name,
                    ["read", "write", "create", "delete", "export", "report"],
                )
            elif doctype == "Retailer Application":
                if name == ROLE_BUSINESS_ADMIN:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "create", "delete", "export", "report"])
                elif name == ROLE_RSM:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "report"])
                else:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "create"])
            elif doctype == "Delivery Follow-Up Obligation":
                if name == ROLE_BUSINESS_ADMIN:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "create", "delete", "export", "report"])
                elif name == ROLE_SALESPERSON:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "report"])
                else:
                    _ensure_custom_docperm(doctype, name, ["read", "report"])
            elif doctype == "Retailer Visit":
                if name == ROLE_BUSINESS_ADMIN:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "create", "delete", "export", "report"])
                else:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "create", "report"])
            else:
                _ensure_custom_docperm(doctype, name, ["read"])

    _remove_custom_docperm("Territory", ROLE_SALESPERSON)
    for role in (ROLE_SALESPERSON, ROLE_SALES_MANAGER):
        _remove_custom_docperm("Sales Order", role)
    for old_role in LEGACY_SALES_ROLE_MAP:
        for doctype in {
            "Item", "Item Group", "Brand", "UOM", "Company", "Customer",
            "Account", "Price List", "Territory", "Customer Group", "Sales Order",
        }:
            _remove_custom_docperm(doctype, old_role)
    remove_legacy_roles()
    migrate_existing_assignments()
    ensure_sales_erp_sidebar()
    frappe.clear_cache()


def configure_launcher():
    """Explicit initial deployment setting; migrations preserve subsequent admin choices."""
    frappe.db.set_single_value("Website Settings", "home_page", "clothing")
    if frappe.get_meta("Desktop Settings").has_field("desktop_page"):
        frappe.db.set_single_value("Desktop Settings", "desktop_page", "Apps")
    frappe.clear_cache()


def after_migrate():
    ensure_module_app_mapped()
    after_install()
    ensure_sales_erp_sidebar()
