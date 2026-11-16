"""Keep Sales ERP operational users inside their purpose-built application."""

from sales_erp.insights_compat import is_insights_admin
from sales_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN
from sales_erp.security import get_current_user, get_user_roles


def restrict_sales_app_visibility(bootinfo):
    """Enforce app visibility scoping:
    1. Frappe Insights is strictly available only to admins.
    2. Operational sales users (ASM, RSM) can ONLY see Sales ERP.
       All other applications (ERPNext, India Compliance, Warehouse ERP, Quality ERP, etc.)
       are hidden.
    """
    user = get_current_user()
    roles = get_user_roles(user)
    sales_roles = {row["role_name"] for row in ALL_ROLES if row["role_name"] != ROLE_BUSINESS_ADMIN}
    is_sales_user = bool(roles & sales_roles)
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

    # 2. Operational sales users should only see Sales ERP.
    if is_sales_user and not is_admin:
        for app in bootinfo.get("app_data") or []:
            if app.get("app_name") != "sales_erp":
                app.update(
                    on_apps_screen=False,
                    app_route="",
                    desk_route="",
                    dock=[],
                )
