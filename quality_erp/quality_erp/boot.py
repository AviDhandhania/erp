"""Keep Quality ERP operational users inside their purpose-built application."""

from quality_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN
from quality_erp.security import get_current_user, get_user_roles


def restrict_quality_app_visibility(bootinfo):
    """Enforce app visibility scoping:
    1. Operational Quality users only see Quality ERP.
    2. Administrative ERP apps (ERPNext, Insights, India Compliance) and other operational apps
       (Sales ERP, Warehouse ERP) are hidden from operational quality users.
    """
    user = get_current_user()
    roles = get_user_roles(user)
    quality_roles = {row["role_name"] for row in ALL_ROLES if row["role_name"] != ROLE_BUSINESS_ADMIN}
    is_qual_user = bool(roles & quality_roles)
    is_admin = user == "Administrator" or "System Manager" in roles or ROLE_BUSINESS_ADMIN in roles

    if is_qual_user and not is_admin:
        for app in bootinfo.get("app_data") or []:
            if app.get("app_name") != "quality_erp":
                app.update(
                    on_apps_screen=False,
                    app_route="",
                    desk_route="",
                    dock=[],
                )
