"""Keep Clothing ERP operational users inside their purpose-built application."""

from clothing_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
)
from clothing_erp.security import get_current_user, get_user_roles


def restrict_erpnext_app_visibility(bootinfo):
    """Hide upstream app tiles (ERPNext, Insights) from operational Clothing ERP users.

    This is navigation scoping, not an authorization boundary. Document permissions and
    the app's server-side assignment checks remain authoritative.
    """
    user = get_current_user()
    roles = get_user_roles(user)
    clothing_roles = {row["role_name"] for row in ALL_ROLES}
    is_clothing_user = bool(roles & clothing_roles)
    is_administrator = user == "Administrator" or "System Manager" in roles
    if not is_clothing_user or is_administrator or ROLE_BUSINESS_ADMIN in roles:
        return

    for app in bootinfo.get("app_data") or []:
        if app.get("app_name") in ("erpnext", "insights"):
            app.update(
                on_apps_screen=False,
                app_route="",
                desk_route="",
                dock=[],
            )
