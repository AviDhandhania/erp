"""Warehouse ERP security and permission boundaries; no database or network needed."""
import unittest
from unittest.mock import patch
import frappe
from warehouse_erp import security
from warehouse_erp.roles import (
    ROLE_WAREHOUSE_OPERATOR,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_BUSINESS_ADMIN,
)


class TestWarehouseSecurity(unittest.TestCase):
    def test_serial_batch_bundle_mutation_is_limited_to_pick_submit_context(self):
        document = frappe._dict(
            voucher_type="Pick List", voucher_no="TEST-PICK-1"
        )
        with patch.object(
            security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}
        ):
            self.assertFalse(
                security.serial_batch_bundle_has_permission(
                    document, user="warehouse@example.invalid", ptype="create"
                )
            )
            frappe.flags.clothing_pick_bundle = document.voucher_no
            try:
                self.assertTrue(
                    security.serial_batch_bundle_has_permission(
                        document, user="warehouse@example.invalid", ptype="submit"
                    )
                )
                document.voucher_no = "OTHER-PICK"
                self.assertFalse(
                    security.serial_batch_bundle_has_permission(
                        document, user="warehouse@example.invalid", ptype="write"
                    )
                )
            finally:
                frappe.flags.pop("clothing_pick_bundle", None)

    def test_no_assignments_denies_warehouse_data(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_warehouses", return_value=[]):
            self.assertFalse(security.warehouse_has_permission("TEST-WAREHOUSE", user="test@example.invalid"))
            self.assertEqual(security.get_warehouse_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.get_pick_list_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.get_delivery_note_conditions("test@example.invalid"), "1=0")

    def test_mixed_warehouse_document_is_denied(self):
        doc = frappe._dict(doctype="Delivery Note", items=[frappe._dict(warehouse="TEST-A"), frappe._dict(warehouse="TEST-B")])
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_warehouses", return_value=["TEST-A"]):
            self.assertFalse(security.delivery_note_has_permission(doc, user="test@example.invalid"))

    def test_assigned_pick_list_requires_allowed_warehouses(self):
        doc = frappe._dict(doctype="Pick List", name="TEST-PICK", locations=[frappe._dict(warehouse="TEST-A")])
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_warehouses", return_value=["TEST-A"]):
            self.assertTrue(security.pick_list_has_permission(doc, user="test@example.invalid"))
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_warehouses", return_value=["TEST-B"]):
            self.assertFalse(security.pick_list_has_permission(doc, user="test@example.invalid"))

    def test_pick_list_checks_nested_parent_warehouse(self):
        doc = frappe._dict(
            doctype="Pick List",
            name="TEST-PICK",
            parent_warehouse="PARENT-WH",
            locations=[frappe._dict(warehouse="CHILD-WH")],
        )
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_warehouses", return_value=["CHILD-WH"]):
            # Allowed locations, but parent warehouse not in allowed -> rejected
            self.assertFalse(security.pick_list_has_permission(doc, user="test@example.invalid"))

        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_warehouses", return_value=["PARENT-WH", "CHILD-WH"]):
            self.assertTrue(security.pick_list_has_permission(doc, user="test@example.invalid"))

    def test_lock_pick_bundles_locks_bundles_for_update(self):
        from warehouse_erp import fulfillment
        document = frappe._dict(
            locations=[
                frappe._dict(serial_and_batch_bundle="BUNDLE-001"),
                frappe._dict(serial_and_batch_bundle="BUNDLE-002"),
                frappe._dict(serial_and_batch_bundle=None),
            ]
        )
        with patch.object(frappe.db, "sql") as sql:
            fulfillment._lock_pick_bundles(document)
            sql.assert_called_once()
            call_sql = sql.call_args[0][0]
            self.assertIn("tabSerial and Batch Bundle", call_sql)
            self.assertIn("FOR UPDATE", call_sql)
