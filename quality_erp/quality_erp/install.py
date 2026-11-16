"""Idempotent role and permission provisioning for Quality ERP."""

import os
import frappe
from quality_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
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


def ensure_quality_erp_sidebar():
    """Ensure standard Quality ERP sidebar is imported and up-to-date."""
    sidebar_file = os.path.join(
        os.path.dirname(__file__),
        "quality_erp",
        "sidebar",
        "quality_erp",
        "quality_erp.json",
    )
    if os.path.exists(sidebar_file):
        frappe.modules.import_file.import_file_by_path(sidebar_file, force=True, ignore_version=True)


def after_install():
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
        for dt in ("Supplier", "Purchase Order", "Quality Inspection"):
            _ensure_custom_docperm(dt, name, ["read"])

        if name == ROLE_BUSINESS_ADMIN:
            _ensure_custom_docperm(
                "Supplier Quality Inspection",
                name,
                ["read", "write", "create", "delete", "export", "report"],
            )
            _ensure_custom_docperm(
                "Return Quarantine",
                name,
                ["read", "write", "create", "delete", "export", "report"],
            )
        else:
            _ensure_custom_docperm(
                "Supplier Quality Inspection",
                name,
                ["read", "write", "create", "report"],
            )
            _ensure_custom_docperm(
                "Return Quarantine",
                name,
                ["read", "write", "create", "report"],
            )

    ensure_quality_erp_sidebar()
    frappe.clear_cache()


def after_migrate():
    after_install()
    ensure_quality_erp_sidebar()
