"""Unit and integration tests for customer return intake, quarantine isolation, and refurbishment pipeline."""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from warehouse_erp import returns
from warehouse_erp.returns import (
    complete_refurbishment,
    intake_customer_return,
    move_to_refurbishment,
)
from warehouse_erp.roles import ROLE_WAREHOUSE_MANAGER


class TestReturns(unittest.TestCase):
    def test_unauthorized_role_is_rejected_before_document_read(self):
        """User without warehouse manager role is rejected immediately."""
        with (
            patch.object(returns, "require_role", side_effect=frappe.PermissionError),
            patch.object(frappe.db, "exists") as exists,
            self.assertRaises(frappe.PermissionError),
        ):
            intake_customer_return(
                delivery_note="MAT-DN-0001",
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )
        exists.assert_not_called()

    def test_quarantine_warehouse_permission_enforced(self):
        """Manager lacking permission for target quarantine warehouse is denied."""
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=False),
            patch.object(returns, "assigned_warehouses", return_value=["Other Warehouse - TC"]),
            self.assertRaises(frappe.PermissionError),
        ):
            intake_customer_return(
                delivery_note="MAT-DN-0001",
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )

    def test_invalid_return_reason_is_rejected(self):
        """Unrecognized return reason string is rejected."""
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            self.assertRaises(frappe.ValidationError),
        ):
            intake_customer_return(
                delivery_note="MAT-DN-0001",
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Invalid Reason",
            )

    def test_invalid_quantity_is_rejected(self):
        """Negative or zero return quantity is rejected."""
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            self.assertRaises(frappe.ValidationError),
        ):
            intake_customer_return(
                delivery_note="MAT-DN-0001",
                item_code="TEST-SHIRT-M",
                quantity=-5,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )

    def test_non_submitted_delivery_note_cannot_be_returned(self):
        """Draft delivery note is rejected as return source."""
        orig_dn = frappe._dict(name="MAT-DN-0001", docstatus=0, is_return=0, items=[], check_permission=MagicMock())
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            self.assertRaises(frappe.ValidationError),
        ):
            intake_customer_return(
                delivery_note=orig_dn.name,
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )

    def test_return_cannot_target_another_return(self):
        """Return delivery note cannot itself be returned."""
        orig_dn = frappe._dict(name="MAT-DN-0001", docstatus=1, is_return=1, items=[], check_permission=MagicMock())
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            self.assertRaises(frappe.ValidationError),
        ):
            intake_customer_return(
                delivery_note=orig_dn.name,
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )

    def test_undelivered_item_cannot_be_returned(self):
        """Item not present in the original Delivery Note is rejected."""
        orig_item = frappe._dict(name="ROW-1", item_code="OTHER-ITEM", qty=5)
        orig_dn = frappe._dict(
            name="MAT-DN-0001",
            docstatus=1,
            is_return=0,
            items=[orig_item],
            check_permission=MagicMock(),
        )
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            self.assertRaises(frappe.ValidationError),
        ):
            intake_customer_return(
                delivery_note=orig_dn.name,
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )

    def test_excess_return_quantity_is_rejected(self):
        """Returning more than delivered minus previously returned is rejected."""
        orig_item = frappe._dict(name="ROW-1", item_code="TEST-SHIRT-M", qty=10, rate=500)
        orig_dn = frappe._dict(
            name="MAT-DN-0001",
            docstatus=1,
            is_return=0,
            items=[orig_item],
            customer="TEST Retailer",
            company="TEST Company",
            check_permission=MagicMock(),
        )
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=8.0),
            patch.object(frappe, "get_cached_value", return_value={}),
            self.assertRaisesRegex(frappe.ValidationError, "exceeds remaining returnable quantity"),
        ):
            intake_customer_return(
                delivery_note=orig_dn.name,
                item_code="TEST-SHIRT-M",
                quantity=3,  # 8 already returned out of 10, so max returnable is 2
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
            )

    def test_duplicate_serial_return_is_rejected(self):
        """Returning a serial number that was already returned is rejected."""
        orig_item = frappe._dict(name="ROW-1", item_code="TEST-SHIRT-M", qty=2, rate=500, serial_no="SN-001\nSN-002")
        orig_dn = frappe._dict(
            name="MAT-DN-0001",
            docstatus=1,
            is_return=0,
            items=[orig_item],
            customer="TEST Retailer",
            company="TEST Company",
            check_permission=MagicMock(),
        )
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", return_value=orig_dn),
            patch.object(returns, "_get_already_returned_quantity", return_value=1.0),
            patch.object(returns, "_get_already_returned_serials", return_value={"SN-001"}),
            patch.object(frappe, "get_cached_value", return_value={"has_serial_no": 1}),
            self.assertRaisesRegex(frappe.ValidationError, "has already been returned"),
        ):
            intake_customer_return(
                delivery_note=orig_dn.name,
                item_code="TEST-SHIRT-M",
                quantity=1,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Defective Stitching",
                serial_no="SN-001",
            )

    def test_intake_customer_return_success(self):
        """Successful return creates and submits native return Delivery Note and Return Quarantine."""
        orig_item = frappe._dict(name="ROW-1", item_code="TEST-SHIRT-M", qty=10, rate=500)
        orig_dn = frappe._dict(
            name="MAT-DN-0001",
            docstatus=1,
            is_return=0,
            items=[orig_item],
            customer="TEST Retailer",
            company="TEST Company",
            check_permission=MagicMock(),
        )
        return_dn_mock = frappe._dict(
            name="MAT-DN-RET-0001",
            items=[],
            append=MagicMock(),
            insert=MagicMock(),
            submit=MagicMock(),
            flags=frappe._dict(),
        )
        quarantine_mock = {"name": "RET-Q-2026-00001"}

        def mock_get_doc(doctype, name=None, *args, **kwargs):
            if doctype == "Delivery Note" or (isinstance(doctype, dict) and doctype.get("doctype") == "Delivery Note"):
                return orig_dn
            return frappe._dict(name=name, doctype=doctype)

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(returns, "_lock_delivery_note"),
            patch.object(frappe, "get_doc", side_effect=mock_get_doc),
            patch.object(returns, "_get_already_returned_quantity", return_value=2.0),
            patch.object(frappe, "get_cached_value", return_value={}),
            patch.object(frappe, "new_doc", return_value=return_dn_mock),
            patch("quality_erp.quality.record_return_quarantine", return_value=quarantine_mock),
            patch.object(frappe.db, "commit"),
        ):
            result = intake_customer_return(
                delivery_note=orig_dn.name,
                item_code="TEST-SHIRT-M",
                quantity=3,
                quarantine_warehouse="Quarantine - TC",
                return_reason="Fabric Fault",
                notes="Torn fabric near hemline",
            )

        self.assertEqual(result["return_delivery_note"], "MAT-DN-RET-0001")
        self.assertEqual(result["return_quarantine"], "RET-Q-2026-00001")
        self.assertEqual(result["status"], "Quarantined")
        return_dn_mock.insert.assert_called_once()
        return_dn_mock.submit.assert_called_once()
        self.assertEqual(return_dn_mock.is_return, 1)
        self.assertEqual(return_dn_mock.return_against, orig_dn.name)

    def test_move_to_refurbishment_requires_passing_quality_status(self):
        """Moving to refurbishment fails if inspection status is not 'Inspected - Passed Refurbishment'."""
        quarantine_row = [
            {
                "name": "RET-Q-0001",
                "inspection_status": "Quarantined",  # Still in quarantine, not yet inspected!
                "item_code": "TEST-SHIRT-M",
                "quantity": 2,
                "quarantine_warehouse": "Quarantine - TC",
            }
        ]
        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "sql", return_value=quarantine_row),
            self.assertRaisesRegex(frappe.ValidationError, "Only goods with passing quality inspection"),
        ):
            move_to_refurbishment("RET-Q-0001", "Refurbishment WIP - TC")

    def test_move_to_refurbishment_success_creates_and_submits_stock_entry(self):
        """Passed quarantine goods move to refurbishment WIP via native Material Transfer Stock Entry."""
        quarantine_row = [
            {
                "name": "RET-Q-0001",
                "inspection_status": "Inspected - Passed Refurbishment",
                "item_code": "TEST-SHIRT-M",
                "quantity": 2,
                "quarantine_warehouse": "Quarantine - TC",
            }
        ]
        rq_doc = frappe._dict(
            name="RET-Q-0001",
            inspection_status="Inspected - Passed Refurbishment",
            flags=frappe._dict(),
            save=MagicMock(),
        )
        se_mock = frappe._dict(
            name="STE-MAT-0001",
            append=MagicMock(),
            insert=MagicMock(),
            submit=MagicMock(),
            flags=frappe._dict(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "sql", return_value=quarantine_row),
            patch.object(frappe, "get_doc", return_value=rq_doc),
            patch.object(frappe.db, "get_value", return_value="TEST Company"),
            patch.object(frappe, "new_doc", return_value=se_mock),
            patch.object(frappe.db, "commit"),
        ):
            result = move_to_refurbishment("RET-Q-0001", "Refurbishment WIP - TC")

        self.assertEqual(result["stock_entry"], "STE-MAT-0001")
        self.assertEqual(result["status"], "In Refurbishment")
        se_mock.insert.assert_called_once()
        se_mock.submit.assert_called_once()
        self.assertEqual(se_mock.purpose, "Material Transfer")
        self.assertEqual(rq_doc.inspection_status, "In Refurbishment")
        self.assertEqual(rq_doc.refurbishment_warehouse, "Refurbishment WIP - TC")

    def test_complete_refurbishment_success_restocks_into_saleable_warehouse(self):
        """Completing refurbishment transfers stock into saleable warehouse via native Stock Entry."""
        quarantine_row = [
            {
                "name": "RET-Q-0001",
                "inspection_status": "In Refurbishment",
                "item_code": "TEST-SHIRT-M",
                "quantity": 2,
                "refurbishment_warehouse": "Refurbishment WIP - TC",
            }
        ]
        rq_doc = frappe._dict(
            name="RET-Q-0001",
            inspection_status="In Refurbishment",
            flags=frappe._dict(),
            save=MagicMock(),
        )
        se_mock = frappe._dict(
            name="STE-RESTOCK-0001",
            append=MagicMock(),
            insert=MagicMock(),
            submit=MagicMock(),
            flags=frappe._dict(),
        )

        with (
            patch.object(returns, "require_role"),
            patch.object(returns, "is_warehouse_admin", return_value=True),
            patch.object(frappe.db, "sql", return_value=quarantine_row),
            patch.object(frappe, "get_doc", return_value=rq_doc),
            patch.object(frappe.db, "get_value", return_value="TEST Company"),
            patch.object(frappe, "new_doc", return_value=se_mock),
            patch.object(frappe.db, "commit"),
        ):
            result = complete_refurbishment(
                quarantine_name="RET-Q-0001",
                target_saleable_warehouse="Finished Goods - TC",
                notes="Stitching reinforced and pressed",
            )

        self.assertEqual(result["restock_entry"], "STE-RESTOCK-0001")
        self.assertEqual(result["status"], "Restocked")
        se_mock.insert.assert_called_once()
        se_mock.submit.assert_called_once()
        self.assertEqual(se_mock.purpose, "Material Transfer")
        self.assertEqual(rq_doc.inspection_status, "Restocked")
        self.assertEqual(rq_doc.target_warehouse, "Finished Goods - TC")
        self.assertIn("Stitching reinforced and pressed", rq_doc.inspection_notes)
