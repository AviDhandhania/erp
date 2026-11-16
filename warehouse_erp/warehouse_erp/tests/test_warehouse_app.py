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
        frappe.set_user("Administrator")
        seed_warehouse_data()
        self.operator = SEED_WAREHOUSE_OPERATOR
        self.manager = SEED_WAREHOUSE_MANAGER

    def test_warehouse_user_app_isolation(self):
        """Warehouse operator must only see Warehouse ERP on the apps screen."""
        frappe.set_user(self.operator)
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
        """Verify role helpers correctly recognize warehouse operator and manager."""
        self.assertTrue(is_warehouse_operator(self.operator))
        self.assertFalse(is_warehouse_manager(self.operator))
        self.assertFalse(is_warehouse_admin(self.operator))

        self.assertTrue(is_warehouse_operator(self.manager))
        self.assertTrue(is_warehouse_manager(self.manager))
        self.assertFalse(is_warehouse_admin(self.manager))

        self.assertTrue(is_warehouse_admin("Administrator"))

    def test_assigned_warehouses_and_fulfillment_tasks(self):
        """Assigned warehouses and fulfillment tasks are retrievable for warehouse users."""
        frappe.set_user(self.operator)
        whs = assigned_warehouses(self.operator)
        self.assertIsInstance(whs, list)
        self.assertTrue(len(whs) > 0)

        tasks = get_fulfillment_tasks(task_type="pick", state="all")
        self.assertIn("tasks", tasks)
        self.assertIn("pagination", tasks)
