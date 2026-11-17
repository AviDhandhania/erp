"""Keep Clothing ERP operational users inside their purpose-built application."""

import frappe
from clothing_erp.insights_compat import is_insights_admin
from clothing_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
)
from clothing_erp.security import get_current_user, get_user_roles


def restrict_erpnext_app_visibility(bootinfo):
    """Enforce app visibility scoping:
    1. Frappe Insights is strictly available only to admins.
    2. ERPNext and India Compliance are hidden from operational users.
    """
    user = get_current_user()
    roles = get_user_roles(user)
    clothing_roles = {row["role_name"] for row in ALL_ROLES if row["role_name"] != ROLE_BUSINESS_ADMIN}
    is_clothing_user = bool(roles & clothing_roles)
    is_admin = user == "Administrator" or "System Manager" in roles or ROLE_BUSINESS_ADMIN in roles

    # 1. Enforce admin-only for Insights: non-admins must never see Insights tile
    if not is_insights_admin(user, roles=roles):
        for app in bootinfo.get("app_data") or []:
            if app.get("app_name") in ("insights", "insights_v2"):
                app.update(
                    on_apps_screen=False,
                    app_route="",
                    desk_route="",
                    dock=[],
                )

    # 2. Operational users should not see administrative ERP apps.
    if is_clothing_user and not is_admin:
        for app in bootinfo.get("app_data") or []:
            if app.get("app_name") in ("erpnext", "india_compliance"):
                app.update(
                    on_apps_screen=False,
                    app_route="",
                    desk_route="",
                    dock=[],
                )


def apply_runtime_patches():
    """Apply runtime isolation patches across apps."""
    try:
        from sales_erp.boot import apply_runtime_patches as sales_apply
        sales_apply()
    except Exception:
        pass


def restrict_app_and_workspace_visibility(bootinfo):
    """Enforce app and workspace visibility during boot."""
    apply_runtime_patches()
    return restrict_erpnext_app_visibility(bootinfo)

