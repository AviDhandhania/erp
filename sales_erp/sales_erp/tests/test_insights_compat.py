"""Tests for Frappe Insights compatibility and demo data resilience."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from sales_erp import insights_compat


class TestInsightsCompat(unittest.TestCase):
    def test_safe_download_uses_bundled_duckdb(self):
        insights_compat.patch_demo_data_factory()
        from insights.setup.demo import DemoDataFactory

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_db = Path(temp_dir) / "insights_demo_data.duckdb"
            fake_factory = MagicMock()
            fake_factory.db_filename = "insights_demo_data.duckdb"
            fake_factory.db_file_path = str(temp_db)
            fake_factory.db_url = "https://invalid.example.com/not_exist.duckdb"

            with patch.object(frappe, "get_app_path") as get_app_path:
                bundled_dummy = Path(temp_dir) / "bundled.duckdb"
                bundled_dummy.write_bytes(b"DUCKDB_DEMO_DATA")
                get_app_path.return_value = str(bundled_dummy)

                DemoDataFactory.download_demo_data(fake_factory)

                self.assertTrue(temp_db.exists())
                self.assertEqual(temp_db.read_bytes(), b"DUCKDB_DEMO_DATA")

    def test_is_insights_admin_roles(self):
        # Administrator user
        self.assertTrue(insights_compat.is_insights_admin("Administrator"))

        # Admin roles
        for role in (
            "System Manager",
            "Clothing Business Administrator",
            "Insights Admin",
        ):
            with self.subTest(role=role):
                self.assertTrue(
                    insights_compat.is_insights_admin("admin_user", roles={role})
                )

        # Operational / non-admin roles
        for role in (
            "Clothing Area Sales Manager",
            "Clothing Regional Sales Manager",
            "Clothing Warehouse Operator",
            "Clothing Warehouse Manager",
            "Insights User",
        ):
            with self.subTest(role=role):
                self.assertFalse(
                    insights_compat.is_insights_admin("regular_user", roles={role})
                )

        # Guest
        self.assertFalse(insights_compat.is_insights_admin("Guest"))
        with patch.object(frappe, "session", frappe._dict(user="Guest")):
            self.assertFalse(insights_compat.is_insights_admin(None))

    def test_check_app_permission_matches_admin(self):
        with patch.object(insights_compat, "is_insights_admin", return_value=True):
            self.assertTrue(insights_compat.check_app_permission())

        with patch.object(insights_compat, "is_insights_admin", return_value=False):
            self.assertFalse(insights_compat.check_app_permission())

    def test_enforce_insights_admin_access_allowed_for_admin(self):
        fake_req = MagicMock(path="/insights/workbooks")
        with (
            patch.object(frappe, "request", fake_req),
            patch.object(insights_compat, "is_insights_admin", return_value=True),
        ):
            # Should execute without raising
            insights_compat.enforce_insights_admin_access()

    def test_enforce_insights_admin_access_ignored_for_non_insights_routes(self):
        fake_req = MagicMock(path="/desk")
        with (
            patch.object(frappe, "request", fake_req),
            patch.object(insights_compat, "is_insights_admin", return_value=False),
        ):
            # Non-insights route should be completely untouched
            insights_compat.enforce_insights_admin_access()

    def test_enforce_insights_admin_access_denies_authenticated_non_admin(self):
        fake_req = MagicMock(path="/insights/dashboard")
        with (
            patch.object(frappe, "request", fake_req),
            patch.object(frappe, "session", frappe._dict(user="salesperson@example.com")),
            patch.object(insights_compat, "is_insights_admin", return_value=False),
        ):
            with self.assertRaises(frappe.PermissionError):
                insights_compat.enforce_insights_admin_access()

    def test_enforce_insights_admin_access_denies_api_call(self):
        fake_req = MagicMock(path="/api/method/insights.api.queries.get")
        with (
            patch.object(frappe, "request", fake_req),
            patch.object(frappe, "session", frappe._dict(user="user@example.com")),
            patch.object(insights_compat, "is_insights_admin", return_value=False),
        ):
            with self.assertRaises(frappe.PermissionError):
                insights_compat.enforce_insights_admin_access()

    def test_enforce_insights_admin_access_redirects_guest(self):
        fake_req = MagicMock(path="/insights")
        with (
            patch.object(frappe, "request", fake_req),
            patch.object(frappe, "session", frappe._dict(user="Guest")),
            patch.object(insights_compat, "is_insights_admin", return_value=False),
        ):
            with self.assertRaises(frappe.Redirect):
                insights_compat.enforce_insights_admin_access()
            self.assertIn("/login?redirect-to=/insights", frappe.local.flags.redirect_location)

    def test_patched_insights_permissions_doc_and_query_conditions(self):
        insights_compat.patch_insights_permissions()
        import insights.permissions

        dummy_doc = frappe._dict(doctype="Insights Workbook", name="wb-123")

        # Non-admin user
        with patch.object(insights_compat, "is_insights_admin", return_value=False):
            self.assertFalse(insights.permissions.has_doc_permission(dummy_doc, "read", "user@example.com"))
            self.assertEqual(insights.permissions.get_permission_query_conditions("user@example.com", "Insights Workbook"), "1=2")

        # Admin user
        with patch.object(insights_compat, "is_insights_admin", return_value=True):
            self.assertTrue(insights.permissions.has_doc_permission(dummy_doc, "read", "Administrator"))
