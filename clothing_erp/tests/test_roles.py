"""Authorization regressions; no database or network needed."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from clothing_erp import install, security
from clothing_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_SALESPERSON,
    ROLE_SALES_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)


class TestSecurity(unittest.TestCase):
    def test_operational_sales_roles_do_not_receive_native_sales_order_access(self):
        self.assertNotIn("Sales Order", install._role_doctypes(ROLE_SALESPERSON))
        self.assertNotIn("Sales Order", install._role_doctypes(ROLE_SALES_MANAGER))
        self.assertNotIn("Territory", install._role_doctypes(ROLE_SALESPERSON))
        self.assertIn("Customer Group", install._role_doctypes(ROLE_SALESPERSON))
        self.assertIn("Sales Order", install._role_doctypes(ROLE_BUSINESS_ADMIN))

    def test_warehouse_roles_receive_read_only_tracked_stock_dependencies(self):
        doctypes = install._role_doctypes(ROLE_WAREHOUSE_OPERATOR)
        self.assertIn("Batch", doctypes)
        self.assertIn("Serial No", doctypes)
        self.assertIn("Serial and Batch Bundle", doctypes)
        self.assertNotIn("Stock Entry", doctypes)

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

    def test_guest_has_no_access(self):
        self.assertFalse(security.has_any_role(ROLE_SALESPERSON, "Guest"))

    def test_administrator_has_access(self):
        self.assertTrue(security.is_clothing_admin("Administrator"))

    def test_unassigned_salesperson_is_denied(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}), patch.object(security, "assigned_sales_territories", return_value=[]):
            self.assertFalse(security.has_retailer_access("TEST-RETAILER", "test@example.invalid"))
            self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.sales_order_conditions("test@example.invalid"), "1=0")

    def test_asm_access_is_required_for_each_retailer_territory(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}), patch.object(security, "assigned_sales_territories", return_value=["TEST North"]), patch.object(frappe.db, "get_value", side_effect=["TEST North", "TEST South", "TEST South"]):
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

    def test_clothing_manager_is_also_territory_scoped(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON, ROLE_SALES_MANAGER}):
            with patch.object(security, "assigned_sales_territories", return_value=[]):
                self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "1=0")

    def test_sales_manager_retailer_access_is_territory_scoped(self):
        with (
            patch.object(security, "get_user_roles", return_value={ROLE_SALES_MANAGER}),
            patch.object(security, "assigned_sales_territories", return_value=["TEST North"]),
            patch.object(frappe.db, "get_value", return_value="TEST South"),
        ):
            self.assertFalse(
                security.has_retailer_access("TEST Retailer", "manager@example.invalid")
            )

    def test_asm_application_and_visit_records_remain_owner_scoped(self):
        with patch.object(
            security, "get_user_roles", return_value={ROLE_SALESPERSON}
        ):
            application_condition = security.retailer_application_conditions(
                "asm@example.invalid"
            )
            visit_condition = security.retailer_visit_conditions(
                "asm@example.invalid"
            )
        self.assertIn("`owner` = 'asm@example.invalid'", application_condition)
        self.assertIn("`salesperson` = 'asm@example.invalid'", visit_condition)

    def test_rsm_application_records_are_territory_scoped(self):
        with (
            patch.object(
                security, "get_user_roles", return_value={ROLE_SALES_MANAGER}
            ),
            patch.object(
                security, "assigned_sales_territories", return_value=["TEST North"]
            ),
        ):
            condition = security.retailer_application_conditions(
                "rsm@example.invalid"
            )
        self.assertIn("`territory` in ('TEST North')", condition)

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

    def test_salesperson_cannot_access_user_management(self):
        doc = frappe._dict(doctype="User", name="test@example.invalid")
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}):
            self.assertFalse(security.user_has_permission(doc, user="test@example.invalid"))
            self.assertEqual(security.user_query_conditions("test@example.invalid"), "1=0")

    def test_rsm_cannot_access_user_management_but_admin_can(self):
        doc = frappe._dict(doctype="User", name="test@example.invalid")
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON, ROLE_SALES_MANAGER}):
            self.assertFalse(security.user_has_permission(doc, user="test@example.invalid"))
            self.assertEqual(security.user_query_conditions("test@example.invalid"), "1=0")
        self.assertTrue(security.user_has_permission(doc, user="Administrator"))

    def test_rsm_supervision_query_conditions_are_scoped_to_supervised_asms_in_territory(self):
        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_SALES_MANAGER}),
            patch.object(security, "get_current_user", return_value="rsm@example.invalid"),
        ):
            condition = security.asm_supervision_conditions("rsm@example.invalid")
            self.assertIn("`tabASM Supervision`.`rsm` = 'rsm@example.invalid'", condition)

    def test_asm_supervision_document_permissions_restrict_non_admin_edits(self):
        doc = frappe._dict(doctype="ASM Supervision", asm="asm@example.invalid", rsm="rsm@example.invalid")
        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_SALES_MANAGER}),
            patch.object(security, "get_current_user", return_value="rsm@example.invalid"),
        ):
            self.assertFalse(security.asm_supervision_has_permission(doc, "rsm@example.invalid", "write"))
            self.assertFalse(security.asm_supervision_has_permission(doc, "rsm@example.invalid", "create"))
