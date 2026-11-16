"""Keep Warehouse ERP operational users inside their purpose-built application."""

from warehouse_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN
from warehouse_erp.security import get_current_user, get_user_roles


def restrict_warehouse_app_visibility(bootinfo):
    """Enforce app visibility scoping:
    1. Operational Warehouse users only see Warehouse ERP.
    2. Administrative ERP apps (ERPNext, Insights, India Compliance) and other operational apps
       (Sales ERP, Quality ERP) are hidden from operational warehouse users.
    """
    user = get_current_user()
    roles = get_user_roles(user)
    wh_roles = {row["role_name"] for row in ALL_ROLES if row["role_name"] != ROLE_BUSINESS_ADMIN}
    is_wh_user = bool(roles & wh_roles)
    is_admin = user == "Administrator" or "System Manager" in roles or ROLE_BUSINESS_ADMIN in roles

    if is_wh_user and not is_admin:
        for app in bootinfo.get("app_data") or []:
            if app.get("app_name") != "warehouse_erp":
                app.update(
                    on_apps_screen=False,
                    app_route="",
                    desk_route="",
                    dock=[],
                )
