"""Idempotent app-owned role and read-permission provisioning."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission

from clothing_erp.erpnext_compat import ensure_erpnext_contact_fields
from clothing_erp.retailer_defaults import ensure_retailer_defaults
from clothing_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALESPERSON,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)


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
    # Workflow writes and permissions provisioned by Gemini
    for role in ALL_ROLES:
        name = role["role_name"]
        doctypes = {"Item", "Item Group", "Brand", "UOM"}
        if name in {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}:
            doctypes |= {
                "Company",
                "Customer",
                "Sales Order",
                "Territory",
                "Customer Group",
                "Account",
                "Price List",
            }
        if name in {
            ROLE_WAREHOUSE_OPERATOR,
            ROLE_WAREHOUSE_MANAGER,
            ROLE_BUSINESS_ADMIN,
        }:
            doctypes |= {"Warehouse", "Pick List", "Delivery Note"}
        for doctype in sorted(doctypes):
            if doctype == "Sales Order":
                if name == ROLE_SALESPERSON:
                    _ensure_custom_docperm(doctype, name, ["read", "write", "create"])
                elif name in {ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}:
                    _ensure_custom_docperm(
                        doctype,
                        name,
                        ["read", "write", "create", "submit", "cancel", "amend"],
                    )
                else:
                    _ensure_custom_docperm(doctype, name, ["read"])
            else:
                _ensure_custom_docperm(doctype, name, ["read"])
    frappe.clear_cache()


def configure_launcher():
    """Explicit initial deployment setting; migrations preserve subsequent admin choices."""
    frappe.db.set_single_value("Website Settings", "home_page", "clothing")
    if frappe.get_meta("Desktop Settings").has_field("desktop_page"):
        frappe.db.set_single_value("Desktop Settings", "desktop_page", "Apps")
    frappe.clear_cache()


def after_migrate():
    after_install()
