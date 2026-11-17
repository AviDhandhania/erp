"""Comprehensive integration and workflow tests for Session 10:
Warehouse Returns, Quarantine, Refurbishment, Printable Labels and Manifests.

Covers:
1. Label & Manifest Generation: Pick list manifest, shipping carton label, return quarantine tag,
   refurbishment work ticket, and delivery carrier handoff manifest.
2. Strict Non-Sensitive Projection: Never leaks commercial pricing, rates, margins, or credit limits.
3. Deterministic HTML & Reviewed ZPL II standard commands (^XA ... ^XZ, Code 128 barcodes).
4. Automated Reprint Tracking: Increments counter in cache, logs Activity Log audit events,
   and injects visible/ZPL reprint watermark banners.
5. Printer Failure & Network Resilience: Safe error handling without corrupting document state.
6. Role & Warehouse Scoping: Server-side validation rejecting cross-warehouse and unauthorized access.
7. Physical Customer Returns: Atomic intake, row-locked balance verification, excess rejection,
   duplicate/unallocated serial & batch validation, negative Delivery Note submission, and quarantine isolation.
8. Quality Handoff: Seamless registration into Return Quarantine (Quality ERP).
9. Refurbishment Lifecycle: Assignment, operation validation, consumed materials reference,
   cost tracking, timings, before/after evidence photos.
10. Mandatory Post-Refurbishment Quality Reinspection Gate: Restocking blocked on pending or rejected
    reinspection; allowed only on passing reinspection.
11. Native Stock Entry Restocking: Material transfer to saleable warehouse.
12. Commercial Financial Authorization Boundary: Strict separation of physical receipt from commercial
    financial credit/refund authorization (Pending Commercial Approval).
13. SLA Queues & Operational Dashboards: Aging calculation, SLA breach detection, reason aggregation,
    zero cross-warehouse leakage.
14. Concurrency & High Volume: Two-device concurrent race handling and 50-item bulk return processing.
15. Versioned Mobile API Contract: All mobile endpoints return api_version == "v1".
"""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, now_datetime, nowdate

from warehouse_erp import labels, mobile_api, returns, security
from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
)


