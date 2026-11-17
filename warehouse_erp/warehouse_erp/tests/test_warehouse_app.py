"""Unit and integration tests for Warehouse ERP."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase

from warehouse_erp.boot import restrict_warehouse_app_visibility
from warehouse_erp.fulfillment import (
    get_fulfillment_tasks,
)
from warehouse_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)
from warehouse_erp.security import (
    assigned_warehouses,
    delivery_note_has_permission,
    is_warehouse_admin,
    is_warehouse_manager,
    is_warehouse_operator,
    pick_list_has_permission,
)
from warehouse_erp.seed import (
    SEED_WAREHOUSE_MANAGER,
    SEED_WAREHOUSE_OPERATOR,
    seed_warehouse_data,
)


class TestWarehouseERP(FrappeTestCase):
    def setUp(self):
        super().setUp()
        from collections import defaultdict
        frappe.local.request_cache = defaultdict(dict)
        frappe.setup_module_map()
        frappe.set_user("Administrator")
        seed_warehouse_data()
        self.manager = SEED_WAREHOUSE_MANAGER

    def test_warehouse_user_app_isolation(self):
        """Warehouse manager must only see Warehouse ERP on the apps screen."""
        frappe.set_user(self.manager)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                    {"app_name": "insights", "on_apps_screen": True},
                    {"app_name": "india_compliance", "on_apps_screen": True},
                ]
            }
        )
        restrict_warehouse_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertEqual(visible, ["warehouse_erp"])

    def test_legacy_operator_has_no_app_access(self):
        """Unauthenticated or unassigned users have no access to Warehouse ERP."""
        frappe.set_user("Administrator")
        # Test with a user lacking warehouse manager role
        unprivileged = "test-unprivileged@example.invalid"
        if not frappe.db.exists("User", unprivileged):
            frappe.get_doc({
                "doctype": "User",
                "email": unprivileged,
                "first_name": "Unprivileged",
                "send_welcome_email": 0,
                "user_type": "System User",
            }).insert(ignore_permissions=True)

        frappe.set_user(unprivileged)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                ]
            }
        )
        restrict_warehouse_app_visibility(bootinfo)
        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertNotIn("warehouse_erp", visible)

    def test_warehouse_manager_app_isolation(self):
        """Warehouse manager must also only see Warehouse ERP on the apps screen."""
        frappe.set_user(self.manager)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                ]
            }
        )
        restrict_warehouse_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertEqual(visible, ["warehouse_erp"])

    def test_admin_sees_all_apps_in_warehouse_boot(self):
        """Administrator retains access to all apps."""
        frappe.set_user("Administrator")
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                ]
            }
        )
        restrict_warehouse_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertIn("warehouse_erp", visible)
        self.assertIn("sales_erp", visible)
        self.assertIn("quality_erp", visible)
        self.assertIn("erpnext", visible)

    def test_warehouse_role_checks(self):
        """Verify role helpers correctly recognize warehouse manager and deny non-manager."""
        self.assertFalse(is_warehouse_manager("test-non-manager@example.invalid"))
        self.assertFalse(is_warehouse_admin("test-non-manager@example.invalid"))

        self.assertTrue(is_warehouse_operator(self.manager))
        self.assertTrue(is_warehouse_manager(self.manager))
        self.assertFalse(is_warehouse_admin(self.manager))

        self.assertTrue(is_warehouse_admin("Administrator"))

    def test_assigned_warehouses_and_fulfillment_tasks(self):
        """Assigned warehouses and fulfillment tasks are retrievable for warehouse managers."""
        frappe.set_user(self.manager)
        whs = assigned_warehouses(self.manager)
        self.assertIsInstance(whs, list)
        self.assertTrue(len(whs) > 0)

        tasks = get_fulfillment_tasks(task_type="pick", state="all")
        self.assertIn("tasks", tasks)
        self.assertIn("pagination", tasks)

    def test_warehouse_runtime_scoping(self):
        """Warehouse manager only sees warehouse_erp and Warehouse ERP workspace."""
        from frappe.apps import get_apps
        from frappe.desk.desktop import get_workspaces

        frappe.set_user(self.manager)
        frappe.local.request_cache.clear()
        apps = [a["name"] for a in get_apps()]
        self.assertEqual(apps, ["warehouse_erp"])

        ws_pages = [w["name"] for w in get_workspaces()["pages"]]
        self.assertEqual(ws_pages, ["Warehouse ERP"])

    def test_operator_migration_to_manager(self):
        """Legacy operator user is cleanly migrated to manager and loses operator role."""
        from warehouse_erp.install import migrate_warehouse_operators_to_managers

        test_op = "legacy-op-test@example.invalid"
        frappe.set_user("Administrator")
        # Ensure legacy role exists temporarily for testing migration
        if not frappe.db.exists("Role", ROLE_WAREHOUSE_OPERATOR):
            frappe.get_doc({"doctype": "Role", "role_name": ROLE_WAREHOUSE_OPERATOR, "desk_access": 1, "is_custom": 1}).insert(ignore_permissions=True)

        if not frappe.db.exists("User", test_op):
            frappe.get_doc({
                "doctype": "User",
                "email": test_op,
                "first_name": "Legacy Op",
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": ROLE_WAREHOUSE_OPERATOR}],
            }).insert(ignore_permissions=True)
        else:
            op_doc = frappe.get_doc("User", test_op)
            op_doc.remove_roles(ROLE_WAREHOUSE_MANAGER)
            op_doc.add_roles(ROLE_WAREHOUSE_OPERATOR)

        # Before migration: has only operator role, cannot run fulfillment tasks
        frappe.set_user(test_op)
        frappe.local.request_cache.clear()
        with self.assertRaises(frappe.PermissionError):
            get_fulfillment_tasks(task_type="pick", state="all")

        # Run migration
        frappe.set_user("Administrator")
        migrate_warehouse_operators_to_managers()

        # After migration: user has manager role, operator role removed, legacy role deleted
        roles = set(frappe.get_roles(test_op))
        self.assertIn(ROLE_WAREHOUSE_MANAGER, roles)
        self.assertNotIn(ROLE_WAREHOUSE_OPERATOR, roles)
        self.assertFalse(frappe.db.exists("Role", ROLE_WAREHOUSE_OPERATOR))

    def test_cross_app_warehouse_access_denied(self):
        """Users outside warehouse roles cannot access warehouse fulfillment tasks."""
        for user in ["test-asm-south@example.invalid", "test-quality-inspector@example.invalid"]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            with self.assertRaises(frappe.PermissionError):
                get_fulfillment_tasks(task_type="pick", state="all")
