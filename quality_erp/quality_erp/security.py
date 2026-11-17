"""High-security server authorization and critical gate enforcement for Quality ERP."""

import frappe
from quality_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)

SUPER_USER_ROLES = {"System Manager", "Administrator"}
CRITICAL_ADMIN_GATES = {"Production Go Ahead", "Final Inspection"}


def get_current_user(user=None):
    return user or frappe.session.user


def get_user_roles(user=None):
    user = get_current_user(user)
    if not user or user == "Guest":
        return set()
    if user != "Administrator" and not frappe.db.get_value("User", user, "enabled"):
        return set()
    return set(frappe.get_roles(user))


def has_any_role(required_roles, user=None):
    if get_current_user(user) == "Administrator":
        return True
    required = {required_roles} if isinstance(required_roles, str) else set(required_roles)
    return bool(get_user_roles(user) & (required | SUPER_USER_ROLES))


def require_role(allowed_roles, user=None):
    if not has_any_role(allowed_roles, user):
        frappe.throw(frappe._("You do not have permission to access this operation."), frappe.PermissionError)
    return True


def is_quality_admin(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN}, user)


def is_quality_manager(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN, ROLE_QUALITY_MANAGER}, user)


def is_quality_inspector(user=None):
    return has_any_role({ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN}, user)


def has_quality_app_access():
    return has_any_role({r["role_name"] for r in ALL_ROLES})


def assert_can_approve_quality_gate(stage, user=None):
    """Enforce highest level of data security:
    Critical gates (Production Go Ahead & Final Inspection) can ONLY be approved by Administrator.
    """
    user = get_current_user(user)
    if stage in CRITICAL_ADMIN_GATES and not is_quality_admin(user):
        frappe.throw(
            frappe._("Critical quality gate '{0}' requires Administrator approval. Quality Inspectors cannot approve release gates.").format(stage),
            frappe.PermissionError,
        )


def quality_inspection_has_permission(doc, ptype="read", user=None):
    user = get_current_user(user)
    if is_quality_admin(user):
        return True
    if not is_quality_inspector(user):
        return False
    if ptype in ("write", "create"):
        return True
    if ptype in ("submit", "cancel", "delete"):
        return is_quality_admin(user)
    return True


def return_quarantine_has_permission(doc, ptype="read", user=None):
    user = get_current_user(user)
    if is_quality_admin(user):
        return True
    if not is_quality_inspector(user):
        return False
    if ptype in ("write", "create"):
        return True
    if ptype in ("submit", "cancel", "delete"):
        return is_quality_admin(user)
    return True


def get_quality_inspection_conditions(user=None):
    user = get_current_user(user)
    if not is_quality_inspector(user):
        return "1=0"
    return ""


def get_return_quarantine_conditions(user=None):
    user = get_current_user(user)
    if not is_quality_inspector(user):
        return "1=0"
    return ""
