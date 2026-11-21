"""Idempotent role and permission provisioning for Quality ERP."""

import os
import frappe
from quality_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)


def _sync_standard_docperms(doctype):
    """If Custom DocPerm is used for a DocType, ensure all standard DocPerms from
    doctype metadata are present so native roles (Purchase User, Purchase Manager,
    System Manager, etc.) never lose their baseline permissions."""
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

    for dt in ("Supplier", "Purchase Order", "Quality Inspection"):
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
        for role_name in (ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER):
            _ensure_custom_docperm(dt, role_name, ["read", "report", "print", "email"])

    for role in ALL_ROLES:
        name = role["role_name"]

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
            _ensure_custom_docperm(
                "Production Quality Cycle",
                name,
                ["read", "write", "create", "delete", "export", "report"],
            )
            _ensure_custom_docperm(
                "Quality Checklist Template",
                name,
                ["read", "write", "create", "delete", "export", "report"],
            )
            _ensure_custom_docperm(
                "Supplier Quality Claim",
                name,
                ["read", "write", "create", "delete", "export", "report"],
            )
        elif name == ROLE_QUALITY_MANAGER:
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
            _ensure_custom_docperm(
                "Production Quality Cycle",
                name,
                ["read", "write", "create", "report"],
            )
            _ensure_custom_docperm(
                "Quality Checklist Template",
                name,
                ["read", "write", "create", "report"],
            )
            _ensure_custom_docperm(
                "Supplier Quality Claim",
                name,
                ["read", "write", "create", "export", "report"],
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
            _ensure_custom_docperm(
                "Production Quality Cycle",
                name,
                ["read", "write", "create", "report"],
            )
            _ensure_custom_docperm(
                "Quality Checklist Template",
                name,
                ["read", "report"],
            )
            _ensure_custom_docperm(
                "Supplier Quality Claim",
                name,
                ["read", "write", "create", "report"],
            )

    ensure_quality_erp_sidebar()
    _ensure_custom_docperm("Return Quarantine", "Clothing Warehouse Manager", ["read", "write", "create", "report"])
    frappe.clear_cache()


def after_migrate():
    after_install()
    ensure_quality_erp_sidebar()
    try:
        from quality_erp.cycle import migrate_supplier_inspections_to_cycles
        migrate_supplier_inspections_to_cycles()
    except Exception:
        pass
