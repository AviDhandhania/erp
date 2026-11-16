"""Unit and integration tests for Sales ERP."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase

from sales_erp.boot import restrict_sales_app_visibility
from sales_erp.roles import (
    ROLE_ASM,
    ROLE_BUSINESS_ADMIN,
    ROLE_RSM,
)
from sales_erp.seed import (
    SEED_ASM_NORTH,
    SEED_ASM_SOUTH,
    SEED_RSM,
    seed_catalogue,
)
from sales_erp.supervision import (
    assign_asm_supervision,
    get_active_supervising_rsm,
    get_supervised_asms,
    get_territory_supervision,
    is_active_supervisor,
    record_assignment_history,
    sales_role_user_query,
    validate_asm_user,
    validate_rsm_user,
)


class TestSalesERP(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        seed_catalogue()
        self.asm_south = SEED_ASM_SOUTH
        self.asm_north = SEED_ASM_NORTH
        self.rsm = SEED_RSM

    def test_asm_app_isolation(self):
        """ASM must only see Sales ERP on the apps screen."""
        frappe.set_user(self.asm_south)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                    {"app_name": "insights", "on_apps_screen": True},
                    {"app_name": "india_compliance", "on_apps_screen": True},
                ]
            }
        )
        restrict_sales_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertEqual(visible, ["sales_erp"])

    def test_rsm_app_isolation(self):
        """RSM must only see Sales ERP on the apps screen."""
        frappe.set_user(self.rsm)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                ]
            }
        )
        restrict_sales_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertEqual(visible, ["sales_erp"])

    def test_admin_sees_all_apps_in_sales_boot(self):
        """Administrator retains access to all apps."""
        frappe.set_user("Administrator")
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                ]
            }
        )
        restrict_sales_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertIn("sales_erp", visible)
        self.assertIn("warehouse_erp", visible)
        self.assertIn("quality_erp", visible)
        self.assertIn("erpnext", visible)

    def test_user_filtering_by_sales_roles(self):
        """Ensure search fields for ASM and RSM only return users with the exact roles."""
        frappe.set_user("Administrator")
        asm_results = sales_role_user_query("User", "", "name", 0, 20, {"role": ROLE_ASM})
        asm_users = [row[0] for row in asm_results]
        self.assertIn(self.asm_south, asm_users)
        self.assertNotIn("Administrator", asm_users)
        self.assertNotIn(self.rsm, asm_users)

        rsm_results = sales_role_user_query("User", "", "name", 0, 20, {"role": ROLE_RSM})
        rsm_users = [row[0] for row in rsm_results]
        self.assertIn(self.rsm, rsm_users)
        self.assertNotIn(self.asm_south, rsm_users)
        self.assertNotIn("Administrator", rsm_users)

    def test_validate_role_helpers(self):
        """Validate ASM and RSM role validation helpers."""
        # Does not raise for valid users
        validate_asm_user(self.asm_south)
        validate_rsm_user(self.rsm)

        with self.assertRaises(frappe.ValidationError):
            validate_asm_user(self.rsm)

        with self.assertRaises(frappe.ValidationError):
            validate_rsm_user(self.asm_south)

    def test_territory_supervision_and_relationship(self):
        """Verify ASM-RSM relationship and territory assignment."""
        supervision = get_territory_supervision("TEST South Sales Territory")
        self.assertIsNotNone(supervision)
        self.assertEqual(supervision.asm, self.asm_south)
        self.assertEqual(supervision.rsm, self.rsm)

        self.assertEqual(get_active_supervising_rsm(self.asm_south), self.rsm)
        self.assertTrue(is_active_supervisor(self.rsm, self.asm_south))
        self.assertIn(self.asm_south, get_supervised_asms(self.rsm))

    def test_retailer_assignment_history_records_territory(self):
        """Retailer assignment history must track territory and supervisory chain."""
        history = record_assignment_history(
            territory="TEST South Sales Territory",
            customer="TEST Catalogue Boutique",
            new_asm=self.asm_south,
            new_rsm=self.rsm,
            reason="Initial territory onboarding",
        )
        self.assertIsNotNone(history)
        doc = frappe.get_doc("Retailer Assignment History", history)
        self.assertEqual(doc.territory, "TEST South Sales Territory")
        self.assertEqual(doc.new_asm, self.asm_south)
        self.assertEqual(doc.new_rsm, self.rsm)
