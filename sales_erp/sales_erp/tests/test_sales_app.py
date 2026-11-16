"""Unit and integration tests for Sales ERP."""

import unittest
import frappe
from frappe.utils import flt
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
        from collections import defaultdict
        frappe.local.request_cache = defaultdict(dict)
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

    def test_retailer_application_request_info_and_resubmit_flow(self):
        """RSM requests more info -> status More Information Requested -> ASM resubmits -> RSM approves."""
        uid = frappe.generate_hash(length=6)
        frappe.set_user(self.asm_south)
        app_doc = frappe.get_doc({
            "doctype": "Retailer Application",
            "shop_name": f"TEST Info Flow Shop {uid}",
            "contact_person": "Flow Owner",
            "phone": f"987{uid[:6]}",
            "territory": "TEST South Sales Territory",
            "customer_group": "Buy & Sell",
            "salesperson": self.asm_south,
            "billing_address_line1": "123 South St",
            "billing_city": "Bengaluru",
            "billing_state": "Karnataka",
            "country": "India",
            "status": "Pending",
        }).insert()

        # 1. RSM requests more information
        frappe.set_user(self.rsm)
        from sales_erp.sales_erp.doctype.retailer_application.retailer_application import (
            approve,
            request_more_info,
            resubmit,
        )
        # Empty comment raises error
        with self.assertRaises(frappe.ValidationError):
            request_more_info(app_doc.name, "  ")

        res = request_more_info(app_doc.name, "Please upload latest shop photo and GSTIN")
        self.assertEqual(res["status"], "More Information Requested")
        app_doc.reload()
        self.assertEqual(app_doc.status, "More Information Requested")
        self.assertEqual(app_doc.requested_information, "Please upload latest shop photo and GSTIN")
        self.assertEqual(app_doc.info_requested_by, self.rsm)

        # 2. Cannot approve while in More Information Requested
        with self.assertRaises(frappe.ValidationError):
            approve(app_doc.name)

        # 3. ASM resubmits application
        frappe.set_user(self.asm_south)
        resubmit_res = resubmit(app_doc.name, "Added GSTIN in notes")
        self.assertEqual(resubmit_res["status"], "Resubmitted")
        app_doc.reload()
        self.assertEqual(app_doc.status, "Resubmitted")
        self.assertIn("Added GSTIN in notes", app_doc.notes or "")

        # 4. RSM approves resubmitted application
        frappe.set_user(self.rsm)
        approval_res = approve(app_doc.name)
        self.assertEqual(approval_res["status"], "Approved")
        app_doc.reload()
        self.assertEqual(app_doc.status, "Approved")
        self.assertTrue(bool(app_doc.customer))

    def test_retailer_application_approval_with_credit_limit(self):
        """RSM can approve retailer application with initial credit limit, propagating to Customer."""
        from sales_erp.sales_erp.doctype.retailer_application.retailer_application import approve

        uid = frappe.generate_hash(length=6)
        frappe.set_user(self.asm_south)
        app_doc = frappe.get_doc({
            "doctype": "Retailer Application",
            "shop_name": f"TEST Credit Limit Boutique {uid}",
            "contact_person": "Credit Limit Owner",
            "phone": f"988{uid[:6]}",
            "territory": "TEST South Sales Territory",
            "customer_group": "Buy & Sell",
            "salesperson": self.asm_south,
            "billing_address_line1": "456 South Avenue",
            "billing_city": "Bengaluru",
            "billing_state": "Karnataka",
            "country": "India",
            "status": "Pending",
        }).insert()

        # 1. Negative credit limit rejected
        frappe.set_user(self.rsm)
        with self.assertRaises(frappe.ValidationError):
            approve(app_doc.name, initial_credit_limit=-500)

        # 2. ASM cannot approve
        frappe.set_user(self.asm_south)
        with self.assertRaises(frappe.PermissionError):
            approve(app_doc.name, initial_credit_limit=50000)

        # 3. Supervised RSM successfully approves with initial credit limit
        frappe.set_user(self.rsm)
        res = approve(app_doc.name, initial_credit_limit=50000.0)
        self.assertEqual(res["status"], "Approved")
        self.assertEqual(res["initial_credit_limit"], 50000.0)

        app_doc.reload()
        self.assertEqual(app_doc.status, "Approved")
        self.assertEqual(flt(app_doc.initial_credit_limit), 50000.0)
        self.assertTrue(bool(app_doc.customer))

        cust_doc = frappe.get_doc("Customer", app_doc.customer)
        self.assertTrue(len(cust_doc.credit_limits) > 0)
        self.assertEqual(flt(cust_doc.credit_limits[0].credit_limit), 50000.0)

    def test_runtime_app_and_workspace_scoping(self):
        """Operational ASM and RSM users only receive sales_erp apps and workspaces."""
        from frappe.apps import get_apps
        from frappe.desk.desktop import get_workspaces

        for user in [self.asm_south, self.rsm]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            apps = [a["name"] for a in get_apps()]
            self.assertEqual(apps, ["sales_erp"])

            ws_pages = [w["name"] for w in get_workspaces()["pages"]]
            self.assertEqual(ws_pages, ["Sales ERP"])

        # Administrator sees all apps and all workspaces
        frappe.set_user("Administrator")
        frappe.local.request_cache.clear()
        admin_apps = [a["name"] for a in get_apps()]
        self.assertIn("sales_erp", admin_apps)
        self.assertIn("warehouse_erp", admin_apps)
        self.assertIn("quality_erp", admin_apps)
        self.assertIn("erpnext", admin_apps)

