"""Compatibility adapters for upstream Frappe Insights integration."""

import os
import shutil
import frappe

try:
    from insights.decorators import insights_whitelist
except ImportError:
    def insights_whitelist(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


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


# Apply monkeypatch on module import if Insights is installed
patch_demo_data_factory()
