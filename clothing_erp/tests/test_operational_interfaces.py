"""Operational endpoints reject privilege escalation and return real empty results."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import frappe
from clothing_erp import api


class TestOperationalInterfaces(unittest.TestCase):
    def test_preview_role_switch_always_rejects(self):
        with patch.object(frappe, "throw", side_effect=frappe.PermissionError), patch.object(frappe, "_", side_effect=lambda s: s):
            for role in ("Administrator", "Salesperson", "Warehouse Operator"):
                with self.assertRaises(frappe.PermissionError):
                    api.switch_preview_role(role)

    def test_sales_endpoint_rejects_unauthorized_user_before_queries(self):
        with patch.object(api, "require_role", side_effect=frappe.PermissionError), patch.object(frappe, "get_all") as query:
            with self.assertRaises(frappe.PermissionError):
                api.get_salesperson_dashboard()
            query.assert_not_called()

    def test_warehouse_endpoint_rejects_unauthorized_user_before_queries(self):
        with patch.object(api, "require_role", side_effect=frappe.PermissionError), patch.object(frappe, "get_list") as query:
            with self.assertRaises(frappe.PermissionError):
                api.get_warehouse_dashboard()
            query.assert_not_called()

    def test_empty_site_has_zero_sales_metrics_without_fake_orders(self):
        def query(doctype, **kwargs):
            return [] if kwargs.get("order_by") else [frappe._dict(total=0)]

        with patch.object(api, "require_role"), patch.object(api, "today", return_value="2026-11-07"), patch.object(api, "_sales_customer_scope", return_value=None), patch.object(frappe, "get_all", side_effect=query):
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
            if kwargs.get("group_by") == "currency":
                return currencies
            return [] if kwargs.get("order_by") else [frappe._dict(total=0)]
        with patch.object(api, "require_role"), patch.object(api, "today", return_value="2026-11-07"), patch.object(api, "_sales_customer_scope", return_value=None), patch.object(frappe, "get_all", side_effect=query):
            result = api.get_salesperson_dashboard()
        self.assertEqual(result["monthly_sales"], currencies)
        self.assertNotIn("month_sales_value", result["metrics"])

    def test_retailer_directory_rejects_unauthorized_users_before_query(self):
        with patch.object(api, "require_role", side_effect=frappe.PermissionError), patch.object(frappe, "get_list") as query:
            with self.assertRaises(frappe.PermissionError):
                api.get_retailer_directory()
            query.assert_not_called()

    def test_retailer_directory_bounds_search_and_pagination(self):
        rows = [frappe._dict(name=f"TEST Retailer {index}") for index in range(3)]
        with patch.object(api, "require_role"), patch.object(frappe, "get_list", return_value=rows) as query:
            result = api.get_retailer_directory(search="  TEST  ", page=0, page_size=2)
        self.assertEqual(len(result["retailers"]), 2)
        self.assertTrue(result["has_more"])
        self.assertEqual(query.call_args.kwargs["start"], 0)
        self.assertEqual(query.call_args.kwargs["limit"], 3)
        self.assertNotIn("ignore_permissions", query.call_args.kwargs)
