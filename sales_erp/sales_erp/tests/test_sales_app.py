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
        import random
        uid = frappe.generate_hash(length=6)
        phone = f"98{random.randint(10000000, 99999999)}"
        frappe.set_user(self.asm_south)
        app_doc = frappe.get_doc({
            "doctype": "Retailer Application",
            "shop_name": f"TEST Info Flow Shop {uid}",
            "contact_person": "Flow Owner",
            "phone": phone,
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

        import random
        uid = frappe.generate_hash(length=6)
        phone = f"98{random.randint(10000000, 99999999)}"
        frappe.set_user(self.asm_south)
        app_doc = frappe.get_doc({
            "doctype": "Retailer Application",
            "shop_name": f"TEST Credit Limit Boutique {uid}",
            "contact_person": "Credit Limit Owner",
            "phone": phone,
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

    def test_cross_app_sales_access_denied(self):
        """Users outside sales roles cannot approve, request info, or resubmit retailer applications."""
        from sales_erp.sales_erp.doctype.retailer_application.retailer_application import (
            approve,
            request_more_info,
            resubmit,
        )

        import random
        uid = frappe.generate_hash(length=6)
        phone = f"98{random.randint(10000000, 99999999)}"
        frappe.set_user(self.asm_south)
        app_doc = frappe.get_doc({
            "doctype": "Retailer Application",
            "shop_name": f"TEST Cross App App {uid}",
            "contact_person": "Cross Owner",
            "phone": phone,
            "territory": "TEST South Sales Territory",
            "customer_group": "Buy & Sell",
            "salesperson": self.asm_south,
            "billing_address_line1": "789 Boundary Rd",
            "billing_city": "Bengaluru",
            "billing_state": "Karnataka",
            "country": "India",
            "status": "Pending",
        }).insert()

        for user in ["test-warehouse-operator@example.invalid", "test-quality-inspector@example.invalid"]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            with self.assertRaises(frappe.PermissionError):
                approve(app_doc.name)

            with self.assertRaises(frappe.PermissionError):
                request_more_info(app_doc.name, "Attempt unauthorized comment")

            with self.assertRaises(frappe.PermissionError):
                resubmit(app_doc.name, "Attempt unauthorized resubmit")

    def test_asm_retailer_visit_supervisory_workflow(self):
        """ASM visit automatically resolves supervising RSM and allows RSM review."""
        from sales_erp.sales_erp.doctype.retailer_visit.retailer_visit import review_visit

        # 1. ASM cannot log a visit for a retailer outside their assigned territory
        frappe.set_user(self.asm_south)
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc({
                "doctype": "Retailer Visit",
                "customer": "TEST Catalogue Boutique",  # Belongs to TEST North Sales Territory
                "visit_date": frappe.utils.now_datetime(),
                "visit_type": "Sample & Order Taking",
                "outcome": "Order Expected",
                "notes": "Attempt unauthorized cross-territory visit",
            }).insert()

        # 2. ASM successfully logs a visit for an authorized South territory retailer
        visit = frappe.get_doc({
            "doctype": "Retailer Visit",
            "customer": "TEST 2-1 Buy & Sell Store",  # Belongs to TEST South Sales Territory
            "visit_date": frappe.utils.now_datetime(),
            "visit_type": "Sample & Order Taking",
            "outcome": "Order Expected",
            "notes": "Presented summer knitwear collection.",
        }).insert()

        self.assertEqual(visit.salesperson, self.asm_south)
        self.assertEqual(visit.visitor_role, "Area Sales Manager")
        self.assertEqual(visit.rsm, self.rsm)
        self.assertEqual(visit.review_status, "Submitted")

        # 3. ASM cannot file an RSM Periodic Review
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc({
                "doctype": "Retailer Visit",
                "customer": "TEST 2-1 Buy & Sell Store",
                "visit_date": frappe.utils.now_datetime(),
                "visit_type": "RSM Periodic Review",
                "outcome": "Closed",
                "notes": "Attempt unauthorized review type",
            }).insert()

        # 4. Non-supervising user cannot review the visit
        frappe.set_user("test-warehouse-operator@example.invalid")
        with self.assertRaises(frappe.PermissionError):
            review_visit(visit.name, status="Reviewed by RSM", notes="Unauthorized review attempt")

        # 5. Supervising RSM reviews the ASM visit
        frappe.set_user(self.rsm)
        res = review_visit(visit.name, status="Reviewed by RSM", notes="Approved order target ₹50,000")
        self.assertEqual(res["review_status"], "Reviewed by RSM")
        self.assertEqual(res["reviewed_by"], self.rsm)

        visit.reload()
        self.assertEqual(visit.review_status, "Reviewed by RSM")
        self.assertEqual(visit.reviewed_by, self.rsm)
        self.assertEqual(visit.review_notes, "Approved order target ₹50,000")
        self.assertTrue(bool(visit.reviewed_on))

    def test_rsm_periodic_review_visit(self):
        """RSM can file an RSM Periodic Review capturing dealer and financial assessments."""
        frappe.set_user(self.rsm)
        rsm_visit = frappe.get_doc({
            "doctype": "Retailer Visit",
            "customer": "TEST Catalogue Boutique",
            "visit_date": frappe.utils.now_datetime(),
            "visit_type": "RSM Periodic Review",
            "outcome": "Order Expected",
            "notes": "Conducted 80-day comprehensive shop assessment.",
            "financial_assessment": "Healthy",
            "customer_footfall": 40,
            "stock_condition": "Well Maintained",
            "recommended_credit_limit": 60000.0,
            "dealer_feedback": "Dealer is satisfied with fabric quality and delivery speed.",
        }).insert()

        self.assertEqual(rsm_visit.salesperson, self.rsm)
        self.assertEqual(rsm_visit.rsm, self.rsm)
        self.assertEqual(rsm_visit.visitor_role, "Regional Sales Manager")
        self.assertEqual(rsm_visit.review_status, "Reviewed by RSM")
        self.assertEqual(rsm_visit.financial_assessment, "Healthy")
        self.assertEqual(rsm_visit.customer_footfall, 40)
        self.assertEqual(flt(rsm_visit.recommended_credit_limit), 60000.0)

    def test_rsm_visit_cadence_lifecycle_and_escalation(self):
        """Verify 80-day RSM visit cadence calculation, advance warning, grace period, and escalation."""
        from frappe.utils import add_days, nowdate
        from sales_erp.cadence import (
            STATUS_APPROACHING,
            STATUS_COMPLIANT,
            STATUS_GRACE,
            STATUS_OVERDUE,
            evaluate_rsm_visit_cadence,
            get_customer_rsm_visit_status,
        )

        customer = "TEST Catalogue Boutique"
        today = nowdate()

        try:
            # 1. Base status on customer creation date (recently seeded, so < 70 days elapsed)
            status_today = get_customer_rsm_visit_status(customer, target_date=today)
            self.assertEqual(status_today["customer"], customer)
            self.assertEqual(status_today["rsm"], self.rsm)
            self.assertEqual(status_today["status"], STATUS_COMPLIANT)

            # 2. Advance warning approaching deadline: 75 days elapsed
            target_approaching = add_days(status_today["base_date"], 75)
            status_75 = get_customer_rsm_visit_status(customer, target_date=target_approaching)
            self.assertEqual(status_75["status"], STATUS_APPROACHING)
            self.assertEqual(status_75["days_elapsed"], 75)
            self.assertEqual(status_75["days_remaining"], 5)

            # 3. Grace period: 82 days elapsed (target was day 80, grace is days 81-85)
            target_grace = add_days(status_today["base_date"], 82)
            status_82 = get_customer_rsm_visit_status(customer, target_date=target_grace)
            self.assertEqual(status_82["status"], STATUS_GRACE)
            self.assertEqual(status_82["days_elapsed"], 82)

            # 4. Overdue and escalated: 86 days elapsed (> 85 days)
            target_overdue = add_days(status_today["base_date"], 86)
            status_86 = get_customer_rsm_visit_status(customer, target_date=target_overdue)
            self.assertEqual(status_86["status"], STATUS_OVERDUE)
            self.assertEqual(status_86["days_elapsed"], 86)

            # 5. Idempotent evaluation at approaching date (day 75) creates ToDo for RSM
            eval_75 = evaluate_rsm_visit_cadence(target_date=target_approaching, notify=True)
            self.assertGreaterEqual(eval_75["approaching"], 1)
            rsm_todos = frappe.get_all(
                "ToDo",
                filters={"reference_type": "Customer", "reference_name": customer, "allocated_to": self.rsm, "status": "Open"},
            )
            self.assertTrue(len(rsm_todos) >= 1)
            first_todo_count = len(rsm_todos)

            # Running again does NOT duplicate open ToDos
            evaluate_rsm_visit_cadence(target_date=target_approaching, notify=True)
            rsm_todos_after = frappe.get_all(
                "ToDo",
                filters={"reference_type": "Customer", "reference_name": customer, "allocated_to": self.rsm, "status": "Open"},
            )
            self.assertEqual(len(rsm_todos_after), first_todo_count)

            # 6. Evaluation at overdue date (day 86) creates Administrator escalation
            eval_86 = evaluate_rsm_visit_cadence(target_date=target_overdue, notify=True)
            self.assertGreaterEqual(eval_86["overdue"], 1)
            notifs = frappe.get_all(
                "Notification Log",
                filters={"document_type": "Customer", "document_name": customer},
            )
            self.assertTrue(len(notifs) >= 1)

            # 7. Submitting a qualifying RSM visit closes the obligation and resets cadence to Compliant
            frappe.set_user(self.rsm)
            visit = frappe.get_doc({
                "doctype": "Retailer Visit",
                "customer": customer,
                "visit_date": target_overdue,
                "visit_type": "RSM Periodic Review",
                "outcome": "Closed",
                "notes": "Completed 80-day cycle periodic review.",
            }).insert()

            frappe.set_user("Administrator")
            # Check that open ToDo was closed
            open_todos = frappe.get_all(
                "ToDo",
                filters={"reference_type": "Customer", "reference_name": customer, "allocated_to": self.rsm, "status": "Open"},
            )
            self.assertEqual(len(open_todos), 0)

            # Cadence on the day of the visit is now Compliant
            status_after_visit = get_customer_rsm_visit_status(customer, target_date=target_overdue)
            self.assertEqual(status_after_visit["status"], STATUS_COMPLIANT)
            self.assertEqual(status_after_visit["days_elapsed"], 0)
            self.assertEqual(status_after_visit["last_visit"], visit.name)
        finally:
            frappe.set_user("Administrator")
            frappe.db.sql("DELETE FROM `tabRetailer Visit` WHERE customer = %s AND visit_date >= '2027-01-01'", customer)
            frappe.db.sql("DELETE FROM `tabToDo` WHERE reference_type = 'Customer' AND reference_name = %s", customer)
            frappe.db.sql("DELETE FROM `tabNotification Log` WHERE document_type = 'Customer' AND document_name = %s", customer)
            frappe.db.commit()

    def test_rsm_visit_cadence_report_permissions(self):
        """Verify role and territory scoping for the RSM visit cadence report."""
        from sales_erp.cadence import get_rsm_visit_cadence_report

        # 1. Administrator sees all territories
        frappe.set_user("Administrator")
        admin_report = get_rsm_visit_cadence_report()
        self.assertGreaterEqual(admin_report["summary"]["total"], 2)
        self.assertIn("Administrator", admin_report["user_scope"])

        # 2. RSM sees only territories under their supervision
        frappe.set_user(self.rsm)
        rsm_report = get_rsm_visit_cadence_report()
        self.assertGreaterEqual(rsm_report["summary"]["total"], 1)
        self.assertIn(self.rsm, rsm_report["user_scope"])

        # 3. ASM sees only their assigned territory
        frappe.set_user(self.asm_south)
        asm_report = get_rsm_visit_cadence_report()
        for rec in asm_report["records"]:
            self.assertEqual(rec["territory"], "TEST South Sales Territory")

        # ASM cannot query a territory outside their assignment
        with self.assertRaises(frappe.PermissionError):
            get_rsm_visit_cadence_report(territory="TEST North Sales Territory")

        # 4. Unauthorized roles cannot access the cadence report
        frappe.set_user("test-warehouse-operator@example.invalid")
        with self.assertRaises(frappe.PermissionError):
            get_rsm_visit_cadence_report()



