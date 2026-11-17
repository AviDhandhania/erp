"""Suite authorization and role regression tests; no database or network needed."""
import unittest
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

    def test_guest_has_no_access(self):
        self.assertFalse(security.has_any_role(ROLE_SALESPERSON, "Guest"))

    def test_administrator_has_access(self):
        self.assertTrue(security.is_clothing_admin("Administrator"))

    def test_app_access_restricted_to_admin(self):
        with patch.object(security, "has_any_role", return_value=True):
            self.assertTrue(security.has_app_access())
        with patch.object(security, "has_any_role", return_value=False):
            self.assertFalse(security.has_app_access())

    def test_legacy_roles_are_purged_and_not_in_active_roles(self):
        from clothing_erp.roles import ALL_ROLES, LEGACY_ROLE_SALESPERSON, LEGACY_ROLE_SALES_MANAGER
        active_role_names = {r["role_name"] for r in ALL_ROLES}
        self.assertNotIn(LEGACY_ROLE_SALESPERSON, active_role_names)
        self.assertNotIn(LEGACY_ROLE_SALES_MANAGER, active_role_names)
        deleted_docs = []
        with (
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_all", return_value=["HR-1"]),
            patch.object(frappe, "delete_doc", side_effect=lambda dt, dn, **kw: deleted_docs.append((dt, dn))),
        ):
            install.remove_legacy_roles()
        self.assertIn(("Role", LEGACY_ROLE_SALESPERSON), deleted_docs)
        self.assertIn(("Role", LEGACY_ROLE_SALES_MANAGER), deleted_docs)
