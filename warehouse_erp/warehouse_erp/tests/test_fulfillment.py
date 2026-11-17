"""Stage 6 fulfillment boundary and UI contract tests."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from warehouse_erp import fulfillment


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
        document = frappe._dict(
            name="TEST-PICK-1",
            docstatus=docstatus,
            status="Draft" if docstatus == 0 else "Open",
            locations=[row],
            flags=frappe._dict(),
            check_permission=MagicMock(),
            save=MagicMock(),
            submit=MagicMock(),
            set_item_locations=MagicMock(),
            add_comment=MagicMock(),
        )
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
            patch.object(fulfillment, "_active_pick_list_workflow", return_value=None),
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
        page = root / "warehouse_erp/page/fulfillment_tasks/fulfillment_tasks.js"
        self.assertTrue(page.exists())
        workspace = json.loads(
            (
                root
                / "warehouse_erp/workspace/warehouse_erp/warehouse_erp.json"
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
            patch.object(fulfillment, "_scan_barcode", return_value=frappe._dict()),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.verify_pick_item(
                document.name, "TEST-LOCATION-1", "WRONG-BARCODE"
            )
        lock.assert_not_called()

    def test_pick_verification_prevents_over_picking_after_lock(self):
        before, _before_row = self.pick_document(picked_qty=2, stock_qty=3)
        after, _after_row = self.pick_document(picked_qty=2, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", side_effect=[before, after]),
            patch.object(fulfillment, "_item_tracking", return_value=frappe._dict()),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.verify_pick_item(
                before.name, "TEST-LOCATION-1", "TEST-SHIRT-M", 2
            )
        lock.assert_called_once_with(before.name)
        after.save.assert_not_called()

    def test_pick_verification_locks_rechecks_and_saves_native_pick_list(self):
        before, _before_row = self.pick_document(picked_qty=0, stock_qty=3)
        after, after_row = self.pick_document(picked_qty=0, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", side_effect=[before, after]),
            patch.object(fulfillment, "_item_tracking", return_value=frappe._dict()),
            patch.object(fulfillment, "_lock_pick_list") as lock,
        ):
            result = fulfillment.verify_pick_item(
                before.name, "TEST-LOCATION-1", "TEST-SHIRT-M", 2
            )
        lock.assert_called_once_with(before.name)
        self.assertEqual(after.check_permission.call_count, 1)
        self.assertEqual(after.scan_mode, 1)
        self.assertEqual(after_row.picked_qty, 2)
        after.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(result["picked_qty"], 2)
        self.assertFalse(result["complete"])

    def test_serialized_item_requires_a_serial_scan_before_lock(self):
        document, _row = self.pick_document(stock_qty=1)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(
                fulfillment,
                "_item_tracking",
                return_value=frappe._dict(has_serial_no=1, has_batch_no=0),
            ),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.verify_pick_item(
                document.name, "TEST-LOCATION-1", "TEST-SHIRT-M"
            )
        lock.assert_not_called()

    def test_serial_scan_replaces_preallocation_and_updates_native_fields(self):
        before, before_row = self.pick_document(stock_qty=1)
        after, after_row = self.pick_document(stock_qty=1)
        before_row.serial_no = "TEST-SERIAL-OLD"
        after_row.serial_no = "TEST-SERIAL-OLD"
        serial_scan = frappe._dict(
            item_code="TEST-SHIRT-M", serial_no="TEST-SERIAL-NEW"
        )
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", side_effect=[before, after]),
            patch.object(fulfillment, "_scan_barcode", return_value=serial_scan),
            patch.object(
                fulfillment,
                "_item_tracking",
                return_value=frappe._dict(has_serial_no=1, has_batch_no=0),
            ),
            patch.object(fulfillment, "_lock_pick_list"),
        ):
            result = fulfillment.verify_pick_item(
                before.name, before_row.name, serial_scan.serial_no
            )
        self.assertEqual(after_row.serial_no, serial_scan.serial_no)
        self.assertEqual(after_row.use_serial_batch_fields, 1)
        self.assertEqual(after_row.picked_qty, 1)
        after.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(result["scan_type"], "serial")

    def test_duplicate_serial_scan_is_rejected_before_lock(self):
        document, row = self.pick_document(picked_qty=1, stock_qty=2)
        row.serial_no = "TEST-SERIAL-1"
        scan = frappe._dict(item_code=row.item_code, serial_no="TEST-SERIAL-1")
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(fulfillment, "_scan_barcode", return_value=scan),
            patch.object(
                fulfillment,
                "_item_tracking",
                return_value=frappe._dict(has_serial_no=1, has_batch_no=0),
            ),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.verify_pick_item(document.name, row.name, scan.serial_no)
        lock.assert_not_called()

    def test_batch_scan_sets_native_batch_fields_and_quantity(self):
        before, before_row = self.pick_document(stock_qty=3)
        after, after_row = self.pick_document(stock_qty=3)
        scan = frappe._dict(item_code=before_row.item_code, batch_no="TEST-BATCH-1")
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", side_effect=[before, after]),
            patch.object(fulfillment, "_scan_barcode", return_value=scan),
            patch.object(
                fulfillment,
                "_item_tracking",
                return_value=frappe._dict(has_serial_no=0, has_batch_no=1),
            ),
            patch.object(fulfillment, "_lock_pick_list"),
        ):
            result = fulfillment.verify_pick_item(
                before.name, before_row.name, scan.batch_no, 2
            )
        self.assertEqual(after_row.batch_no, scan.batch_no)
        self.assertEqual(after_row.use_serial_batch_fields, 1)
        self.assertEqual(after_row.picked_qty, 2)
        after.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(result["scan_type"], "batch")

    def test_pick_completion_rejects_unauthorized_user_before_document_read(self):
        with (
            patch.object(fulfillment, "require_role", side_effect=frappe.PermissionError),
            patch.object(frappe, "get_doc") as query,
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.complete_pick_list("TEST-PICK-1")
        query.assert_not_called()

    def test_shortage_resolution_rejects_unauthorized_user_before_document_read(self):
        with (
            patch.object(fulfillment, "require_role", side_effect=frappe.PermissionError),
            patch.object(frappe, "get_doc") as query,
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.resolve_pick_shortage("TEST-PICK-1", "TEST no stock")
        query.assert_not_called()

    def test_shortage_resolution_requires_a_completely_unpicked_row(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(fulfillment, "_active_pick_list_workflow", return_value=None),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.resolve_pick_shortage(document.name, "TEST no stock")
        lock.assert_not_called()

    def test_shortage_resolution_locks_uses_native_reallocation_and_audits(self):
        document, picked_row = self.pick_document(picked_qty=1, stock_qty=1)
        unpicked_row = frappe._dict(
            name="TEST-LOCATION-2",
            item_code="TEST-SHIRT-L",
            warehouse="TEST Warehouse A",
            stock_uom="Nos",
            stock_qty=2,
            qty=2,
            picked_qty=0,
        )
        document.locations.append(unpicked_row)

        def reallocate(save=False):
            self.assertTrue(save)
            document.locations[1] = frappe._dict(
                name="TEST-LOCATION-3",
                item_code=unpicked_row.item_code,
                warehouse="TEST Warehouse B",
                stock_uom="Nos",
                stock_qty=2,
                qty=2,
                picked_qty=0,
            )

        document.set_item_locations.side_effect = reallocate
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(fulfillment, "_active_pick_list_workflow", return_value=None),
            patch.object(fulfillment, "_require_unpicked_rows") as eligible,
            patch.object(fulfillment, "_lock_pick_list") as lock,
        ):
            result = fulfillment.resolve_pick_shortage(
                document.name, "TEST shelf empty <check>"
            )
        lock.assert_called_once_with(document.name)
        self.assertEqual(eligible.call_count, 2)
        self.assertTrue(document.flags.ignore_permissions)
        document.set_item_locations.assert_called_once_with(save=True)
        self.assertEqual(document.locations[0].name, picked_row.name)
        self.assertEqual(result["unallocated_qty"], 0)
        comment = document.add_comment.call_args.args[1]
        self.assertIn("TEST shelf empty &lt;check&gt;", comment)

    def test_pick_completion_requires_every_row_before_lock(self):
        document, _row = self.pick_document(picked_qty=2, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(fulfillment, "_active_pick_list_workflow", return_value=None),
            patch.object(
                fulfillment,
                "_require_complete_pick",
                side_effect=frappe.ValidationError,
            ) as complete_check,
            patch.object(fulfillment, "_lock_pick_list") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.complete_pick_list(document.name)
        complete_check.assert_called_once_with(document)
        lock.assert_not_called()

    def test_pick_completion_does_not_bypass_active_workflow(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(
                fulfillment,
                "_active_pick_list_workflow",
                return_value="TEST Pick Approval",
            ),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.complete_pick_list(document.name)
        lock.assert_not_called()

    def test_pick_completion_locks_rechecks_submits_and_closes_assignments(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3)

        def submit():
            document.docstatus = 1
            document.status = "Open"

        document.submit.side_effect = submit
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document) as get_doc,
            patch.object(fulfillment, "_active_pick_list_workflow", return_value=None),
            patch.object(fulfillment, "_lock_pick_list") as lock,
            patch.object(fulfillment, "_close_pick_assignments") as close_assignments,
        ):
            result = fulfillment.complete_pick_list(document.name)
        self.assertGreaterEqual(get_doc.call_count, 2)
        lock.assert_called_once_with(document.name)
        self.assertGreaterEqual(document.check_permission.call_count, 2)
        self.assertTrue(document.flags.ignore_permissions)
        document.submit.assert_called_once_with()
        close_assignments.assert_called_once_with(document.name)
        self.assertEqual(result["docstatus"], 1)

    def test_pick_completion_clears_bundle_context_when_native_submit_fails(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3)
        document.submit.side_effect = frappe.ValidationError
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch.object(fulfillment, "_active_pick_list_workflow", return_value=None),
            patch.object(fulfillment, "_lock_pick_list"),
            patch.object(fulfillment, "_close_pick_assignments") as close_assignments,
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.complete_pick_list(document.name)
        self.assertIsNone(frappe.flags.get("clothing_pick_bundle"))
        close_assignments.assert_not_called()

    def test_create_delivery_note_from_pick_requires_submitted_pick_list(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3, docstatus=0)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.create_delivery_note_from_pick(document.name)

    def test_create_delivery_note_from_pick_enforces_warehouse_permissions(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3, docstatus=1)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch("warehouse_erp.security.is_warehouse_admin", return_value=False),
            patch("warehouse_erp.security.assigned_warehouses", return_value=["Other Warehouse"]),
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.create_delivery_note_from_pick(document.name)

    def test_create_delivery_note_from_pick_returns_existing_draft(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3, docstatus=1)
        existing_row = [{"name": "MAT-DN-EXISTING", "customer": "TEST Retailer", "docstatus": 0}]
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch("warehouse_erp.security.is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "sql", return_value=existing_row),
        ):
            result = fulfillment.create_delivery_note_from_pick(document.name)
        self.assertEqual(result["delivery_note"], "MAT-DN-EXISTING")
        self.assertEqual(result["docstatus"], 0)

    def test_create_delivery_note_from_pick_success(self):
        document, _row = self.pick_document(picked_qty=3, stock_qty=3, docstatus=1)
        dn_mock = frappe._dict(name="MAT-DN-0001", customer="TEST Customer", docstatus=0)
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=document),
            patch("warehouse_erp.security.is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "sql", return_value=[]),
            patch("erpnext.stock.doctype.pick_list.pick_list.create_delivery_note", return_value=dn_mock),
            patch.object(frappe.db, "commit"),
        ):
            result = fulfillment.create_delivery_note_from_pick(document.name)
        self.assertEqual(result["delivery_note"], "MAT-DN-0001")
        self.assertEqual(result["customer"], "TEST Customer")

    def test_dispatch_delivery_note_requires_draft(self):
        dn = frappe._dict(name="MAT-DN-0001", docstatus=1, items=[], check_permission=MagicMock())
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=dn),
            self.assertRaises(frappe.ValidationError),
        ):
            fulfillment.dispatch_delivery_note(dn.name)

    def test_dispatch_delivery_note_enforces_warehouse_permissions(self):
        item = frappe._dict(warehouse="TEST Warehouse")
        dn = frappe._dict(name="MAT-DN-0001", docstatus=0, items=[item], check_permission=MagicMock())
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=dn),
            patch.object(fulfillment, "_lock_delivery_note"),
            patch("warehouse_erp.security.is_warehouse_admin", return_value=False),
            patch("warehouse_erp.security.assigned_warehouses", return_value=["Other Warehouse"]),
            self.assertRaises(frappe.PermissionError),
        ):
            fulfillment.dispatch_delivery_note(dn.name)

    def test_dispatch_delivery_note_success_with_metadata_and_submit(self):
        item = frappe._dict(warehouse="TEST Warehouse")
        dn = frappe._dict(
            name="MAT-DN-0001",
            docstatus=0,
            status="Draft",
            items=[item],
            flags=frappe._dict(),
            check_permission=MagicMock(),
            submit=MagicMock(),
        )

        def submit():
            dn.docstatus = 1
            dn.status = "Completed"

        dn.submit.side_effect = submit
        with (
            patch.object(fulfillment, "require_role"),
            patch.object(frappe, "get_doc", return_value=dn),
            patch.object(fulfillment, "_lock_delivery_note") as lock,
            patch("warehouse_erp.security.is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "commit"),
        ):
            result = fulfillment.dispatch_delivery_note(
                delivery_note=dn.name,
                transporter_name="FastTrack Logistics",
                vehicle_no="KA-01-AB-1234",
                lr_no="LR-987654",
                lr_date="2026-11-17",
            )
        lock.assert_called_once_with(dn.name)
        self.assertEqual(dn.transporter_name, "FastTrack Logistics")
        self.assertEqual(dn.vehicle_no, "KA-01-AB-1234")
        self.assertEqual(dn.lr_no, "LR-987654")
        dn.submit.assert_called_once()
        self.assertEqual(result["docstatus"], 1)
        self.assertEqual(result["status"], "Completed")

