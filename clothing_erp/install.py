"""Idempotent app-owned role and read-permission provisioning."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission

from clothing_erp.erpnext_compat import ensure_erpnext_contact_fields
from clothing_erp.retailer_defaults import ensure_retailer_defaults
from clothing_erp.roles import (
    ALL_ROLES,
    LEGACY_ROLE_SALES_MANAGER,
    LEGACY_ROLE_SALESPERSON,
    ROLE_BUSINESS_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALESPERSON,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)
from clothing_erp.supervision import migrate_existing_assignments


LEGACY_SALES_ROLE_MAP = {
    LEGACY_ROLE_SALESPERSON: ROLE_SALESPERSON,
    LEGACY_ROLE_SALES_MANAGER: ROLE_SALES_MANAGER,
}


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
    """Move legacy salesperson/manager users onto the ASM/RSM role model.

    Existing customer assignments are converted to territory assignments before
    the old role is removed. This preserves access while deliberately adopting
    the new rule that an ASM works with every retailer in their territory.
    """
    for old_role, new_role in LEGACY_SALES_ROLE_MAP.items():
        # Earlier releases created matching Role Profiles. Rename those first so
        # saving a User cannot silently restore the retired role assignment.
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
            if old_role == LEGACY_ROLE_SALESPERSON:
                customer_names = frappe.get_all(
                    "User Permission",
                    filters={"user": user_name, "allow": "Customer"},
                    pluck="for_value",
                )
                for territory in set(
                    frappe.get_all(
                        "Customer",
                        filters={"name": ["in", customer_names]},
                        pluck="territory",
                    )
                    if customer_names
                    else []
                ):
                    _ensure_user_permission(user_name, "Territory", territory)
                if not frappe.db.exists(
                    "User Permission",
                    {"user": user_name, "allow": "Territory", "is_default": 1},
                ):
                    first_permission = frappe.db.get_value(
                        "User Permission",
                        {"user": user_name, "allow": "Territory"},
                        "name",
                        order_by="creation asc",
                    )
                    if first_permission:
                        frappe.db.set_value(
                            "User Permission", first_permission, "is_default", 1
                        )
            user.remove_roles(old_role)
            frappe.clear_cache(user=user_name)

    # Also repairs an interrupted/older migration where the role moved before a
    # default Territory was chosen. This keeps after_migrate fully idempotent.
    asm_users = frappe.get_all(
        "Has Role",
        filters={"role": ROLE_SALESPERSON, "parenttype": "User"},
        pluck="parent",
    )
    for user_name in set(asm_users):
        if frappe.db.exists(
            "User Permission",
            {"user": user_name, "allow": "Territory", "is_default": 1},
        ):
            continue
        first_permission = frappe.db.get_value(
            "User Permission",
            {"user": user_name, "allow": "Territory"},
            "name",
            order_by="creation asc",
        )
        if first_permission:
            frappe.db.set_value("User Permission", first_permission, "is_default", 1)
            frappe.clear_cache(user=user_name)


def _ensure_custom_docperm(doctype, role, ptypes):
    perm_name = frappe.db.get_value(
        "Custom DocPerm",
        {"parent": doctype, "role": role, "permlevel": 0},
        "name",
    )
    if perm_name:
        doc = frappe.get_doc("Custom DocPerm", perm_name)
        changed = False
        for ptype in ptypes:
            if not getattr(doc, ptype, 0):
                setattr(doc, ptype, 1)
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
    else:
        values = {
            "doctype": "Custom DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            "permlevel": 0,
        }
        for ptype in ptypes:
            values[ptype] = 1
        frappe.get_doc(values).insert(ignore_permissions=True)


def _remove_custom_docperm(doctype, role):
    """Remove app-owned access that is no longer part of the role contract."""
    for name in frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype, "role": role, "permlevel": 0},
        pluck="name",
    ):
        frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True)


def _role_doctypes(role):
    doctypes = {"Item", "Item Group", "Brand", "UOM"}
    if role in {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}:
        doctypes |= {"Company", "Customer", "Account", "Price List", "ASM Supervision"}
    if role == ROLE_SALESPERSON:
        doctypes.add("Customer Group")
    if role in {ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}:
        doctypes |= {"Territory", "Customer Group"}
    if role == ROLE_BUSINESS_ADMIN:
        doctypes.add("Sales Order")
    if role in {
        ROLE_WAREHOUSE_OPERATOR,
        ROLE_WAREHOUSE_MANAGER,
        ROLE_BUSINESS_ADMIN,
    }:
        doctypes |= {
            "Warehouse",
            "Pick List",
            "Delivery Note",
            "Batch",
            "Serial No",
            "Serial and Batch Bundle",
        }
    return doctypes


def after_install():
    ensure_erpnext_contact_fields()
    ensure_retailer_defaults()
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_clothing_product_images",
                    "fieldtype": "Table",
                    "label": "Clothing Product Gallery",
                    "options": "Clothing Product Image",
                    "insert_after": "image",
                    "description": "Additional ordered images shown in the Clothing ERP catalogue.",
                },
                {
                    "fieldname": "custom_clothing_metadata_section",
                    "fieldtype": "Section Break",
                    "label": "Clothing Catalogue Metadata",
                    "insert_after": "custom_clothing_product_images",
                    "collapsible": 1,
                    "depends_on": "eval:doc.has_variants && !doc.variant_of",
                },
                {
                    "fieldname": "custom_clothing_style_code",
                    "fieldtype": "Data",
                    "label": "Clothing Style Code",
                    "insert_after": "custom_clothing_metadata_section",
                    "in_standard_filter": 1,
                    "description": "Shared style or design reference. Each colour remains a separate Item template and SKU.",
                },
                {
                    "fieldname": "custom_clothing_collection",
                    "fieldtype": "Data",
                    "label": "Clothing Collection",
                    "insert_after": "custom_clothing_style_code",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_clothing_fabric",
                    "fieldtype": "Data",
                    "label": "Clothing Fabric",
                    "insert_after": "custom_clothing_collection",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_clothing_fit",
                    "fieldtype": "Data",
                    "label": "Clothing Fit",
                    "insert_after": "custom_clothing_fabric",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_clothing_season",
                    "fieldtype": "Data",
                    "label": "Clothing Season",
                    "insert_after": "custom_clothing_fit",
                    "in_standard_filter": 1,
                },
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_clothing_request_id",
                    "fieldtype": "Data",
                    "label": "Clothing Order Request ID",
                    "insert_after": "customer",
                    "hidden": 1,
                    "read_only": 1,
                    "no_copy": 1,
                    "unique": 1,
                    "description": "Idempotency key for Sales Orders created from the Clothing ERP catalogue.",
                }
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
    for role in ALL_ROLES:
        name = role["role_name"]
        for doctype in sorted(_role_doctypes(name)):
            if doctype == "Sales Order":
                _ensure_custom_docperm(
                    doctype,
                    name,
                    ["read", "write", "create", "submit", "cancel", "amend"],
                )
            elif doctype == "ASM Supervision" and name == ROLE_BUSINESS_ADMIN:
                _ensure_custom_docperm(
                    doctype,
                    name,
                    ["read", "write", "create", "delete", "export", "report"],
                )
            elif doctype == "Serial and Batch Bundle" and name in {
                ROLE_WAREHOUSE_OPERATOR,
                ROLE_WAREHOUSE_MANAGER,
                ROLE_BUSINESS_ADMIN,
            }:
                # A permission hook restricts mutation to the row-locked Pick List
                # completion service; direct bundle creation remains denied.
                _ensure_custom_docperm(
                    doctype, name, ["read", "write", "create", "submit"]
                )
            else:
                _ensure_custom_docperm(doctype, name, ["read"])
    # Territory is server-owned for an ASM. Customer Group remains readable so
    # the ASM can choose one of the four retailer types in the intake form.
    _remove_custom_docperm("Territory", ROLE_SALESPERSON)
    # Drafts are created through the validated catalogue service. Operational
    # sales roles must not acquire a native ERPNext Sales Order form/API surface.
    for role in (ROLE_SALESPERSON, ROLE_SALES_MANAGER):
        _remove_custom_docperm("Sales Order", role)
    for old_role in LEGACY_SALES_ROLE_MAP:
        for doctype in {
            "Item", "Item Group", "Brand", "UOM", "Company", "Customer",
            "Account", "Price List", "Territory", "Customer Group", "Sales Order",
        }:
            _remove_custom_docperm(doctype, old_role)
    migrate_existing_assignments()
    frappe.clear_cache()


def configure_launcher():
    """Explicit initial deployment setting; migrations preserve subsequent admin choices."""
    frappe.db.set_single_value("Website Settings", "home_page", "clothing")
    if frappe.get_meta("Desktop Settings").has_field("desktop_page"):
        frappe.db.set_single_value("Desktop Settings", "desktop_page", "Apps")
    frappe.clear_cache()


def after_migrate():
    after_install()
