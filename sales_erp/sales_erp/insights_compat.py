"""Compatibility and security adapters for upstream Frappe Insights integration."""

import os
import shutil
import urllib.parse
import frappe

try:
    from insights.decorators import insights_whitelist
except ImportError:
    def insights_whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


INSIGHTS_ADMIN_ROLES = {
    "Administrator",
    "System Manager",
    "Clothing Business Administrator",
    "Insights Admin",
}


def is_insights_admin(user=None, roles=None):
    """Check if the given user has administrative privileges for Frappe Insights."""
    user = user or getattr(frappe.session, "user", None)
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    if roles is None:
        try:
            from sales_erp.security import get_user_roles
            roles = get_user_roles(user)
        except Exception:
            roles = set(frappe.get_roles(user)) if hasattr(frappe, "get_roles") else set()
    else:
        roles = set(roles)

    if roles & INSIGHTS_ADMIN_ROLES:
        return True

    try:
        from insights.insights.doctype.insights_team.insights_team import admin_team_members
        if user in admin_team_members():
            return True
    except Exception:
        pass

    return False


def check_app_permission():
    """App launcher permission check: Insights is strictly available only to admins."""
    return is_insights_admin()


def enforce_insights_admin_access():
    """Ensure that Frappe Insights web routes and APIs are strictly available only to admins."""
    request = getattr(frappe, "request", None)
    form_dict = getattr(frappe.local, "form_dict", {}) or {}

    path = (getattr(request, "path", None) or "").strip()
    cmd = form_dict.get("cmd") or ""
    doctype = form_dict.get("doctype") or ""

    is_insights_web = path.startswith("/insights") or path.startswith("/insights_v2")
    is_insights_desk = path.startswith("/app/insights-") or path.startswith("/desk#insights")
    is_insights_api = (
        path.startswith("/api/method/insights.")
        or cmd.startswith("insights.")
        or path.startswith("/api/resource/Insights")
        or doctype.startswith("Insights ")
    )

    if not (is_insights_web or is_insights_desk or is_insights_api):
        return

    if is_insights_admin():
        return

    user = getattr(frappe.session, "user", None)
    if not user or user == "Guest":
        redirect_to = urllib.parse.quote(path or "/insights")
        frappe.local.flags.redirect_location = f"/login?redirect-to={redirect_to}"
        raise frappe.Redirect

    frappe.throw(
        frappe._("Frappe Insights is restricted to administrators."),
        frappe.PermissionError,
    )


def patch_insights_permissions():
    """Patch upstream Insights app and doc permission checks to enforce admin-only access."""
    try:
        import insights.permissions

        orig_has_doc = getattr(insights.permissions, "has_doc_permission", None)
        orig_query_cond = getattr(insights.permissions, "get_permission_query_conditions", None)

        def restricted_check_app_permission():
            return is_insights_admin()

        def restricted_has_doc_permission(doc, ptype=None, user=None):
            if not is_insights_admin(user):
                return False
            if orig_has_doc:
                return orig_has_doc(doc, ptype, user)
            return True

        def restricted_get_permission_query_conditions(user=None, doctype=None):
            if not is_insights_admin(user):
                return "1=2"
            if orig_query_cond:
                return orig_query_cond(user, doctype)
            return ""

        insights.permissions.check_app_permission = restricted_check_app_permission
        insights.permissions.has_doc_permission = restricted_has_doc_permission
        insights.permissions.get_permission_query_conditions = restricted_get_permission_query_conditions
    except ImportError:
        pass


def patch_demo_data_factory():
    """Ensure DemoDataFactory uses the local bundled DuckDB demo file rather than failing on remote download."""
    try:
        from insights.setup.demo import DemoDataFactory
    except ImportError:
        return

    def safe_download_demo_data(self):
        bundled = None
        try:
            bundled = frappe.get_app_path("insights", "setup", self.db_filename)
        except Exception:
            pass

        if bundled and os.path.exists(bundled):
            os.makedirs(os.path.dirname(self.db_file_path), exist_ok=True)
            if not os.path.exists(self.db_file_path) or os.path.getsize(self.db_file_path) == 0:
                shutil.copyfile(bundled, self.db_file_path)
            return

        if getattr(frappe.flags, "in_test", False) or os.environ.get("CI"):
            return

        if os.path.exists(self.db_file_path) and os.path.getsize(self.db_file_path) > 0:
            return

        import requests

        try:
            with requests.get(self.db_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                os.makedirs(os.path.dirname(self.db_file_path), exist_ok=True)
                with open(self.db_file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            frappe.log_error("Error downloading demo data. Please check your Internet connection.")
            raise e

    DemoDataFactory.download_demo_data = safe_download_demo_data


@insights_whitelist(role="Insights Admin", methods=["POST"])
def setup_demo_data():
    """Resilient demo data setup using local bundled demo DuckDB database."""
    if getattr(frappe.flags, "in_test", False) or os.environ.get("CI"):
        return

    patch_demo_data_factory()
    try:
        from insights.setup.demo import DemoDataFactory

        factory = DemoDataFactory()
        factory.run()
        frappe.db.commit()
    except Exception:
        frappe.log_error("Insights: Demo Data Setup Failed")
        frappe.throw("Failed to setup demo data")


# Apply monkeypatches on module import if Insights is installed
patch_demo_data_factory()
patch_insights_permissions()
