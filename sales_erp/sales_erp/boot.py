"""Keep Sales ERP operational users inside their purpose-built application."""

import frappe
from sales_erp.insights_compat import is_insights_admin
from sales_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN
from sales_erp.security import get_current_user, get_user_roles

APP_MODULE_MAP = {
    "sales_erp": "Sales ERP",
    "warehouse_erp": "Warehouse ERP",
    "quality_erp": "Quality ERP",
}


def get_user_operational_permitted_apps(user=None):
    user = user or frappe.session.user
    if not user or user in ("Administrator", "Guest"):
        return None
    roles = set(frappe.get_roles(user))
    if "System Manager" in roles or ROLE_BUSINESS_ADMIN in roles:
        return None

    sales_roles = {"Clothing Area Sales Manager", "Clothing Regional Sales Manager"}
    wh_roles = {"Clothing Warehouse Manager"}
    quality_roles = {"Clothing Quality Inspector", "Clothing Quality Manager"}

    permitted = set()
    if roles & sales_roles:
        permitted.add("sales_erp")
    if roles & wh_roles:
        permitted.add("warehouse_erp")
    if roles & quality_roles:
        permitted.add("quality_erp")

    return permitted if permitted else None


def ensure_module_app_mapped():
    """Ensure sales_erp, warehouse_erp, and quality_erp are always mapped in local.module_app."""
    module_app = getattr(frappe.local, "module_app", None)
    if module_app is None:
        frappe.setup_module_map()
        module_app = getattr(frappe.local, "module_app", None) or {}

    missing = any(mod not in module_app for mod in ("sales_erp", "warehouse_erp", "quality_erp"))
    if missing:
        frappe.cache.delete_value("app_modules")
        frappe.client_cache.delete_value("installed_app_modules")
        frappe.setup_module_map(include_all_apps=True)
        if hasattr(frappe.local, "module_app") and frappe.local.module_app is not None:
            frappe.local.module_app["sales_erp"] = "sales_erp"
            frappe.local.module_app["warehouse_erp"] = "warehouse_erp"
            frappe.local.module_app["quality_erp"] = "quality_erp"


def apply_runtime_patches():
    """Patch get_apps and get_workspaces to guarantee strict operational app isolation."""
    ensure_module_app_mapped()
    try:
        import frappe.apps
        if not getattr(frappe.apps, "_isolation_patched", False):
            orig_get_apps = frappe.apps.get_apps

            def filtered_get_apps(*args, **kwargs):
                apps = orig_get_apps(*args, **kwargs)
                perm = get_user_operational_permitted_apps()
                if perm is not None:
                    return [a for a in apps if a.get("name") in perm]
                return apps

            filtered_get_apps._original = orig_get_apps
            frappe.apps.get_apps = filtered_get_apps
            frappe.apps._isolation_patched = True
    except Exception:
        pass

    try:
        import frappe.desk.desktop
        if not getattr(frappe.desk.desktop, "_isolation_patched", False):
            orig_get_workspaces = frappe.desk.desktop.get_workspaces

            def filtered_get_workspaces(*args, **kwargs):
                res = orig_get_workspaces(*args, **kwargs)
                perm = get_user_operational_permitted_apps()
                if perm is not None and isinstance(res, dict) and "pages" in res:
                    perm_modules = {APP_MODULE_MAP[app] for app in perm if app in APP_MODULE_MAP}
                    res["pages"] = [
                        p for p in res["pages"]
                        if p.get("app") in perm or p.get("module") in perm_modules
                    ]
                return res

            filtered_get_workspaces._original = orig_get_workspaces
            frappe.desk.desktop.get_workspaces = filtered_get_workspaces
            frappe.desk.desktop._isolation_patched = True
    except Exception:
        pass


def restrict_sales_app_visibility(bootinfo):
    """Enforce app visibility scoping:
    1. Frappe Insights is strictly available only to admins.
    2. Operational sales users (ASM, RSM) can ONLY see Sales ERP.
       All other applications (ERPNext, India Compliance, Warehouse ERP, Quality ERP, etc.)
       are hidden.
    """
    apply_runtime_patches()
    if bootinfo.get("module_app"):
        bootinfo["module_app"]["sales_erp"] = "sales_erp"
        bootinfo["module_app"]["warehouse_erp"] = "warehouse_erp"
        bootinfo["module_app"]["quality_erp"] = "quality_erp"
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
            else:
                app["on_apps_screen"] = True
                app["desk_route"] = "/desk/sales-erp"
                app["app_route"] = "/desk/sales-erp"

        if "apps_data" in bootinfo and isinstance(bootinfo["apps_data"], dict):
            apps_list = bootinfo["apps_data"].get("apps") or []
            bootinfo["apps_data"]["apps"] = [a for a in apps_list if a.get("name") == "sales_erp"]
            bootinfo["apps_data"]["default_path"] = "/desk/sales-erp"

        if bootinfo.get("module_sidebars"):
            bootinfo["module_sidebars"] = {
                m: v for m, v in bootinfo["module_sidebars"].items() if m == "Sales ERP"
            }

        bootinfo["home_shell"] = "Sales ERP"
        bootinfo["home_page"] = "/desk/sales-erp"
        if bootinfo.get("allowed_workspaces"):
            bootinfo["allowed_workspaces"] = [
                w for w in bootinfo["allowed_workspaces"]
                if w.get("module") == "Sales ERP" or w.get("app") == "sales_erp"
            ]
