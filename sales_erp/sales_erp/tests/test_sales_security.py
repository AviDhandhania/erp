"""Sales ERP security and permission boundaries; no database or network needed."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from sales_erp import install, security
from sales_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_SALESPERSON,
    ROLE_SALES_MANAGER,
)


class TestSalesSecurity(unittest.TestCase):
    def test_operational_sales_roles_do_not_receive_native_sales_order_access(self):
        self.assertNotIn("Sales Order", install._role_doctypes(ROLE_SALESPERSON))
        self.assertNotIn("Sales Order", install._role_doctypes(ROLE_SALES_MANAGER))
        self.assertNotIn("Territory", install._role_doctypes(ROLE_SALESPERSON))
        self.assertIn("Customer Group", install._role_doctypes(ROLE_SALESPERSON))
        self.assertIn("Sales Order", install._role_doctypes(ROLE_BUSINESS_ADMIN))

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

    def test_other_erpnext_roles_are_left_to_native_permissions(self):
        with patch.object(security, "get_user_roles", return_value={"Sales User"}):
            self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "")
            self.assertTrue(security.customer_has_permission(SimpleNamespace(name="TEST-A"), user="test@example.invalid"))

    def test_clothing_manager_is_also_territory_scoped(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALES_MANAGER}), patch.object(security, "assigned_sales_territories", return_value=[]):
            self.assertFalse(security.has_retailer_access("TEST-A", "test@example.invalid"))
            self.assertEqual(security.get_salesperson_customer_conditions("test@example.invalid"), "1=0")
            self.assertEqual(security.sales_order_conditions("test@example.invalid"), "1=0")

    def test_sales_manager_retailer_access_is_territory_scoped(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALES_MANAGER}), patch.object(security, "assigned_sales_territories", return_value=["TEST North"]), patch.object(frappe.db, "get_value", return_value="TEST North"):
            self.assertTrue(security.has_retailer_access("TEST-A", "test@example.invalid"))
            self.assertTrue(security.customer_has_permission(SimpleNamespace(name="TEST-A"), user="test@example.invalid"))

    def test_asm_application_and_visit_records_remain_owner_scoped(self):
        with patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}), patch.object(security, "assigned_sales_territories", return_value=["TEST North"]):
            application_condition = security.retailer_application_conditions("asm@example.invalid")
            visit_condition = security.retailer_visit_conditions("asm@example.invalid")
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

    def test_stale_manual_user_permissions_do_not_grant_sales_access(self):
        """Native User Permissions alone must never grant Clothing ERP access."""
        from sales_erp import ordering
        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(ordering, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}),
            patch.object(ordering, "get_user_roles", return_value={ROLE_SALESPERSON}),
            patch.object(security, "assigned_documents", return_value=["STALE-CUSTOMER"]),
            patch.object(security, "assigned_sales_territories", return_value=[]),
            patch.object(ordering, "assigned_sales_territories", return_value=[]),
        ):
            self.assertFalse(security.has_retailer_access("STALE-CUSTOMER", "asm@example.invalid"))
            self.assertEqual(ordering._order_customer_scope(), [])

    def test_rsm_cannot_review_or_submit_order_outside_supervised_territories(self):
        """RSM cannot access or submit orders for retailers outside supervised territories."""
        from sales_erp import ordering
        with (
            patch.object(ordering, "is_clothing_admin", return_value=False),
            patch.object(ordering, "get_user_roles", return_value={ROLE_SALES_MANAGER}),
            patch.object(ordering, "assigned_sales_territories", return_value=["Supervised North"]),
            patch.object(frappe, "get_all", return_value=["Customer-North"]),
            # frappe.db.get_value returns None because Customer-South is not in Customer-North filter
            patch.object(frappe.db, "get_value", return_value=None),
        ):
            with self.assertRaises(frappe.PermissionError):
                ordering._validate_order_access("SO-SOUTH-001")

    def test_asm_sees_orders_for_every_retailer_in_active_territory(self):
        """An ASM sees orders for every retailer in their active territory."""
        from sales_erp import ordering
        with (
            patch.object(ordering, "is_clothing_admin", return_value=False),
            patch.object(ordering, "assigned_sales_territories", return_value=["Active Territory"]),
            patch.object(frappe, "get_all", return_value=["Shop-1", "Shop-2", "Shop-3"]),
        ):
            scope = ordering._order_customer_scope()
            self.assertEqual(scope, ["Shop-1", "Shop-2", "Shop-3"])

    def test_ended_or_reassigned_territories_lose_access_immediately(self):
        """Expired or ended supervisions immediately lose sales access."""
        with (
            patch.object(security, "get_current_user", return_value="asm@example.invalid"),
            patch.object(security, "get_user_roles", return_value={ROLE_SALESPERSON}),
            # DB returns no active rows because status is Ended or dates expired
            patch.object(frappe.db, "sql", return_value=[]),
        ):
            territories = security.assigned_sales_territories("asm@example.invalid")
            self.assertEqual(territories, [])
            self.assertFalse(security.has_retailer_access("Shop-1", "asm@example.invalid"))

    def test_administrators_retain_explicit_global_oversight(self):
        """Administrators have unrestricted scope across all retailers and orders."""
        from sales_erp import ordering
        with (
            patch.object(ordering, "is_clothing_admin", return_value=True),
        ):
            self.assertIsNone(ordering._order_customer_scope())
            self.assertTrue(security.has_retailer_access("Any-Shop", "Administrator"))
