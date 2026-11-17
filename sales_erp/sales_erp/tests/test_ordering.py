"""Stage 5 draft-order boundary and authoritative input tests."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import getdate

from sales_erp import ordering


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

    def test_order_directory_rejects_unauthorized_user_before_scope_or_query(self):
        with (
            patch.object(ordering, "require_role", side_effect=frappe.PermissionError),
            patch.object(ordering, "_order_customer_scope") as scope,
            patch.object(frappe, "get_all") as query,
            self.assertRaises(frappe.PermissionError),
        ):
            ordering.get_clothing_orders()
        scope.assert_not_called()
        query.assert_not_called()

    def test_order_directory_is_retailer_scoped_and_bounded(self):
        rows = [
            frappe._dict(name=f"SAL-ORD-TEST-{index:04}", customer="TEST Retailer")
            for index in range(51)
        ]
        with (
            patch.object(ordering, "require_role"),
            patch.object(
                ordering, "_order_customer_scope", return_value=["TEST Retailer"]
            ),
            patch.object(frappe, "get_all", return_value=rows) as query,
        ):
            result = ordering.get_clothing_orders(
                search="  TEST  ", state="draft", page=2, page_size=500
            )
        self.assertEqual(len(result["orders"]), 50)
        self.assertTrue(result["pagination"]["has_more"])
        self.assertEqual(result["pagination"]["page_size"], 50)
        self.assertEqual(query.call_args.kwargs["start"], 50)
        self.assertEqual(query.call_args.kwargs["limit"], 51)
        self.assertEqual(
            query.call_args.kwargs["filters"]["customer"],
            ["in", ["TEST Retailer"]],
        )
        self.assertEqual(query.call_args.kwargs["filters"]["docstatus"], 0)
        self.assertEqual(
            query.call_args.kwargs["filters"]["custom_clothing_request_id"],
            ["is", "set"],
        )

    def test_order_directory_with_no_assignments_does_not_query_orders(self):
        with (
            patch.object(ordering, "require_role"),
            patch.object(ordering, "_order_customer_scope", return_value=[]),
            patch.object(frappe, "get_all") as query,
        ):
            result = ordering.get_clothing_orders()
        query.assert_not_called()
        self.assertEqual(result["orders"], [])

    def test_order_detail_checks_scope_before_reading_items(self):
        with (
            patch.object(ordering, "require_role"),
            patch.object(frappe.db, "get_value", return_value=None) as order_query,
            patch.object(
                ordering, "_order_customer_scope", return_value=["TEST Retailer"]
            ),
            patch.object(frappe, "throw", side_effect=frappe.PermissionError),
            patch.object(frappe, "get_all") as items,
            self.assertRaises(frappe.PermissionError),
        ):
            ordering.get_clothing_order("SAL-ORD-TEST-0001")
        items.assert_not_called()
        self.assertEqual(
            order_query.call_args.args[1]["customer"], ["in", ["TEST Retailer"]]
        )

    def test_clothing_orders_page_replaces_native_sales_order_workspace_links(self):
        root = Path(__file__).parents[1]
        page = root / "sales_erp/page/clothing_orders/clothing_orders.js"
        self.assertTrue(page.exists())
        self.assertIn("get_clothing_orders", page.read_text())
        content = (
            root / "sales_erp/workspace/sales_erp/sales_erp.json"
        ).read_text()
        self.assertIn('"link_to": "clothing-orders"', content)
        self.assertNotIn('"link_to": "Sales Order"', content)

    def test_submit_rejects_unauthorized_user_before_order_lookup(self):
        with (
            patch.object(ordering, "require_role", side_effect=frappe.PermissionError),
            patch.object(ordering, "_validate_order_access") as access,
            self.assertRaises(frappe.PermissionError),
        ):
            ordering.submit_clothing_order("SAL-ORD-TEST-0001")
        access.assert_not_called()

    def test_submit_does_not_bypass_active_workflow(self):
        order = frappe._dict(name="SAL-ORD-TEST-0001", docstatus=0)
        with (
            patch.object(ordering, "require_role"),
            patch.object(ordering, "_validate_order_access", return_value=order),
            patch.object(
                ordering,
                "_active_sales_order_workflow",
                return_value="TEST Sales Approval",
            ),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(frappe.db, "sql") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            ordering.submit_clothing_order(order.name)
        self.assertFalse(
            any("for update" in str(call.args[0]).lower() for call in lock.call_args_list)
        )

    def test_submit_locks_rechecks_and_uses_native_controller(self):
        order = frappe._dict(name="SAL-ORD-TEST-0001", docstatus=0)
        document = MagicMock(
            name=order.name,
            customer="TEST Retailer",
            docstatus=1,
            status="To Deliver and Bill",
            currency="INR",
            grand_total=998,
        )
        with (
            patch.object(ordering, "require_role"),
            patch.object(
                ordering, "_validate_order_access", side_effect=[order, order]
            ) as access,
            patch.object(ordering, "_active_sales_order_workflow", return_value=None),
            patch.object(frappe.db, "sql") as lock,
            patch.object(frappe, "get_doc", return_value=document),
        ):
            result = ordering.submit_clothing_order(order.name)
        self.assertEqual(access.call_count, 2)
        self.assertIn("for update", lock.call_args.args[0].lower())
        self.assertTrue(document.flags.ignore_permissions)
        document.submit.assert_called_once_with()
        self.assertEqual(result["docstatus"], 1)

    def test_cancel_rejects_unauthorized_user_before_order_lookup(self):
        with (
            patch.object(ordering, "require_role", side_effect=frappe.PermissionError),
            patch.object(ordering, "_validate_order_access") as access,
            self.assertRaises(frappe.PermissionError),
        ):
            ordering.cancel_clothing_order("SAL-ORD-TEST-0001")
        access.assert_not_called()

    def test_cancel_does_not_bypass_active_workflow(self):
        order = frappe._dict(name="SAL-ORD-TEST-0001", docstatus=1)
        with (
            patch.object(ordering, "require_role"),
            patch.object(ordering, "_validate_order_access", return_value=order),
            patch.object(
                ordering,
                "_active_sales_order_workflow",
                return_value="TEST Sales Approval",
            ),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(frappe.db, "sql") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            ordering.cancel_clothing_order(order.name)
        self.assertFalse(
            any("for update" in str(call.args[0]).lower() for call in lock.call_args_list)
        )

    def test_cancel_locks_rechecks_and_uses_native_controller(self):
        order = frappe._dict(name="SAL-ORD-TEST-0001", docstatus=1)
        document = MagicMock(
            name=order.name,
            customer="TEST Retailer",
            docstatus=2,
            status="Cancelled",
            currency="INR",
            grand_total=998,
        )
        with (
            patch.object(ordering, "require_role"),
            patch.object(
                ordering, "_validate_order_access", side_effect=[order, order]
            ) as access,
            patch.object(ordering, "_active_sales_order_workflow", return_value=None),
            patch.object(frappe.db, "sql") as lock,
            patch.object(frappe, "get_doc", return_value=document),
        ):
            result = ordering.cancel_clothing_order(order.name)
        self.assertEqual(access.call_count, 2)
        self.assertIn("for update", lock.call_args.args[0].lower())
        self.assertTrue(document.flags.ignore_permissions)
        document.cancel.assert_called_once_with()
        self.assertEqual(result["docstatus"], 2)

    def test_order_dialog_exposes_only_server_authorized_lifecycle_actions(self):
        page = (
            Path(__file__).parents[1]
            / "sales_erp/page/clothing_orders/clothing_orders.js"
        ).read_text()
        self.assertIn("order.review.can_edit", page)
        self.assertIn('frappe.set_route("Form", "Sales Order", order.name)', page)
        self.assertIn("order.review.can_cancel", page)
        self.assertIn("cancel_clothing_order", page)
