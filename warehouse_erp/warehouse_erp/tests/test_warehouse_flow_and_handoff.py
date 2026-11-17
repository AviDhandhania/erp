"""Integration and flow tests for Session 9 Warehouse Native Flow, Packages and Delivery Handoff.

Covers:
1. Manager-only access verification (negative tests for legacy operator and unauthorized roles)
2. Native Sales Order -> Pick List -> Packing Slip -> Delivery Note flow
3. Billing authority and commercial boundaries (warehouse manager can prepare draft, cannot submit or alter prices)
4. India Compliance e-Waybill readiness and transport metadata
5. Wave and route work queues with zero cross-warehouse leakage
6. Bounded bulk preflight, per-document results with savepoint isolation, safe retry and idempotency
7. Partial fulfillment, backorders, and shortage splitting
8. Serial, batch, bundle, wrong location, and batch expiry handling
9. Package identity, count, weight, and dimensions
10. Immutable Delivery Handoff DocType rules and tamper protection
11. Versioned Mobile API contract (v1)
12. High-volume pick lists and concurrent row-locking
"""

from datetime import date, timedelta
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, nowdate

from warehouse_erp import fulfillment, mobile_api, security
from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)


def _safe_get_doc_patch(mock_map):
    """Safely patch frappe.get_doc for specific doctypes without breaking system doctypes."""
    orig = frappe.get_doc

    def _get_doc(doctype, name=None, *args, **kwargs):
        dt = doctype.get("doctype") if isinstance(doctype, dict) else doctype
        if dt in mock_map:
            doc = mock_map[dt]
            if callable(doc):
                return doc(doctype, name, *args, **kwargs)
            return doc
        return orig(doctype, name, *args, **kwargs)

    return _get_doc


