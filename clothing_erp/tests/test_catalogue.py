"""Catalogue security, filtering and matrix assembly tests."""

import unittest
from unittest.mock import patch

import frappe

from clothing_erp import catalogue


class TestCatalogue(unittest.TestCase):
    def test_unauthorized_request_is_rejected_before_database_access(self):
        with (
            patch.object(catalogue, "require_role", side_effect=frappe.PermissionError),
            patch.object(catalogue, "_selling_price_list") as price_list,
        ):
            with self.assertRaises(frappe.PermissionError):
                catalogue.get_catalogue()
            price_list.assert_not_called()

    def test_catalogue_uses_native_templates_and_builds_variant_matrix(self):
        templates = [
            frappe._dict(
                name="TEST-TSHIRT",
                item_name="TEST Cotton T-shirt",
                item_group="TEST Garments",
                brand="TEST Brand",
                description="Fictional test garment",
                image=None,
                stock_uom="Nos",
            )
        ]
        variants = [
            frappe._dict(
                name="TEST-TSHIRT-BLACK-M",
                item_name="TEST Cotton T-shirt Black M",
                variant_of="TEST-TSHIRT",
                image=None,
                stock_uom="Nos",
            )
        ]
        with (
            patch.object(catalogue, "require_role"),
            patch.object(catalogue, "_selling_price_list", return_value=("TEST Selling", "INR")),
            patch.object(catalogue, "_templates", return_value=templates) as template_query,
            patch.object(catalogue, "_product_images", return_value={"TEST-TSHIRT": [{"image": "/test-front.jpg", "caption": "Front"}]}),
            patch.object(frappe, "get_list", return_value=variants) as variant_query,
            patch.object(
                catalogue,
                "_variant_attributes",
                return_value={
                    "TEST-TSHIRT-BLACK-M": [
                        {"attribute": "Colour", "value": "Black"},
                        {"attribute": "Size", "value": "M"},
                    ]
                },
            ),
            patch.object(
                catalogue,
                "_active_prices",
                return_value={"TEST-TSHIRT-BLACK-M": {"rate": 499, "currency": "INR"}},
            ),
            patch.object(catalogue, "_stock", return_value={"TEST-TSHIRT-BLACK-M": 12}),
        ):
            result = catalogue.get_catalogue(search="  cotton  ", page=0, page_size=999)

        template_query.assert_called_once_with("cotton", "", "", 0, catalogue.MAX_PAGE_SIZE)
        self.assertEqual(variant_query.call_args.args[0], "Item")
        self.assertNotIn("ignore_permissions", variant_query.call_args.kwargs)
        self.assertEqual(result["pagination"], {"page": 1, "page_size": 24, "has_more": False})
        variant = result["products"][0]["variants"][0]
        self.assertEqual(result["products"][0]["images"][0]["caption"], "Front")
        self.assertEqual(variant["item_code"], "TEST-TSHIRT-BLACK-M")
        self.assertEqual(variant["price"], 499)
        self.assertEqual(variant["actual_qty"], 12)
        self.assertTrue(variant["available"])

    def test_active_price_excludes_future_expired_and_customer_specific_rows(self):
        rows = [
            frappe._dict(item_code="ITEM", uom="Nos", price_list_rate=100, currency="INR", valid_from="2026-01-01", valid_upto=None, customer=None, supplier=None, batch_no=None),
            frappe._dict(item_code="ITEM", uom="Nos", price_list_rate=999, currency="INR", valid_from="2027-01-01", valid_upto=None, customer=None, supplier=None, batch_no=None),
            frappe._dict(item_code="ITEM", uom="Nos", price_list_rate=888, currency="INR", valid_from="2025-01-01", valid_upto="2025-12-31", customer=None, supplier=None, batch_no=None),
            frappe._dict(item_code="ITEM", uom="Nos", price_list_rate=777, currency="INR", valid_from="2026-01-01", valid_upto=None, customer="TEST Retailer", supplier=None, batch_no=None),
        ]
        with patch.object(frappe, "get_all", return_value=rows), patch.object(catalogue, "nowdate", return_value="2026-11-07"):
            prices = catalogue._active_prices({"ITEM": "Nos"}, "TEST Selling")
        self.assertEqual(prices, {"ITEM": {"rate": 100.0, "currency": "INR"}})

    def test_arbitrary_price_list_cannot_be_probed(self):
        with patch.object(catalogue, "frappe") as framework:
            framework.db.get_single_value.return_value = "Standard Selling"
            framework.throw.side_effect = frappe.PermissionError
            framework._.side_effect = lambda value: value
            with self.assertRaises(frappe.PermissionError):
                catalogue._selling_price_list("Private Dealer Prices")

    def test_catalogue_page_is_role_scoped_and_linked_from_sales_workspace(self):
        from json import loads
        from pathlib import Path

        app_root = Path(__file__).parents[1]
        page = loads((app_root / "clothing_erp/page/clothing_catalogue/clothing_catalogue.json").read_text())
        workspace = loads((app_root / "clothing_erp/workspace/salesperson_portal/salesperson_portal.json").read_text())
        self.assertEqual(page["module"], "Clothing ERP")
        self.assertNotIn("Guest", {row["role"] for row in page["roles"]})
        self.assertTrue(any(row.get("link_to") == "clothing-catalogue" and row.get("type") == "Page" for row in workspace["shortcuts"]))