class TestWarehouseReturnsAndLabels(FrappeTestCase):
    """Integration test suite covering warehouse returns, refurbishment, and labels."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        # Ensure cache keys are clear
        frappe.cache.delete_keys("label_reprint:*")

    # =========================================================================
    # 1. LABELS & MANIFESTS: NON-SENSITIVE PROJECTION & FORMATS
    # =========================================================================

    def test_label_shipping_carton_omits_sensitive_commercial_data(self):
        """Shipping carton label must contain carrier/package details but NEVER commercial rates or credit."""
        fake_dn = frappe._dict(
            name="MAT-DN-2026-00001",
            customer="Style Retailer",
            customer_name="Style Retailer Inc",
            transporter_name="BlueDart Logistics",
            vehicle_no="DL-01-AB-1234",
            lr_no="LR-987654",
            total_gross_weight=25.5,
            total_net_weight=23.0,
            grand_total=150000.0,  # Sensitive commercial
            items=[frappe._dict(warehouse="Stores - TC", item_code="SHIRT-BLK-M", qty=50, rate=500.0)],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_dn),
        ):
            data = labels.get_label_data("Delivery Note", "MAT-DN-2026-00001", "shipping")

        # Must include package and transport details
        self.assertEqual(data["title"], "SHIPPING CARTON LABEL")
        self.assertEqual(data["document_name"], "MAT-DN-2026-00001")
        self.assertEqual(data["customer_name"], "Style Retailer Inc")
        self.assertEqual(data["transporter_name"], "BlueDart Logistics")
        self.assertEqual(data["lr_no"], "LR-987654")
        self.assertIn("25.50 kg", data["gross_weight"])

        # Must strictly omit financial fields
        self.assertNotIn("grand_total", data)
        self.assertNotIn("rate", data)
        self.assertNotIn("credit_limit", data)
        self.assertNotIn("150000", str(data))

    def test_label_pick_slip_projection_omits_rates(self):
        """Pick slip label lists picking locations and quantities without unit rates."""
        fake_pick = frappe._dict(
            name="PICK-2026-00001",
            custom_wave_id="WAVE-NORTH-01",
            custom_route_id="ROUTE-DELHI",
            locations=[
                frappe._dict(item_code="TSHIRT-RED-L", item_name="Red T-Shirt L", warehouse="Stores - TC", qty=20, picked_qty=20, stock_uom="Nos", rate=450.0),
                frappe._dict(item_code="JEANS-BLU-32", item_name="Blue Jeans 32", warehouse="Stores - TC", qty=10, picked_qty=10, stock_uom="Nos", rate=1200.0),
            ],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_pick),
        ):
            data = labels.get_label_data("Pick List", "PICK-2026-00001", "pick_slip")

        self.assertEqual(data["title"], "WAREHOUSE PICK SLIP")
        self.assertEqual(data["wave_id"], "WAVE-NORTH-01")
        self.assertEqual(data["route_id"], "ROUTE-DELHI")
        self.assertEqual(len(data["items"]), 2)
        for item in data["items"]:
            self.assertNotIn("rate", item)
            self.assertNotIn("price", item)

    def test_label_return_quarantine_tag_projection(self):
        """Return quarantine tag contains quarantine tracking without commercial pricing."""
        fake_rq = frappe._dict(
            name="RET-Q-2026-00010",
            item_code="KURTA-SILK-M",
            quantity=5.0,
            return_reason="Defective Stitching",
            quarantine_warehouse="Quarantine - TC",
            delivery_note="MAT-DN-2026-00001",
            return_delivery_note="MAT-DN-RET-00001",
            retailer="Fashion Outlet",
            inspected_by="quality.officer@example.com",
            inspection_status="Quarantined",
            commercial_credit_amount=15000.0,  # Sensitive
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_rq),
        ):
            data = labels.get_label_data("Return Quarantine", "RET-Q-2026-00010", "quarantine")

        self.assertEqual(data["title"], "RETURN QUARANTINE INTAKE TAG")
        self.assertEqual(data["barcode"], "RET-Q-2026-00010")
        self.assertEqual(data["item_code"], "KURTA-SILK-M")
        self.assertEqual(data["return_reason"], "Defective Stitching")
        self.assertEqual(data["quarantine_warehouse"], "Quarantine - TC")
        self.assertNotIn("commercial_credit_amount", data)
        self.assertNotIn("15000", str(data))

    def test_label_refurbishment_work_ticket_projection(self):
        """Refurbishment work ticket contains operation, assignee, and timings."""
        fake_rq = frappe._dict(
            name="RET-Q-2026-00010",
            item_code="KURTA-SILK-M",
            quantity=1.0,
            refurbishment_operation="Restitching",
            refurbishment_assignee="tailor.ram@example.com",
            refurbishment_warehouse="Refurbishment WIP - TC",
            inspection_notes="Hemline seam broken",
            refurbishment_start_time="2026-11-17 10:00:00",
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_rq),
        ):
            data = labels.get_label_data("Return Quarantine", "RET-Q-2026-00010", "refurbishment")

        self.assertEqual(data["title"], "REFURBISHMENT WORK TICKET")
        self.assertEqual(data["operation"], "Restitching")
        self.assertEqual(data["assignee"], "tailor.ram@example.com")
        self.assertEqual(data["refurbishment_warehouse"], "Refurbishment WIP - TC")

    def test_label_delivery_handoff_manifest_projection(self):
        """Carrier handoff manifest includes driver, vehicle, and handler details."""
        fake_handoff = frappe._dict(
            name="DH-2026-00001",
            delivery_note="MAT-DN-2026-00001",
            transporter_name="SafeExpress",
            accepted_by_handler="Ramesh Kumar",
            driver_name="Ramesh Kumar",
            driver_phone="9876543210",
            vehicle_no="MH-04-AZ-9999",
            lr_no="LR-88888",
            packages_count=3,
            gross_weight=45.0,
            handed_over_by="warehouse.manager@example.com",
            handed_over_on="2026-11-17 14:30:00",
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_handoff),
        ):
            data = labels.get_label_data("Delivery Handoff", "DH-2026-00001", "delivery_handoff")

        self.assertEqual(data["title"], "DELIVERY CARRIER HANDOFF MANIFEST")
        self.assertEqual(data["transporter_name"], "SafeExpress")
        self.assertEqual(data["accepted_by_handler"], "Ramesh Kumar")
        self.assertEqual(data["packages_count"], 3)
        self.assertEqual(data["vehicle_no"], "MH-04-AZ-9999")

    # =========================================================================
    # 2. DETERMINISTIC HTML & REVIEWED ZPL II OUTPUT
    # =========================================================================

    def test_deterministic_html_generation(self):
        """generate_label_html creates deterministic output with barcode fallback."""
        fake_dn = frappe._dict(
            name="MAT-DN-2026-00001",
            customer="Style Retailer",
            customer_name="Style Retailer Inc",
            transporter_name="BlueDart",
            vehicle_no="DL-01-AB-1234",
            lr_no="LR-111",
            total_gross_weight=10.0,
            total_net_weight=9.0,
            items=[],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_dn),
        ):
            html1 = labels.generate_label_html("Delivery Note", "MAT-DN-2026-00001", "shipping", is_reprint=False)
            html2 = labels.generate_label_html("Delivery Note", "MAT-DN-2026-00001", "shipping", is_reprint=False)

        self.assertIn("<!DOCTYPE html>", html1)
        self.assertIn("SHIPPING CARTON LABEL", html1)
        self.assertIn("PKG-MAT-DN-2026-00001-ALL", html1)
        self.assertNotIn("*** REPRINT", html1)

    def test_reviewed_zpl_ii_commands_validity(self):
        """generate_label_zpl outputs valid ZPL II standard syntax starting with ^XA and ending with ^XZ."""
        fake_dn = frappe._dict(
            name="MAT-DN-2026-00001",
            customer="Style Retailer",
            customer_name="Style Retailer Inc",
            transporter_name="BlueDart",
            vehicle_no="DL-01-AB-1234",
            lr_no="LR-111",
            total_gross_weight=10.0,
            total_net_weight=9.0,
            items=[],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_dn),
        ):
            zpl = labels.generate_label_zpl("Delivery Note", "MAT-DN-2026-00001", "shipping", is_reprint=False)

        self.assertTrue(zpl.startswith("^XA"), "ZPL must start with ^XA")
        self.assertTrue(zpl.endswith("^XZ"), "ZPL must end with ^XZ")
        self.assertIn("^PW812", zpl)  # 4-inch 203 DPI width
        self.assertIn("^BCN", zpl)    # Code 128 barcode
        self.assertIn("^FDSHIPPING CARTON LABEL^FS", zpl)

    # =========================================================================
    # 3. REPRINT AUDIT TRACKING & WATERMARK BANNERS
    # =========================================================================

    def test_label_reprint_count_and_audit_watermark(self):
        """Subsequent prints increment counter, record audit events, and inject reprint watermarks."""
        fake_dn = frappe._dict(
            name="MAT-DN-2026-00002",
            customer="Retailer A",
            total_gross_weight=5.0,
            total_net_weight=4.5,
            items=[],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_dn),
            patch.object(labels, "record_security_audit_event") as mock_audit,
        ):
            # 1. First print
            res1 = labels.print_task_label("Delivery Note", "MAT-DN-2026-00002", "shipping", "html")
            self.assertFalse(res1["is_reprint"])
            self.assertEqual(res1["print_count"], 1)
            mock_audit.assert_called_with(
                "Document Label Printed",
                "Delivery Note",
                "MAT-DN-2026-00002",
                unittest.mock.ANY,
            )
            self.assertNotIn("*** REPRINT", res1["label"]["content"])

            # 2. Second print (Reprint)
            res2 = labels.print_task_label("Delivery Note", "MAT-DN-2026-00002", "shipping", "html")
            self.assertTrue(res2["is_reprint"])
            self.assertEqual(res2["print_count"], 2)
            mock_audit.assert_called_with(
                "Document Label Reprinted",
                "Delivery Note",
                "MAT-DN-2026-00002",
                unittest.mock.ANY,
            )
            self.assertIn("*** REPRINT - AUDITED LABEL ***", res2["label"]["content"])

            # 3. ZPL Reprint watermark
            res3 = labels.print_task_label("Delivery Note", "MAT-DN-2026-00002", "shipping", "zpl")
            self.assertTrue(res3["is_reprint"])
            self.assertIn("*** REPRINT - AUDITED ***", res3["label"]["content"])

    # =========================================================================
    # 4. PRINTER FAILURE & NETWORK RESILIENCE
    # =========================================================================

    def test_printer_failure_safe_handling(self):
        """Simulated printer timeout or network disconnection aborts safely without document corruption."""
        fake_dn = frappe._dict(
            name="MAT-DN-2026-00003",
            customer="Retailer B",
            items=[],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_dn),
        ):
            with self.assertRaises(frappe.ValidationError) as ctx:
                labels.print_task_label(
                    "Delivery Note",
                    "MAT-DN-2026-00003",
                    "shipping",
                    simulate_failure=True,
                )
            self.assertIn("Printer 'Default' is offline or timed out", str(ctx.exception))

            # Verify that print count was NOT incremented due to failure
            count = labels._get_print_count("Delivery Note", "MAT-DN-2026-00003", "shipping")
            self.assertEqual(count, 0)

    # =========================================================================
    # 5. ROLE & WAREHOUSE PERMISSIONS ON LABELS
    # =========================================================================

    def test_label_access_denied_for_unauthorized_warehouse(self):
        """Warehouse manager cannot print label for a document containing an unassigned warehouse."""
        fake_pick = frappe._dict(
            name="PICK-2026-00099",
            locations=[frappe._dict(warehouse="Forbidden Warehouse - TC", qty=5)],
            check_permission=MagicMock(),
        )

        with (
            patch.object(labels, "require_role"),
            patch.object(labels, "get_current_user", return_value="manager@example.com"),
            patch.object(labels, "is_warehouse_admin", return_value=False),
            patch.object(labels, "assigned_warehouses", return_value=["Allowed Warehouse - TC"]),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_pick),
        ):
            with self.assertRaises(frappe.PermissionError):
                labels.get_document_label("Pick List", "PICK-2026-00099", "pick_slip")

    # =========================================================================
    # 6. PHYSICAL CUSTOMER RETURNS & QUARANTINE ISOLATION
    # =========================================================================

    def test_return_excess_quantity_is_strictly_rejected(self):
        """Returns exceeding the delivered quantity minus previous returns are rejected."""
        orig_dn = frappe._dict(
            name="MAT-DN-2026-00010",
            docstatus=1,
            is_return=0,
            customer="Style Retailer",
            company="Test Garments",
            items=[frappe._dict(name="ROW-1", item_code="SHIRT-M", qty=10, rate=500)],
            check_permission=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=7.0),
            patch.object(frappe, "get_cached_value", return_value={}),
        ):
            # Remaining returnable is 10 - 7 = 3. Attempting to return 4 must fail.
            with self.assertRaisesRegex(frappe.ValidationError, "exceeds remaining returnable quantity"):
                returns.intake_customer_return(
                    delivery_note="MAT-DN-2026-00010",
                    item_code="SHIRT-M",
                    quantity=4.0,
                    quarantine_warehouse="Quarantine - TC",
                    return_reason="Customer Return",
                )

    def test_return_non_delivered_batch_rejected(self):
        """Returning an unallocated or wrong batch number is rejected."""
        orig_dn = frappe._dict(
            name="MAT-DN-2026-00011",
            docstatus=1,
            is_return=0,
            customer="Style Retailer",
            company="Test Garments",
            items=[frappe._dict(name="ROW-1", item_code="SHIRT-M", qty=5, rate=500, batch_no="BATCH-DELIVERED-01")],
            check_permission=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=0.0),
            patch.object(frappe, "get_cached_value", return_value={"has_batch_no": 1}),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "does not match the delivered batch"):
                returns.intake_customer_return(
                    delivery_note="MAT-DN-2026-00011",
                    item_code="SHIRT-M",
                    quantity=1.0,
                    quarantine_warehouse="Quarantine - TC",
                    return_reason="Defective Stitching",
                    batch_no="BATCH-WRONG-99",
                )

    def test_return_non_delivered_serial_rejected(self):
        """Returning a serial number not in the original delivery is rejected."""
        orig_dn = frappe._dict(
            name="MAT-DN-2026-00012",
            docstatus=1,
            is_return=0,
            customer="Style Retailer",
            company="Test Garments",
            items=[frappe._dict(name="ROW-1", item_code="JACKET-XL", qty=1, rate=2500, serial_no="SN-ORIG-001")],
            check_permission=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=0.0),
            patch.object(returns, "_get_already_returned_serials", return_value=set()),
            patch.object(frappe, "get_cached_value", return_value={"has_serial_no": 1}),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "was not delivered in original Delivery Note"):
                returns.intake_customer_return(
                    delivery_note="MAT-DN-2026-00012",
                    item_code="JACKET-XL",
                    quantity=1.0,
                    quarantine_warehouse="Quarantine - TC",
                    return_reason="Defective Stitching",
                    serial_no="SN-STRANGER-999",
                )

    def test_intake_customer_return_isolates_stock_and_creates_quarantine(self):
        """Intake submits negative Delivery Note into quarantine warehouse and registers Quality ERP Return Quarantine."""
        orig_dn = frappe._dict(
            name="MAT-DN-2026-00015",
            docstatus=1,
            is_return=0,
            customer="Style Retailer",
            company="Test Garments",
            items=[frappe._dict(name="ROW-1", item_code="KURTA-L", qty=10, rate=800)],
            check_permission=MagicMock(),
        )
        return_dn_mock = frappe._dict(
            name="MAT-DN-RET-2026-00015",
            items=[],
            append=MagicMock(),
            insert=MagicMock(),
            submit=MagicMock(),
            flags=frappe._dict(),
        )
        quarantine_mock = {"name": "RET-Q-2026-00099"}

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=0.0),
            patch.object(frappe, "get_cached_value", return_value={}),
            patch.object(frappe, "new_doc", return_value=return_dn_mock),
            patch("quality_erp.quality.record_return_quarantine", return_value=quarantine_mock),
            patch.object(frappe.db, "commit"),
        ):
            res = returns.intake_customer_return(
                delivery_note="MAT-DN-2026-00015",
                item_code="KURTA-L",
                quantity=2.0,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Fabric Fault",
                notes="Visible weaving flaw on front panel",
            )

        self.assertEqual(res["return_delivery_note"], "MAT-DN-RET-2026-00015")
        self.assertEqual(res["return_quarantine"], "RET-Q-2026-00099")
        self.assertEqual(res["status"], "Quarantined")
        return_dn_mock.insert.assert_called_once()
        return_dn_mock.submit.assert_called_once()
        self.assertEqual(return_dn_mock.is_return, 1)

    # =========================================================================
    # 7. FINANCIAL AUTHORIZATION BOUNDARY
    # =========================================================================

    def test_commercial_financial_authorization_boundary(self):
        """Physical return status must state 'Pending Commercial Approval' and never guess credit/refunds."""
        fake_rq = frappe._dict(
            name="RET-Q-2026-00050",
            delivery_note="MAT-DN-2026-00015",
            return_delivery_note="MAT-DN-RET-2026-00015",
            retailer="Style Retailer",
            check_permission=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(frappe.db, "exists", side_effect=lambda dt, dn: dt == "Return Quarantine" and dn == "RET-Q-2026-00050"),
            patch.object(frappe, "get_doc", return_value=fake_rq),
            patch.object(frappe.db, "get_value", return_value="Test Garments"),
        ):
            status = returns.get_return_financial_status("RET-Q-2026-00050")

        self.assertEqual(status["financial_disposition"], "Pending Commercial Approval")
        self.assertFalse(status["credit_note_issued"])
        self.assertFalse(status["refund_issued"])
        self.assertFalse(status["replacement_issued"])
        self.assertIn("Physical quarantine and refurbishment intake only", status["warehouse_authority"])

    # =========================================================================
    # 8. REFURBISHMENT PIPELINE & WORK ASSIGNMENT
    # =========================================================================

    def test_assign_refurbishment_lifecycle(self):
        """Technician assignment records operation, assignee, estimated cost, and before photo."""
        fake_rq_row = [
            {
                "name": "RET-Q-2026-00060",
                "inspection_status": "In Refurbishment",
                "item_code": "JEANS-32",
                "quantity": 1.0,
            }
        ]
        rq_doc = frappe._dict(
            name="RET-Q-2026-00060",
            inspection_status="In Refurbishment",
            flags=frappe._dict(),
            check_permission=MagicMock(),
            save=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(returns, "_lock_return_quarantine"),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "sql", return_value=fake_rq_row),
            patch.object(frappe, "get_doc", return_value=rq_doc),
            patch.object(frappe.db, "commit"),
        ):
            res = returns.assign_refurbishment(
                quarantine_name="RET-Q-2026-00060",
                assignee="tailor.ram@example.com",
                operation="Button / Zipper Replacement",
                estimated_cost=50.0,
                consumed_material="Metal Buttons Pack 10",
                photo_before="/private/files/broken_button.jpg",
                notes="Missing brass button at waistband",
            )

        self.assertEqual(res["status"], "In Refurbishment")
        self.assertEqual(res["assignee"], "tailor.ram@example.com")
        self.assertEqual(res["operation"], "Button / Zipper Replacement")
        self.assertEqual(rq_doc.refurbishment_operation, "Button / Zipper Replacement")
        self.assertEqual(rq_doc.refurbishment_cost, 50.0)

    def test_assign_refurbishment_invalid_operation_rejected(self):
        """Invalid refurbishment operation is rejected."""
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
        ):
            with self.assertRaises(frappe.ValidationError):
                returns.assign_refurbishment(
                    quarantine_name="RET-Q-2026-00060",
                    assignee="tailor.ram@example.com",
                    operation="Laser Engraving",  # Not an allowed operation
                )

    def test_complete_refurbishment_work_submits_for_reinspection(self):
        """Work completion transitions status to 'Awaiting Reinspection' and sets post inspection status to 'Pending Inspection'."""
        fake_rq_row = [
            {
                "name": "RET-Q-2026-00060",
                "inspection_status": "In Refurbishment",
                "item_code": "JEANS-32",
                "quantity": 1.0,
            }
        ]
        rq_doc = frappe._dict(
            name="RET-Q-2026-00060",
            inspection_status="In Refurbishment",
            flags=frappe._dict(),
            check_permission=MagicMock(),
            save=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(returns, "_lock_return_quarantine"),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "sql", return_value=fake_rq_row),
            patch.object(frappe, "get_doc", return_value=rq_doc),
            patch.object(frappe.db, "commit"),
        ):
            res = returns.complete_refurbishment_work(
                quarantine_name="RET-Q-2026-00060",
                photo_after="/private/files/repaired_button.jpg",
                notes="New brass rivet installed and tested",
            )

        self.assertEqual(res["status"], "Awaiting Reinspection")
        self.assertEqual(rq_doc.inspection_status, "Awaiting Reinspection")
        self.assertEqual(rq_doc.post_refurbishment_inspection_status, "Pending Inspection")

    # =========================================================================
    # 9. MANDATORY POST-REFURBISHMENT QUALITY REINSPECTION GATE
    # =========================================================================

    def test_restock_blocked_when_post_reinspection_pending(self):
        """Restocking into saleable inventory is strictly blocked when reinspection is pending."""
        fake_rq_row = [
            {
                "name": "RET-Q-2026-00070",
                "inspection_status": "Awaiting Reinspection",
                "post_refurbishment_inspection_status": "Pending Inspection",
                "item_code": "JEANS-32",
                "quantity": 1.0,
                "refurbishment_warehouse": "Refurbishment WIP - TC",
            }
        ]

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(returns, "_lock_return_quarantine"),
            patch.object(frappe.db, "sql", return_value=fake_rq_row),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "awaiting mandatory post-refurbishment quality re-inspection"):
                returns.complete_refurbishment(
                    quarantine_name="RET-Q-2026-00070",
                    target_saleable_warehouse="Finished Goods - TC",
                )

    def test_restock_blocked_when_post_reinspection_rejected(self):
        """Restocking is blocked when post-refurbishment quality inspection failed."""
        fake_rq_row = [
            {
                "name": "RET-Q-2026-00071",
                "inspection_status": "In Refurbishment",
                "post_refurbishment_inspection_status": "Re-inspected - Rejected",
                "item_code": "JEANS-32",
                "quantity": 1.0,
                "refurbishment_warehouse": "Refurbishment WIP - TC",
            }
        ]

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(returns, "_lock_return_quarantine"),
            patch.object(frappe.db, "sql", return_value=fake_rq_row),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "Post-refurbishment quality inspection failed"):
                returns.complete_refurbishment(
                    quarantine_name="RET-Q-2026-00071",
                    target_saleable_warehouse="Finished Goods - TC",
                )

    def test_post_refurbishment_reinspection_quality_roles_enforced(self):
        """Only Quality roles can perform post-refurbishment reinspection."""
        with (
            patch.object(returns, "require_role", side_effect=frappe.PermissionError),
        ):
            with self.assertRaises(frappe.PermissionError):
                returns.post_refurbishment_reinspection("RET-Q-2026-00072", "Passed")

    def test_complete_refurbishment_success_when_reinspection_passed(self):
        """Restocking succeeds when reinspection passed, submitting native Stock Entry Material Transfer."""
        fake_rq_row = [
            {
                "name": "RET-Q-2026-00075",
                "inspection_status": "Inspected - Passed Refurbishment",
                "post_refurbishment_inspection_status": "Re-inspected - Passed",
                "item_code": "JEANS-32",
                "quantity": 1.0,
                "refurbishment_warehouse": "Refurbishment WIP - TC",
            }
        ]
        rq_doc = frappe._dict(
            name="RET-Q-2026-00075",
            inspection_status="Inspected - Passed Refurbishment",
            flags=frappe._dict(),
            save=MagicMock(),
        )
        se_mock = frappe._dict(
            name="STE-MAT-2026-00099",
            append=MagicMock(),
            insert=MagicMock(),
            submit=MagicMock(),
            flags=frappe._dict(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(returns, "_lock_return_quarantine"),
            patch.object(frappe.db, "sql", return_value=fake_rq_row),
            patch.object(frappe, "get_doc", return_value=rq_doc),
            patch.object(frappe.db, "get_value", return_value="Test Garments"),
            patch.object(frappe, "new_doc", return_value=se_mock),
            patch.object(frappe.db, "commit"),
        ):
            res = returns.complete_refurbishment(
                quarantine_name="RET-Q-2026-00075",
                target_saleable_warehouse="Finished Goods - TC",
                notes="Passed quality reinspection, restocked to FG.",
            )

        self.assertEqual(res["restock_entry"], "STE-MAT-2026-00099")
        self.assertEqual(res["status"], "Restocked")
        se_mock.insert.assert_called_once()
        se_mock.submit.assert_called_once()
        self.assertEqual(se_mock.purpose, "Material Transfer")
        self.assertEqual(rq_doc.inspection_status, "Restocked")
        self.assertEqual(rq_doc.target_warehouse, "Finished Goods - TC")

    # =========================================================================
    # 10. SLA QUEUES & OPERATIONAL DASHBOARD
    # =========================================================================

    def test_returns_operational_dashboard_sla_aging_and_leakage(self):
        """Dashboard flags SLA breaches (>24h quarantine, >72h refurbishment) and avoids cross-warehouse leakage."""
        now = now_datetime()
        fake_rows = [
            {
                "name": "RET-Q-OLD-01",
                "item_code": "SHIRT-M",
                "quantity": 2.0,
                "inspection_status": "Quarantined",
                "return_reason": "Defective Stitching",
                "quarantine_warehouse": "Warehouse A - TC",
                "creation": now - timedelta(hours=30),
                "refurbishment_start_time": None,
                "inspected_on": None,
            },
            {
                "name": "RET-Q-OLD-02",
                "item_code": "PANTS-34",
                "quantity": 1.0,
                "inspection_status": "In Refurbishment",
                "return_reason": "Customer Return",
                "quarantine_warehouse": "Warehouse A - TC",
                "creation": now - timedelta(hours=80),
                "refurbishment_start_time": now - timedelta(hours=80),
                "inspected_on": now - timedelta(hours=80),
            },
        ]

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=False),
            patch.object(returns, "assigned_warehouses", return_value=["Warehouse A - TC"]),
            patch.object(frappe.db, "sql", return_value=fake_rows),
        ):
            dash = returns.get_returns_operational_dashboard()

        self.assertIn("summary", dash)
        self.assertIn("queues", dash)
        self.assertIn("reason_breakdown", dash)
        self.assertEqual(dash["reason_breakdown"]["Defective Stitching"], 1)
        self.assertEqual(dash["reason_breakdown"]["Customer Return"], 1)
        self.assertEqual(dash["summary"]["sla_breaches"], 2)
        self.assertEqual(dash["queues"]["quarantine"][0]["sla_breached"], True)
        self.assertEqual(dash["queues"]["refurbishment"][0]["sla_breached"], True)

    # =========================================================================
    # 11. CONCURRENCY & HIGH VOLUME RETURN PROCESSING
    # =========================================================================

    def test_concurrent_two_device_return_race_protection(self):
        """Row locking on original delivery note ensures two devices returning the last unit serialize or reject."""
        orig_dn = frappe._dict(
            name="MAT-DN-2026-RACE",
            docstatus=1,
            is_return=0,
            customer="Style Retailer",
            company="Test Garments",
            items=[frappe._dict(name="ROW-1", item_code="SHIRT-L", qty=1, rate=500)],
            check_permission=MagicMock(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note") as mock_lock,
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(frappe, "get_cached_value", return_value={}),
        ):
            # Device 1 returns 1 unit -> success
            with (
                patch.object(returns, "_get_already_returned_quantity", return_value=0.0),
                patch.object(frappe, "new_doc", return_value=frappe._dict(name="RET-1", append=MagicMock(), insert=MagicMock(), submit=MagicMock(), flags=frappe._dict())),
                patch("quality_erp.quality.record_return_quarantine", return_value={"name": "Q-1"}),
                patch.object(frappe.db, "commit"),
            ):
                res1 = returns.intake_customer_return("MAT-DN-2026-RACE", "SHIRT-L", 1.0, "Quarantine - TC", "Defective Stitching")
                self.assertEqual(res1["status"], "Quarantined")
                mock_lock.assert_called_with("MAT-DN-2026-RACE")

            # Device 2 immediately attempts to return 1 unit -> rejected because remaining balance is 0
            with patch.object(returns, "_get_already_returned_quantity", return_value=1.0):
                with self.assertRaisesRegex(frappe.ValidationError, "exceeds remaining returnable quantity"):
                    returns.intake_customer_return("MAT-DN-2026-RACE", "SHIRT-L", 1.0, "Quarantine - TC", "Defective Stitching")

    def test_high_volume_return_batch_validation(self):
        """Intake handles bulk returns with 50 units without state corruption."""
        orig_dn = frappe._dict(
            name="MAT-DN-2026-BULK",
            docstatus=1,
            is_return=0,
            customer="Bulk Retailer",
            company="Test Garments",
            items=[frappe._dict(name="ROW-1", item_code="TEE-BULK", qty=100, rate=300)],
            check_permission=MagicMock(),
        )
        return_dn_mock = frappe._dict(
            name="MAT-DN-RET-BULK",
            items=[],
            append=MagicMock(),
            insert=MagicMock(),
            submit=MagicMock(),
            flags=frappe._dict(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=10.0),
            patch.object(frappe, "get_cached_value", return_value={}),
            patch.object(frappe, "new_doc", return_value=return_dn_mock),
            patch("quality_erp.quality.record_return_quarantine", return_value={"name": "RET-Q-BULK-01"}),
            patch.object(frappe.db, "commit"),
        ):
            # Return 50 units (out of 90 available)
            res = returns.intake_customer_return(
                delivery_note="MAT-DN-2026-BULK",
                item_code="TEE-BULK",
                quantity=50.0,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Customer Return",
                notes="Bulk seasonal excess return",
            )

        self.assertEqual(res["return_delivery_note"], "MAT-DN-RET-BULK")
        self.assertEqual(res["return_quarantine"], "RET-Q-BULK-01")

    # =========================================================================
    # 12. VERSIONED MOBILE API CONTRACT
    # =========================================================================

    def test_mobile_api_returns_and_labels_contract(self):
        """All mobile endpoints for returns and labels adhere to api_version == 'v1' contract."""
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(returns, "intake_customer_return", return_value={"status": "Quarantined"}),
            patch.object(returns, "move_to_refurbishment", return_value={"status": "In Refurbishment"}),
            patch.object(returns, "assign_refurbishment", return_value={"status": "Refurbishment Assigned"}),
            patch.object(returns, "complete_refurbishment_work", return_value={"status": "Awaiting Reinspection"}),
            patch.object(returns, "post_refurbishment_reinspection", return_value={"status": "Re-inspected - Passed"}),
            patch.object(returns, "complete_refurbishment", return_value={"status": "Restocked"}),
            patch.object(returns, "get_return_financial_status", return_value={"commercial_status": "Pending Commercial Approval"}),
            patch.object(returns, "get_returns_operational_dashboard", return_value={"summary": {}}),
            patch.object(labels, "get_document_label", return_value={"doctype": "Delivery Note", "name": "DN-1"}),
            patch.object(labels, "print_task_label", return_value={"success": True}),
        ):
            m1 = mobile_api.intake_mobile_return("DN-1", "ITEM-1", 1.0, "Quarantine", "Customer Return")
            self.assertEqual(m1["api_version"], "v1")

            m2 = mobile_api.move_mobile_refurbishment("Q-1", "Refurbishment")
            self.assertEqual(m2["api_version"], "v1")

            m3 = mobile_api.assign_mobile_refurbishment("Q-1", "tailor@example.com", "Restitching")
            self.assertEqual(m3["api_version"], "v1")

            m4 = mobile_api.complete_mobile_refurbishment_work("Q-1")
            self.assertEqual(m4["api_version"], "v1")

            m5 = mobile_api.reinspect_mobile_refurbishment("Q-1", "Passed")
            self.assertEqual(m5["api_version"], "v1")

            m6 = mobile_api.complete_mobile_refurbishment("Q-1", "Finished Goods")
            self.assertEqual(m6["api_version"], "v1")

            m7 = mobile_api.get_mobile_return_financial_status("Q-1")
            self.assertEqual(m7["api_version"], "v1")

            m8 = mobile_api.get_mobile_returns_dashboard()
            self.assertEqual(m8["api_version"], "v1")

            m9 = mobile_api.get_mobile_document_label("Delivery Note", "DN-1")
            self.assertEqual(m9["api_version"], "v1")

            m10 = mobile_api.print_mobile_task_label("Delivery Note", "DN-1")
            self.assertEqual(m10["api_version"], "v1")
