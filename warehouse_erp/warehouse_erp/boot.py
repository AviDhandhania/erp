"""Keep Warehouse ERP operational users inside their purpose-built application."""

import frappe
from warehouse_erp.roles import ALL_ROLES, ROLE_BUSINESS_ADMIN
from warehouse_erp.security import get_current_user, get_user_roles

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
    wh_roles = {"Clothing Warehouse Operator", "Clothing Warehouse Manager"}
    quality_roles = {"Clothing Quality Inspector", "Clothing Quality Manager"}

    permitted = set()
    if roles & sales_roles:
        permitted.add("sales_erp")
    if roles & wh_roles:
        permitted.add("warehouse_erp")
    if roles & quality_roles:
        permitted.add("quality_erp")

    return permitted if permitted else None


def apply_runtime_patches():
    """Patch get_apps and get_workspaces to guarantee strict operational app isolation."""
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


def restrict_warehouse_app_visibility(bootinfo):
    """Enforce app visibility scoping:
    1. Operational Warehouse users only see Warehouse ERP.
    2. Administrative ERP apps (ERPNext, Insights, India Compliance) and other operational apps
       (Sales ERP, Quality ERP) are hidden from operational warehouse users.
    """
    apply_runtime_patches()
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
            else:
                app["on_apps_screen"] = True
                app["desk_route"] = "/desk/warehouse-erp"
                app["app_route"] = "/desk/warehouse-erp"

        if "apps_data" in bootinfo and isinstance(bootinfo["apps_data"], dict):
            apps_list = bootinfo["apps_data"].get("apps") or []
            bootinfo["apps_data"]["apps"] = [a for a in apps_list if a.get("name") == "warehouse_erp"]
            bootinfo["apps_data"]["default_path"] = "/desk/warehouse-erp"

        if bootinfo.get("module_sidebars"):
            bootinfo["module_sidebars"] = {
                m: v for m, v in bootinfo["module_sidebars"].items() if m == "Warehouse ERP"
            }

        bootinfo["home_shell"] = "Warehouse ERP"
        bootinfo["home_page"] = "/desk/warehouse-erp"
        if bootinfo.get("allowed_workspaces"):
            bootinfo["allowed_workspaces"] = [
                w for w in bootinfo["allowed_workspaces"]
                if w.get("module") == "Warehouse ERP" or w.get("app") == "warehouse_erp"
            ]