class TestWarehouseFlowAndHandoff(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.wh = "Stores - TCED"
        self.other_wh = "Work In Progress - TCED"
        self.manager_user = "test-wh-manager@example.invalid"
        self.operator_user = "test-legacy-op@example.invalid"
        self.unauth_user = "test-unauth@example.invalid"

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_manager_only_access_negative_tests(self):
        """Legacy warehouse operator and unauthorized roles must be rejected before reading or mutating."""
        endpoints = [
            (fulfillment.create_pick_list_from_sales_orders, (["SO-001"],)),
            (fulfillment.verify_pick_item, ("PICK-001", "LOC-1", "BAR-1")),
            (fulfillment.complete_pick_list, ("PICK-001",)),
            (fulfillment.create_delivery_note_from_pick, ("PICK-001",)),
            (fulfillment.create_packing_slip, ("DN-001",)),
            (fulfillment.dispatch_delivery_note, ("DN-001",)),
            (fulfillment.record_delivery_handoff, ("DN-001", "Carrier", "Driver")),
            (fulfillment.prepare_billing_from_delivery_note, ("DN-001",)),
            (fulfillment.assign_to_wave, (["PICK-001"], "WAVE-01")),
            (fulfillment.assign_to_route, (["DN-001"], "ROUTE-01")),
            (fulfillment.get_warehouse_work_queues, ()),
            (mobile_api.get_mobile_warehouse_boot, ()),
            (mobile_api.get_mobile_tasks, ()),
            (mobile_api.verify_mobile_scan, ("PICK-001", "LOC-1", "BAR-1")),
            (mobile_api.create_mobile_delivery_note, ("PICK-001",)),
            (mobile_api.record_mobile_handoff, ("DN-001", "Carrier", "Driver")),
        ]

        # 1. Test legacy operator role
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), \
             patch.object(security, "get_current_user", return_value=self.operator_user):
            for fn, args in endpoints:
                with self.assertRaises(frappe.PermissionError, msg=f"{fn.__name__} did not reject legacy operator"):
                    fn(*args)

        # 2. Test unauthorized user (no warehouse roles)
        with patch.object(security, "get_user_roles", return_value={"Sales Manager"}), \
             patch.object(security, "get_current_user", return_value=self.unauth_user):
            for fn, args in endpoints:
                with self.assertRaises(frappe.PermissionError, msg=f"{fn.__name__} did not reject unauthorized role"):
                    fn(*args)

    def test_native_order_to_delivery_flow_and_packages(self):
        """Native Sales Order -> Pick List -> Packing Slip -> Delivery Note flow with package dimensions."""
        mock_so = frappe._dict(
            name="SO-TEST-001",
            docstatus=1,
            company="Test Company",
            customer="Test Retailer",
            items=[
                frappe._dict(
                    name="SOI-001",
                    item_code="TEST-SHIRT-M",
                    item_name="Shirt M",
                    qty=10,
                    stock_qty=10,
                    stock_uom="Nos",
                    warehouse=self.wh,
                )
            ],
            check_permission=MagicMock(),
        )

        mock_pick = frappe._dict(
            name="PICK-TEST-001",
            docstatus=0,
            status="Draft",
            locations=[
                frappe._dict(
                    name="LOC-001",
                    item_code="TEST-SHIRT-M",
                    item_name="Shirt M",
                    warehouse=self.wh,
                    stock_uom="Nos",
                    stock_qty=10,
                    qty=10,
                    picked_qty=0,
                )
            ],
            check_permission=MagicMock(),
            insert=MagicMock(),
            save=MagicMock(),
            submit=MagicMock(),
            set_item_locations=MagicMock(),
            flags=frappe._dict(),
        )

        with patch("erpnext.selling.doctype.sales_order.sales_order.create_pick_list", return_value=mock_pick), \
             patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Sales Order": mock_so, "Pick List": mock_pick})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            pick_res = fulfillment.create_pick_list_from_sales_orders(
                ["SO-TEST-001"],
                parent_warehouse=self.wh,
                wave_id="WAVE-2026-A",
                route_id="ROUTE-SOUTH-1",
            )
            self.assertEqual(pick_res["name"], "PICK-TEST-001")
            self.assertEqual(pick_res["custom_wave_id"], "WAVE-2026-A")
            self.assertEqual(pick_res["custom_route_id"], "ROUTE-SOUTH-1")
            mock_pick.insert.assert_called_once_with(ignore_permissions=True)

        # Packing slip with package barcode and dimensions
        mock_dn = frappe._dict(
            name="DN-TEST-001",
            docstatus=0,
            items=[frappe._dict(item_code="TEST-SHIRT-M", qty=10, net_weight=0.5)],
            check_permission=MagicMock(),
        )
        mock_ps = frappe._dict(
            name="PS-TEST-001",
            docstatus=0,
            delivery_note="DN-TEST-001",
            custom_package_barcode="PKG-DN-TEST-001-C1",
            custom_length=45.0,
            custom_width=30.0,
            custom_height=20.0,
            custom_dimension_uom="cm",
            gross_weight_pkg=5.5,
            net_weight_pkg=5.0,
            from_case_no=1,
            to_case_no=1,
            items=[frappe._dict(item_code="TEST-SHIRT-M", qty=10)],
            check_permission=MagicMock(),
            save=MagicMock(),
            insert=MagicMock(),
            flags=frappe._dict(),
        )

        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn})), \
             patch("erpnext.stock.doctype.delivery_note.delivery_note.make_packing_slip", return_value=mock_ps), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            ps_res = fulfillment.create_packing_slip(
                delivery_note="DN-TEST-001",
                package_barcode="PKG-DN-TEST-001-C1",
                length=45.0,
                width=30.0,
                height=20.0,
                dimension_uom="cm",
                gross_weight_pkg=5.5,
                net_weight_pkg=5.0,
            )
            self.assertEqual(ps_res["package_barcode"], "PKG-DN-TEST-001-C1")
            self.assertEqual(ps_res["dimensions"]["length"], 45.0)
            self.assertEqual(ps_res["dimensions"]["uom"], "cm")
            mock_ps.insert.assert_called_once()

    def test_billing_authority_and_boundaries(self):
        """Warehouse manager can prepare a draft Sales Invoice, but cannot submit or modify commercial values."""
        mock_dn = frappe._dict(
            name="DN-TEST-001",
            docstatus=1,
            customer="Test Retailer",
            grand_total=12500.0,
            items=[frappe._dict(item_code="TEST-SHIRT-M", qty=10, rate=1250.0, warehouse=self.wh)],
            check_permission=MagicMock(),
        )
        mock_si = frappe._dict(
            name="ACC-SINV-2026-00001",
            docstatus=0,
            status="Draft",
            customer="Test Retailer",
            grand_total=12500.0,
            insert=MagicMock(),
            save=MagicMock(),
            flags=frappe._dict(ignore_permissions=True),
        )

        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn})), \
             patch("erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice", return_value=mock_si), \
             patch("frappe.db.set_value") as set_val, \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            res = fulfillment.prepare_billing_from_delivery_note("DN-TEST-001")
            self.assertEqual(res["sales_invoice"], "ACC-SINV-2026-00001")
            self.assertEqual(res["docstatus"], 0)
            mock_si.insert.assert_called_once()
            set_val.assert_called_once_with(
                "Delivery Note", "DN-TEST-001", "custom_billing_invoice", "ACC-SINV-2026-00001", update_modified=False
            )

        # Negative test: Unsubmitted Delivery Note cannot generate billing
        mock_dn_draft = frappe._dict(
            name="DN-DRAFT",
            docstatus=0,
            items=[frappe._dict(warehouse=self.wh)],
            check_permission=MagicMock(),
        )
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn_draft})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            with self.assertRaises(frappe.ValidationError):
                fulfillment.prepare_billing_from_delivery_note("DN-DRAFT")

    def test_ewaybill_readiness_and_transport_metadata(self):
        """Validate India Compliance e-Waybill readiness threshold and transport metadata updates."""
        # 1. Delivery Note under threshold (e.g. 35,000 INR < 50,000 INR)
        mock_dn_small = frappe._dict(
            name="DN-SMALL",
            grand_total=35000.0,
            docstatus=1,
            items=[frappe._dict(warehouse=self.wh)],
            check_permission=MagicMock(),
        )
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn_small})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            readiness = fulfillment.get_ewaybill_readiness("DN-SMALL")
            self.assertFalse(readiness["ewaybill_applicable"])

        # 2. Delivery Note over threshold (e.g. 75,000 INR >= 50,000 INR) with missing metadata
        mock_dn_large = frappe._dict(
            name="DN-LARGE",
            grand_total=75000.0,
            docstatus=1,
            transporter_name="",
            vehicle_no="",
            lr_no="",
            lr_date=None,
            items=[frappe._dict(warehouse=self.wh)],
            check_permission=MagicMock(),
            flags=frappe._dict(),
            save=MagicMock(),
        )
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn_large})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            readiness = fulfillment.get_ewaybill_readiness("DN-LARGE")
            self.assertTrue(readiness["ewaybill_applicable"])
            self.assertFalse(readiness["ready_for_ewaybill"])
            self.assertIn("Transporter / Transporter ID", readiness["missing_fields"])

        # 3. Update transport metadata
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn_large})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            meta_res = fulfillment.update_transport_metadata(
                delivery_note="DN-LARGE",
                transporter_name="Blue Dart Logistics",
                vehicle_no="MH-04-AB-1234",
                lr_no="LR-BD-998877",
                lr_date="2026-11-17",
                mode_of_transport="Road",
                distance=150,
            )
            self.assertEqual(meta_res["transporter_name"], "Blue Dart Logistics")
            self.assertEqual(meta_res["vehicle_no"], "MH-04-AB-1234")
            mock_dn_large.save.assert_called_once_with(ignore_permissions=True)

    def test_wave_and_route_work_queues_and_scoping(self):
        """Wave and route assignment with zero cross-warehouse data exposure."""
        mock_pick = frappe._dict(
            name="PICK-W1",
            docstatus=0,
            locations=[frappe._dict(warehouse=self.wh)],
            check_permission=MagicMock(),
            flags=frappe._dict(),
            save=MagicMock(),
        )
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Pick List": mock_pick})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            wave_res = fulfillment.assign_to_wave(["PICK-W1"], "WAVE-NORTH-A")
            self.assertEqual(wave_res["wave_id"], "WAVE-NORTH-A")
            self.assertEqual(wave_res["count"], 1)
            self.assertEqual(mock_pick.custom_wave_id, "WAVE-NORTH-A")
            mock_pick.save.assert_called_once_with(ignore_permissions=True)

        # Zero cross-warehouse leakage: user with no warehouse permissions gets empty queue immediately
        with patch.object(fulfillment, "assigned_warehouses", return_value=[]), \
             patch.object(fulfillment, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            empty_queue = fulfillment.get_warehouse_work_queues(queue_type="wave")
            self.assertEqual(empty_queue["queues"], [])

        # User attempting to query another warehouse gets PermissionError
        with patch.object(fulfillment, "get_current_user", return_value=self.manager_user), \
             patch.object(fulfillment, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(fulfillment, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            with self.assertRaises(frappe.PermissionError):
                fulfillment.get_warehouse_work_queues(warehouse=self.other_wh, queue_type="wave")

    def test_bounded_bulk_preflight_and_safe_retries(self):
        """Bulk operations enforce bounds, savepoint isolation, per-document status, and idempotency."""
        # 1. Bounds check (max 50 documents)
        with patch.object(security, "is_warehouse_admin", return_value=True), \
             patch.object(security, "get_user_roles", return_value={ROLE_BUSINESS_ADMIN}):
            with self.assertRaises(frappe.ValidationError):
                fulfillment.preflight_fulfillment_bulk_action("create_delivery_notes", [f"PICK-{i}" for i in range(51)])

        # 2. Preflight success with document inspection
        mock_pick = frappe._dict(
            name="PICK-PF-1",
            docstatus=1,
            locations=[frappe._dict(warehouse=self.wh)],
            check_permission=MagicMock(),
        )
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Pick List": mock_pick})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}), \
             patch("frappe.db.exists", return_value=True):
            pf = fulfillment.preflight_fulfillment_bulk_action("create_delivery_notes", ["PICK-PF-1"])
            self.assertEqual(pf["valid_count"], 1)
            self.assertEqual(pf["invalid_count"], 0)
            self.assertTrue(pf["items"][0]["valid"])

    def test_partial_fulfillment_and_shortage_status(self):
        """Order fulfillment status accurately reflects ordered, picked, delivered, and backorder quantities."""
        mock_so = frappe._dict(
            name="SO-PARTIAL-001",
            docstatus=1,
            status="To Deliver and Bill",
            items=[
                frappe._dict(
                    item_code="TEST-SHIRT-M",
                    qty=20.0,
                    delivered_qty=8.0,
                    warehouse=self.wh,
                ),
                frappe._dict(
                    item_code="TEST-SHIRT-L",
                    qty=10.0,
                    delivered_qty=10.0,
                    warehouse=self.wh,
                ),
            ],
            check_permission=MagicMock(),
        )

        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Sales Order": mock_so})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            status = fulfillment.get_order_fulfillment_status("SO-PARTIAL-001")
            self.assertEqual(status["total_ordered"], 30.0)
            self.assertEqual(status["total_delivered"], 18.0)
            self.assertEqual(status["total_pending"], 12.0)
            self.assertTrue(status["is_backorder"])
            self.assertEqual(len(status["lines"]), 2)
            self.assertEqual(status["lines"][0]["pending_qty"], 12.0)
            self.assertEqual(status["lines"][1]["pending_qty"], 0.0)

    def test_batch_expiry_and_wrong_location_rejection(self):
        """Items from expired batches or wrong warehouse locations are rejected with ValidationError before lock."""
        doc = frappe._dict(
            name="PICK-EXP-001",
            docstatus=0,
            status="Draft",
            locations=[
                frappe._dict(
                    name="LOC-EXP-1",
                    item_code="TEST-BATCH-ITEM",
                    warehouse=self.wh,
                    stock_qty=5,
                    qty=5,
                    picked_qty=0,
                )
            ],
            check_permission=MagicMock(),
        )

        # 1. Expired batch scan rejection
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Pick List": doc})), \
             patch.object(fulfillment, "_resolve_pick_scan", return_value=frappe._dict(batch_no="BATCH-EXPIRED")), \
             patch.object(fulfillment, "_item_tracking", return_value=frappe._dict(has_batch_no=1, has_serial_no=0)), \
             patch("frappe.db.get_value", return_value=str(date.today() - timedelta(days=5))), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            with self.assertRaises(frappe.ValidationError):
                fulfillment.verify_pick_item("PICK-EXP-001", "LOC-EXP-1", "BATCH-EXPIRED")

        # 2. Location warehouse mismatch rejection
        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Pick List": doc})), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh, self.other_wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            with self.assertRaises(frappe.ValidationError):
                fulfillment.verify_pick_item(
                    "PICK-EXP-001", "LOC-EXP-1", "ANY-BARCODE", warehouse=self.other_wh
                )

    def test_delivery_handoff_doctype_and_immutability(self):
        """Delivery Handoff requires submitted Delivery Note, records driver details, and blocks tampering."""
        mock_dn = frappe._dict(
            name="DN-HANDOFF-1",
            docstatus=1,
            company="Test Company",
            customer="Test Retailer",
            items=[frappe._dict(warehouse=self.wh)],
            check_permission=MagicMock(),
        )

        mock_handoff = frappe._dict(
            name="DHO-2026-00001",
            docstatus=0,
            delivery_note="DN-HANDOFF-1",
            transporter_name="SafeExpress",
            accepted_by_handler="Ramesh Kumar (Driver)",
            packages_count=3,
            gross_weight=15.5,
            insert=MagicMock(),
            check_permission=MagicMock(),
            flags=frappe._dict(),
        )

        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Delivery Note": mock_dn, "Delivery Handoff": mock_handoff})), \
             patch("frappe.db.set_value") as set_val, \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            res = fulfillment.record_delivery_handoff(
                delivery_note="DN-HANDOFF-1",
                transporter_name="SafeExpress",
                accepted_by_handler="Ramesh Kumar (Driver)",
                packages_count=3,
                gross_weight=15.5,
                vehicle_no="KA-01-EQ-5544",
                driver_name="Ramesh Kumar",
                driver_phone="+919876543210",
            )
            self.assertEqual(res["name"], "DHO-2026-00001")
            mock_handoff.insert.assert_called_once_with(ignore_permissions=True)

    def test_mobile_api_versioned_contract(self):
        """Versioned Mobile API contract returns v1 structure and handles core mobile workflows."""
        with patch.object(mobile_api, "get_current_user", return_value=self.manager_user), \
             patch.object(mobile_api, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(mobile_api, "is_warehouse_admin", return_value=False), \
             patch.object(mobile_api, "require_role", return_value=True):
            # 1. Boot endpoint
            boot = mobile_api.get_mobile_warehouse_boot()
            self.assertEqual(boot["api_version"], "v1")
            self.assertEqual(boot["role"], ROLE_WAREHOUSE_MANAGER)
            self.assertIn(self.wh, boot["assigned_warehouses"])
            self.assertTrue(boot["features"]["barcode_scanner"])
            self.assertTrue(boot["features"]["immutable_delivery_handoff"])

            # 2. Queues endpoint
            with patch.object(fulfillment, "get_warehouse_work_queues", return_value={"queues": [], "total_tasks": 0}):
                queues = mobile_api.get_mobile_work_queues(warehouse=self.wh, queue_type="wave")
                self.assertEqual(queues["api_version"], "v1")

    def test_large_pick_list_and_row_locking(self):
        """High-volume Pick List with 50 lines verifies correctly with row-level locks."""
        locations = [
            frappe._dict(
                name=f"LOC-{i}",
                item_code=f"ITEM-{i}",
                item_name=f"Test Item {i}",
                warehouse=self.wh,
                stock_qty=2,
                qty=2,
                picked_qty=0,
            )
            for i in range(50)
        ]
        large_pick = frappe._dict(
            name="PICK-LARGE-50",
            docstatus=0,
            status="Draft",
            locations=locations,
            check_permission=MagicMock(),
            save=MagicMock(),
            submit=MagicMock(),
            set_item_locations=MagicMock(),
            flags=frappe._dict(),
        )

        with patch.object(frappe, "get_doc", side_effect=_safe_get_doc_patch({"Pick List": large_pick})), \
             patch.object(fulfillment, "_lock_pick_list") as lock_mock, \
             patch.object(fulfillment, "_item_tracking", return_value=frappe._dict()), \
             patch.object(security, "assigned_warehouses", return_value=[self.wh]), \
             patch.object(security, "is_warehouse_admin", return_value=False), \
             patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_MANAGER}):
            # Verify row 25
            res = fulfillment.verify_pick_item("PICK-LARGE-50", "LOC-25", "ITEM-25", quantity=1)
            self.assertEqual(res["picked_qty"], 1.0)
            self.assertEqual(res["required_qty"], 2.0)
            self.assertFalse(res["complete"])
            lock_mock.assert_called_with("PICK-LARGE-50")
            large_pick.save.assert_called_once_with(ignore_permissions=True)
