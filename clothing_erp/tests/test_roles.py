"""Authorization regressions; no database or network needed."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from clothing_erp import security
from clothing_erp.roles import ROLE_SALESPERSON, ROLE_WAREHOUSE_OPERATOR, ROLE_SALES_MANAGER


class TestSecurity(unittest.TestCase):
    def test_guest_has_no_access(self):
        self.assertFalse(security.has_any_role(ROLE_SALESPERSON, "Guest"))

    def test_administrator_has_access(self):
        self.assertTrue(security.is_clothing_admin("Administrator"))

    def test_unassigned_salesperson_is_denied(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}), patch.object(security, "assigned_documents", return_value=[]):
            self.assertFalse(security.has_retailer_access("TEST-RETAILER", "test@example.invalid"))
            self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.sales_order_conditions("test@example.invalid"), "1=0")

    def test_assignment_is_required_for_each_retailer(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}), patch.object(security, "assigned_documents", return_value=["TEST-A"]):
            self.assertTrue(security.has_retailer_access("TEST-A", "test@example.invalid"))
            self.assertFalse(security.has_retailer_access("TEST-B", "test@example.invalid"))
            self.assertFalse(security.customer_has_permission(SimpleNamespace(name="TEST-B"), user="test@example.invalid"))

    def test_no_assignments_denies_warehouse_data(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_documents", return_value=[]):
            self.assertFalse(security.has_warehouse_access("TEST-WAREHOUSE", "test@example.invalid"))
            self.assertEqual(security.get_operator_warehouse_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.pick_list_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.delivery_note_conditions("test@example.invalid"), "(1=0)")

    def test_other_erpnext_roles_are_left_to_native_permissions(self):
        with patch.object(security, "get_user_roles", return_value={"Sales User"}):
            self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "")
            self.assertTrue(security.customer_has_permission(SimpleNamespace(name="TEST-A"), user="test@example.invalid"))

    def test_clothing_manager_uses_native_permissions(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON, ROLE_SALES_MANAGER}):
            self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "")

    def test_mixed_warehouse_document_is_denied(self):
        doc = frappe._dict(doctype="Delivery Note", items=[frappe._dict(warehouse="TEST-A"), frappe._dict(warehouse="TEST-B")])
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_documents", return_value=["TEST-A"]):
            self.assertFalse(security.operational_document_has_permission(doc, user="test@example.invalid"))

    def test_assigned_pick_list_also_requires_task_assignment(self):
        doc = frappe._dict(doctype="Pick List", name="TEST-PICK", locations=[frappe._dict(warehouse="TEST-A")])
        with patch.object(security, "get_user_roles", return_value={ROLE_WAREHOUSE_OPERATOR}), patch.object(security, "assigned_documents", return_value=["TEST-A"]), patch.object(security, "frappe") as framework:
            db = framework.db
            db.exists.return_value = None
            self.assertFalse(security.operational_document_has_permission(doc, user="test@example.invalid"))
            db.exists.return_value = "TEST-TASK"
            self.assertTrue(security.operational_document_has_permission(doc, user="test@example.invalid"))
