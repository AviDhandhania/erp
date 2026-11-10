"""Catalogue security, filtering and matrix assembly tests."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import frappe

from clothing_erp import catalogue, pricing


class TestCatalogue(unittest.TestCase):
    def test_product_pricing_rejects_unauthorized_user_before_queries(self):
        with (
            patch.object(pricing, "require_role", side_effect=frappe.PermissionError),
            patch.object(frappe, "get_list") as query,
            self.assertRaises(frappe.PermissionError),
        ):
            pricing.get_product_pricing()
        query.assert_not_called()

    def test_product_pricing_page_is_admin_owned_and_linked(self):
        root = Path(__file__).parents[1]
        page = root / "clothing_erp/page/product_pricing/product_pricing.json"
        self.assertTrue(page.exists())
        self.assertIn('"role": "Clothing Business Administrator"', page.read_text())
        workspace = (
            root / "clothing_erp/workspace/clothing_erp/clothing_erp.json"
        ).read_text()
        self.assertIn('"link_to": "product-pricing"', workspace)

    def test_template_price_refuses_overlapping_active_prices_before_mutation(self):
        variants = [
            frappe._dict(
                name="TEST-MAROON-M",
                item_name="TEST Maroon / M",
                variant_of="TEST-MAROON",
                stock_uom="Nos",
                size="M",
            )
        ]
        with (
            patch.object(pricing, "require_role"),
            patch.object(
                pricing,
                "_selling_price_list",
                return_value=frappe._dict(name="Standard Selling", currency="INR"),
            ),
            patch.object(frappe, "get_list", return_value=["TEST-MAROON"]),
            patch.object(pricing, "_size_only_variants", return_value=variants),
            patch.object(frappe.db, "sql"),
            patch.object(
                pricing,
                "_active_generic_prices",
                return_value=({}, {"TEST-MAROON-M"}),
            ),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(frappe, "get_doc") as mutate,
            self.assertRaises(frappe.ValidationError),
        ):
            pricing.set_template_price("TEST-MAROON", "Standard Selling", 999)
        mutate.assert_not_called()

    def test_template_price_creates_native_item_prices_for_every_size(self):
        variants = [
            frappe._dict(
                name=f"TEST-MAROON-{size}",
                item_name=f"TEST Maroon / {size}",
                variant_of="TEST-MAROON",
                stock_uom="Nos",
                size=size,
            )
            for size in ("M", "L")
        ]
        created = []

        def get_doc(payload, *args):
            document = MagicMock()
            document.name = f"TEST-PRICE-{len(created) + 1}"
            created.append((payload, document))
            return document

        with (
            patch.object(pricing, "require_role"),
            patch.object(
                pricing,
                "_selling_price_list",
                return_value=frappe._dict(name="Standard Selling", currency="INR"),
            ),
            patch.object(frappe, "get_list", return_value=["TEST-MAROON"]),
            patch.object(pricing, "_size_only_variants", return_value=variants),
            patch.object(frappe.db, "sql") as lock,
            patch.object(pricing, "_active_generic_prices", return_value=({}, set())),
            patch.object(frappe, "get_doc", side_effect=get_doc),
            patch.object(pricing, "nowdate", return_value="2026-11-10"),
        ):
            result = pricing.set_template_price(
                "TEST-MAROON", "Standard Selling", "999"
            )
        self.assertIn("for update", lock.call_args.args[0].lower())
        self.assertEqual(len(created), 2)
        self.assertEqual(
            {payload["item_code"] for payload, _document in created},
            {"TEST-MAROON-M", "TEST-MAROON-L"},
        )
        self.assertTrue(all(payload["doctype"] == "Item Price" for payload, _ in created))
        self.assertTrue(all(document.insert.called for _payload, document in created))
        self.assertEqual(len(result["changed"]), 2)

    def test_trusted_customer_pricing_keeps_native_checks_without_sales_order_ui_permission(self):
        details = frappe._dict(
            warehouse=None,
            price_list_rate=499,
            blanket_order_rate=0,
            conversion_factor=1,
            margin_type=None,
            margin_rate_or_amount=0,
            discount_amount=0,
            discount_percentage=0,
        )
        context = {"doctype": "Sales Order", "customer": "TEST Retailer"}
        with (
            patch.object(pricing, "validate_pricing_parties") as parties,
            patch.object(pricing, "validate_pricing_price_lists") as price_lists,
            patch.object(pricing, "_get_item_details", return_value=details) as native,
            patch.object(frappe, "has_permission") as sales_order_permission,
        ):
            result = pricing._catalogue_item_details(context, {"items": []})
        parties.assert_called_once()
        price_lists.assert_called_once()
        native.assert_called_once()
        sales_order_permission.assert_not_called()
        self.assertEqual(result.price_list_rate, 499)
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
                custom_clothing_style_code="TEST-STYLE-1",
                custom_clothing_collection="TEST Essentials",
                custom_clothing_fabric="TEST Cotton",
                custom_clothing_fit="TEST Regular",
                custom_clothing_season="TEST Core",
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
            patch.object(
                catalogue, "_selling_price_list", return_value=("TEST Selling", "INR")
            ),
            patch.object(
                catalogue, "_templates", return_value=templates
            ) as template_query,
            patch.object(
                catalogue,
                "_product_images",
                return_value={
                    "TEST-TSHIRT": [{"image": "/test-front.jpg", "caption": "Front"}]
                },
            ),
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

        template_query.assert_called_once_with(
            "cotton",
            "",
            "",
            {"collection": "", "fabric": "", "fit": "", "season": ""},
            0,
            catalogue.MAX_PAGE_SIZE,
        )
        self.assertEqual(variant_query.call_args.args[0], "Item")
        self.assertNotIn("ignore_permissions", variant_query.call_args.kwargs)
        self.assertEqual(
            result["pagination"], {"page": 1, "page_size": 24, "has_more": False}
        )
        variant = result["products"][0]["variants"][0]
        self.assertEqual(result["products"][0]["images"][0]["caption"], "Front")
        self.assertEqual(result["products"][0]["style_code"], "TEST-STYLE-1")
        self.assertEqual(result["products"][0]["fabric"], "TEST Cotton")
        self.assertEqual(variant["item_code"], "TEST-TSHIRT-BLACK-M")
        self.assertEqual(variant["price"], 499)
        self.assertEqual(variant["actual_qty"], 12)
        self.assertTrue(variant["available"])

    def test_template_query_searches_style_code_and_applies_metadata_filters(self):
        with patch.object(frappe, "get_list", return_value=[]) as get_list:
            catalogue._templates(
                search="TEST-STYLE",
                item_group="TEST Garments",
                brand="TEST Brand",
                metadata={
                    "collection": "TEST Essentials",
                    "fabric": "TEST Cotton",
                    "fit": "TEST Regular",
                    "season": "TEST Core",
                },
            )
        kwargs = get_list.call_args.kwargs
        self.assertEqual(
            kwargs["or_filters"]["custom_clothing_style_code"], ["like", "%TEST-STYLE%"]
        )
        self.assertEqual(
            kwargs["filters"]["custom_clothing_collection"], "TEST Essentials"
        )
        self.assertEqual(kwargs["filters"]["custom_clothing_fabric"], "TEST Cotton")
        self.assertEqual(kwargs["filters"]["custom_clothing_fit"], "TEST Regular")
        self.assertEqual(kwargs["filters"]["custom_clothing_season"], "TEST Core")

    def test_filter_values_use_permission_aware_item_queries(self):
        def get_list(doctype, **kwargs):
            if doctype == "Item":
                fieldname = kwargs["fields"][0]
                return [frappe._dict({fieldname: f"TEST {fieldname}"})]
            return []

        with (
            patch.object(catalogue, "require_role"),
            patch.object(frappe, "get_list", side_effect=get_list) as query,
        ):
            result = catalogue.get_catalogue_filters()
        self.assertEqual(result["collection"], ["TEST custom_clothing_collection"])
        item_calls = [call for call in query.call_args_list if call.args[0] == "Item"]
        self.assertEqual(len(item_calls), len(catalogue.METADATA_FIELDS))
        self.assertTrue(
            all("ignore_permissions" not in call.kwargs for call in item_calls)
        )

    def test_active_price_excludes_future_expired_and_customer_specific_rows(self):
        rows = [
            frappe._dict(
                item_code="ITEM",
                uom="Nos",
                price_list_rate=100,
                currency="INR",
                valid_from="2026-01-01",
                valid_upto=None,
                customer=None,
                supplier=None,
                batch_no=None,
            ),
            frappe._dict(
                item_code="ITEM",
                uom="Nos",
                price_list_rate=999,
                currency="INR",
                valid_from="2027-01-01",
                valid_upto=None,
                customer=None,
                supplier=None,
                batch_no=None,
            ),
            frappe._dict(
                item_code="ITEM",
                uom="Nos",
                price_list_rate=888,
                currency="INR",
                valid_from="2025-01-01",
                valid_upto="2025-12-31",
                customer=None,
                supplier=None,
                batch_no=None,
            ),
            frappe._dict(
                item_code="ITEM",
                uom="Nos",
                price_list_rate=777,
                currency="INR",
                valid_from="2026-01-01",
                valid_upto=None,
                customer="TEST Retailer",
                supplier=None,
                batch_no=None,
            ),
        ]
        with (
            patch.object(frappe, "get_all", return_value=rows),
            patch.object(catalogue, "nowdate", return_value="2026-11-07"),
        ):
            prices = catalogue._active_prices({"ITEM": "Nos"}, "TEST Selling")
        self.assertEqual(prices, {"ITEM": {"rate": 100.0, "currency": "INR"}})

    def test_stock_respects_configured_warehouse_user_permissions(self):
        row = frappe._dict(item_code="ITEM", actual_qty=7)
        with (
            patch.object(
                catalogue, "assigned_documents", return_value=["Allowed Warehouse"]
            ),
            patch.object(frappe, "get_all", return_value=[row]) as get_all,
        ):
            self.assertEqual(catalogue._stock(["ITEM"]), {"ITEM": 7.0})
        self.assertEqual(
            get_all.call_args.kwargs["filters"]["warehouse"],
            ["in", ["Allowed Warehouse"]],
        )

    def test_customer_context_uses_native_customer_pricing(self):
        templates = [
            frappe._dict(
                name="TEST-TSHIRT",
                item_name="TEST Shirt",
                item_group="TEST Garments",
                brand="TEST Brand",
                description="Test",
                image=None,
                stock_uom="Nos",
            )
        ]
        variants = [
            frappe._dict(
                name="TEST-TSHIRT-M",
                item_name="TEST Shirt M",
                variant_of="TEST-TSHIRT",
                image=None,
                stock_uom="Nos",
            )
        ]
        with (
            patch.object(catalogue, "require_role"),
            patch.object(
                catalogue, "_selling_price_list", return_value=("Standard", "INR")
            ),
            patch.object(catalogue, "_templates", return_value=templates),
            patch.object(catalogue, "_product_images", return_value={}),
            patch.object(frappe, "get_list", return_value=variants),
            patch.object(catalogue, "_variant_attributes", return_value={}),
            patch.object(catalogue, "_active_prices", return_value={}),
            patch.object(catalogue, "_stock", return_value={}),
            patch(
                "clothing_erp.pricing.get_customer_prices",
                return_value=(
                    {"TEST-TSHIRT-M": {"rate": 425, "currency": "INR"}},
                    "Retailer Price",
                    "INR",
                ),
            ) as customer_prices,
        ):
            result = catalogue.get_catalogue(customer="TEST Retailer")
        customer_prices.assert_called_once_with("TEST Retailer", ["TEST-TSHIRT-M"])
        self.assertEqual(result["price_list"], "Retailer Price")
        self.assertEqual(result["products"][0]["variants"][0]["price"], 425)

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
        page = loads(
            (
                app_root
                / "clothing_erp/page/clothing_catalogue/clothing_catalogue.json"
            ).read_text()
        )
        workspace = loads(
            (
                app_root
                / "clothing_erp/workspace/salesperson_portal/salesperson_portal.json"
            ).read_text()
        )
        catalogue_script = (
            app_root / "clothing_erp/page/clothing_catalogue/clothing_catalogue.js"
        ).read_text()
        self.assertEqual(page["module"], "Clothing ERP")
        self.assertNotIn("Guest", {row["role"] for row in page["roles"]})
        self.assertTrue(
            any(
                row.get("link_to") == "clothing-catalogue" and row.get("type") == "Page"
                for row in workspace["shortcuts"]
            )
        )
        self.assertIn(
            'class="btn btn-primary btn-sm catalogue-photo-trigger catalogue-gallery-action"',
            catalogue_script,
        )
        self.assertIn("View photos ({0})", catalogue_script)
        self.assertIn(
            'class="btn btn-primary btn-sm create-sales-order"', catalogue_script
        )
        self.assertIn(
            "clothing_erp.ordering.create_draft_sales_order", catalogue_script
        )
        self.assertIn('roles.has("Clothing Business Administrator")', catalogue_script)
        self.assertIn("Order {0} was sent for administrator review.", catalogue_script)
