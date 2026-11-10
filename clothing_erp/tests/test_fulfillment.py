"""Stage 6 fulfillment boundary and UI contract tests."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from clothing_erp import fulfillment


class TestFulfillment(unittest.TestCase):
    def pick_document(self, picked_qty=0, stock_qty=3, docstatus=0):
        row = frappe._dict(
            name="TEST-LOCATION-1",
            item_code="TEST-SHIRT-M",
            item_name="TEST Shirt / M",
            warehouse="TEST Warehouse",
            stock_uom="Nos",
            stock_qty=stock_qty,
            qty=stock_qty,
            picked_qty=picked_qty,
        )
        document = MagicMock()
        document.name = "TEST-PICK-1"
        document.docstatus = docstatus
        document.locations = [row]
        return document, row

    def test_directory_rejects_unauthorized_user_before_query(self):
        with (
            patch.object(fulfillment, "require_role", side_effect=frappe.PermissionError),
            patch.object(frappe, "get_list") as query,
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.get_fulfillment_tasks()
        query.assert_not_called()

    def test_directory_uses_native_permissions_and_bounded_pagination(self):
        rows = [frappe._dict(name=f"TEST-PICK-{index}") for index in range(51)]
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_list", return_value=rows) as query,
        ):
            result = fulfillment.get_fulfillment_tasks(
                task_type="pick",
                state="draft",
                search="  TEST  ",
                page=2,
                page_size=500,
            )
        self.assertEqual(len(result["tasks"]), 50)
        self.assertTrue(result["pagination"]["has_more"])
        self.assertEqual(result["pagination"]["page_size"], 50)
        self.assertEqual(query.call_args.kwargs["start"], 50)
        self.assertEqual(query.call_args.kwargs["limit"], 51)
        self.assertEqual(query.call_args.kwargs["filters"]["docstatus"], 0)
        self.assertNotIn("ignore_permissions", query.call_args.kwargs)

    def test_detail_runs_native_document_permission_check(self):
        document = frappe._dict(
            name="TEST-PICK-1",
            company="TEST Company",
            status="Draft",
            docstatus=0,
            locations=[],
        )
        document.check_permission = MagicMock()
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
        ):
            result = fulfillment.get_fulfillment_task("pick", document.name)
        document.check_permission.assert_called_once_with("read")
        self.assertEqual(result["rows"], [])

    def test_detail_stops_when_native_permission_fails(self):
        document = MagicMock()
        document.check_permission.side_effect = frappe.PermissionError
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.get_fulfillment_task("delivery", "TEST-DN-1")

    def test_warehouse_workspace_uses_only_app_owned_fulfillment_page(self):
        root = Path(__file__).parents[1]
        page = root / "clothing_erp/page/fulfillment_tasks/fulfillment_tasks.js"
        self.assertTrue(page.exists())
        workspace = json.loads(
            (
                root
                / "clothing_erp/workspace/warehouse_operations/warehouse_operations.json"
            ).read_text()
        )
        links = workspace["shortcuts"] + workspace["links"]
        self.assertTrue(any(row.get("link_to") == "fulfillment-tasks" for row in links))
        self.assertFalse(
            any(
                row.get("link_to") in {"Pick List", "Delivery Note", "Stock Entry"}
                for row in links
            )
        )

    def test_pick_verification_rejects_unauthorized_user_before_document_read(self):
        with (
            patch.object(fulfillment, "require_role", side_effect=frappe.PermissionError),
            patch.object(frappe, "get_doc") as query,
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.verify_pick_item(
                "TEST-PICK-1", "TEST-LOCATION-1", "TEST-SHIRT-M"
            )
        query.assert_not_called()

    def test_pick_verification_rejects_wrong_barcode_before_lock(self):
        document, _row = self.pick_document()
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(frappe.db, "sql") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.verify_pick_item(
                document.name, "TEST-LOCATION-1", "WRONG-BARCODE"
            )
        self.assertFalse(
            any("for update" in str(call.args[0]).lower() for call in lock.call_args_list)
        )

    def test_pick_verification_prevents_over_picking_after_lock(self):
        before, _before_row = self.pick_document(picked_qty=2, stock_qty=3)
        after, _after_row = self.pick_document(picked_qty=2, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", side_effect=[before, after]),
            patch.object(frappe.db, "sql") as lock,
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.verify_pick_item(
                before.name, "TEST-LOCATION-1", "TEST-SHIRT-M", 2
            )
        self.assertTrue(
            any("for update" in str(call.args[0]).lower() for call in lock.call_args_list)
        )
        after.save.assert_not_called()

    def test_pick_verification_locks_rechecks_and_saves_native_pick_list(self):
        before, _before_row = self.pick_document(picked_qty=0, stock_qty=3)
        after, after_row = self.pick_document(picked_qty=0, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", side_effect=[before, after]),
            patch.object(frappe.db, "sql") as lock,
        ):
            result = fulfillment.verify_pick_item(
                before.name, "TEST-LOCATION-1", "TEST-SHIRT-M", 2
            )
        self.assertIn("for update", lock.call_args.args[0].lower())
        self.assertEqual(after.check_permission.call_count, 1)
        self.assertEqual(after.scan_mode, 1)
        self.assertEqual(after_row.picked_qty, 2)
        after.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(result["picked_qty"], 2)
        self.assertFalse(result["complete"])
