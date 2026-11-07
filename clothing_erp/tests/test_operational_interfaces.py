"""Operational endpoints reject privilege escalation and return real empty results."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import frappe
from clothing_erp import api, security


class TestOperationalInterfaces(unittest.TestCase):
    def test_preview_role_switch_always_rejects(self):
        with patch.object(frappe, "throw", side_effect=frappe.PermissionError), patch.object(frappe, "_", side_effect=lambda s: s):
            for role in ("Administrator", "Salesperson", "Warehouse Operator"):
                with self.assertRaises(frappe.PermissionError):
                    api.switch_preview_role(role)

    def test_sales_endpoint_rejects_unauthorized_user_before_queries(self):
        with patch.object(api, "require_role", side_effect=frappe.PermissionError), patch.object(frappe, "get_list") as query:
            with self.assertRaises(frappe.PermissionError):
                api.get_salesperson_dashboard()
            query.assert_not_called()

    def test_warehouse_endpoint_rejects_unauthorized_user_before_queries(self):
        with patch.object(api, "require_role", side_effect=frappe.PermissionError), patch.object(frappe, "get_list") as query:
            with self.assertRaises(frappe.PermissionError):
                api.get_warehouse_dashboard()
            query.assert_not_called()

    def test_empty_site_has_zero_sales_metrics_without_fake_orders(self):
        with patch.object(api, "require_role"), patch.object(api, "today", return_value="2026-11-07"), patch.object(frappe, "get_list", return_value=[frappe._dict(total=0)]), patch.object(api, "get_sales_orders", return_value=[]):
            data = api.get_salesperson_dashboard()
        self.assertEqual(data["recent_orders"], [])
        self.assertTrue(all(value == 0 for value in data["metrics"].values()))

    def test_native_queries_preserve_permission_checks(self):
        from clothing_erp.erpnext_client import get_customers
        with patch.object(frappe, "get_list", return_value=[]) as query:
            self.assertEqual(get_customers(), [])
            self.assertNotIn("ignore_permissions", query.call_args.kwargs)

    def test_workspace_definitions_are_owned_by_custom_module(self):
        paths = list((Path(__file__).parents[1] / "clothing_erp/workspace").glob("*/*.json"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            data = json.loads(path.read_text())
            self.assertEqual(data["doctype"], "Workspace")
            self.assertEqual(data["module"], "Clothing ERP")
            self.assertEqual(data["title"], data["label"])
            self.assertTrue(data["roles"])

    def test_monthly_sales_are_grouped_by_currency(self):
        currencies = [frappe._dict(currency="INR", total=100), frappe._dict(currency="USD", total=20)]
        def query(doctype, **kwargs):
            return currencies if kwargs.get("group_by") == "currency" else [frappe._dict(total=0)]
        with patch.object(api, "require_role"), patch.object(api, "today", return_value="2026-11-07"), patch.object(frappe, "get_list", side_effect=query), patch.object(api, "get_sales_orders", return_value=[]):
            result = api.get_salesperson_dashboard()
        self.assertEqual(result["monthly_sales"], currencies)
        self.assertNotIn("month_sales_value", result["metrics"])
