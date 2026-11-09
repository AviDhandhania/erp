"""Stage 6 fulfillment boundary and UI contract tests."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from clothing_erp import fulfillment


class TestFulfillment(unittest.TestCase):
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
