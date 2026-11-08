"""Stage 5 draft-order boundary and authoritative input tests."""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import getdate

from clothing_erp import ordering


class TestOrdering(unittest.TestCase):
    def test_unauthorized_request_is_rejected_before_customer_or_item_access(self):
        with (
            patch.object(ordering, "require_role", side_effect=frappe.PermissionError),
            patch.object(ordering, "_validate_customer") as customer,
            self.assertRaises(frappe.PermissionError),
        ):
            ordering.create_draft_sales_order("TEST Retailer", [], "not-a-request-id")
        customer.assert_not_called()

    def test_selection_combines_duplicate_sizes_and_rejects_fractional_quantity(self):
        self.assertEqual(
            ordering._items(
                [
                    {"item_code": "TEST-TEE-S01", "qty": 2},
                    {"item_code": "TEST-TEE-S01", "qty": "3"},
                ]
            ),
            [{"item_code": "TEST-TEE-S01", "qty": 5}],
        )
        with (
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            self.assertRaises(frappe.ValidationError),
        ):
            ordering._items([{"item_code": "TEST-TEE-S01", "qty": 1.5}])

    def test_native_draft_receives_no_browser_price_or_discount(self):
        order = MagicMock(
            customer="TEST Retailer",
            docstatus=0,
            status="Draft",
            currency="INR",
            grand_total=998,
        )
        order.name = "SAL-ORD-TEST-0001"
        with (
            patch.object(ordering, "require_role"),
            patch.object(ordering, "_validate_customer", return_value="TEST Retailer"),
            patch.object(ordering, "_existing_order", return_value=None),
            patch.object(ordering, "_validate_catalogue_items"),
            patch.object(ordering, "_validate_company", return_value="TEST Company"),
            patch.object(frappe, "get_doc", return_value=order) as get_doc,
            patch.object(ordering, "nowdate", return_value="2026-11-08"),
        ):
            result = ordering.create_draft_sales_order(
                "TEST Retailer",
                [
                    {
                        "item_code": "TEST-TEE-S01",
                        "qty": 2,
                        "rate": 1,
                        "discount_percentage": 99,
                    }
                ],
                "6d508e18-83cf-4dfe-9732-68bc7db84eb4",
                "2026-11-09",
            )
        payload = get_doc.call_args.args[0]
        self.assertEqual(payload["doctype"], "Sales Order")
        self.assertEqual(
            payload["items"],
            [
                {
                    "item_code": "TEST-TEE-S01",
                    "qty": 2,
                    "delivery_date": getdate("2026-11-09"),
                }
            ],
        )
        self.assertNotIn("rate", payload["items"][0])
        self.assertNotIn("discount_percentage", payload["items"][0])
        order.insert.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(result["name"], "SAL-ORD-TEST-0001")

    def test_catalogue_items_are_permission_filtered_and_size_only(self):
        item = frappe._dict(
            name="TEST-TEE-S01",
            variant_of="TEST-TEE",
            stock_uom="Nos",
        )
        with (
            patch.object(frappe, "get_list", return_value=[item]) as get_list,
            patch.object(
                frappe,
                "get_all",
                return_value=[frappe._dict(parent="TEST-TEE-S01", attribute="Size")],
            ),
        ):
            ordering._validate_catalogue_items(["TEST-TEE-S01"])
        self.assertNotIn("ignore_permissions", get_list.call_args.kwargs)

        with (
            patch.object(frappe, "get_list", return_value=[item]),
            patch.object(
                frappe,
                "get_all",
                return_value=[
                    frappe._dict(parent="TEST-TEE-S01", attribute="Size"),
                    frappe._dict(parent="TEST-TEE-S01", attribute="Colour"),
                ],
            ),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            self.assertRaises(frappe.ValidationError),
        ):
            ordering._validate_catalogue_items(["TEST-TEE-S01"])

    def test_same_request_returns_existing_order_without_recreating_it(self):
        existing = frappe._dict(
            name="SAL-ORD-TEST-0001",
            owner="test-salesperson@example.invalid",
            customer="TEST Retailer",
            docstatus=0,
            status="Draft",
            currency="INR",
            grand_total=499,
        )
        with (
            patch.object(ordering, "require_role"),
            patch.object(ordering, "_validate_customer", return_value="TEST Retailer"),
            patch.object(ordering, "_existing_order", return_value=existing),
            patch.object(ordering, "_items") as items,
        ):
            result = ordering.create_draft_sales_order(
                "TEST Retailer",
                [],
                "6d508e18-83cf-4dfe-9732-68bc7db84eb4",
            )
        items.assert_not_called()
        self.assertTrue(result["idempotent_replay"])

    def test_company_selection_is_permission_aware(self):
        with (
            patch.object(
                frappe.defaults, "get_user_default", return_value="TEST Company"
            ),
            patch.object(frappe, "get_list", return_value=["TEST Company"]) as query,
        ):
            self.assertEqual(ordering._validate_company(), "TEST Company")
        self.assertNotIn("ignore_permissions", query.call_args.kwargs)
