"""Tests for RSM 80-day visit cadence, tracking, obligations and escalations."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from sales_erp.cadence import (
    STATUS_APPROACHING,
    STATUS_COMPLIANT,
    STATUS_GRACE,
    STATUS_OVERDUE,
    close_rsm_visit_obligation,
    evaluate_rsm_visit_cadence,
    get_customer_rsm_visit_status,
    get_rsm_visit_cadence_report,
)
from sales_erp.seed import SEED_ASM_NORTH, SEED_ASM_SOUTH, SEED_RSM, seed_catalogue


class TestCadence(FrappeTestCase):
    def setUp(self):
        super().setUp()
        from collections import defaultdict
        frappe.local.request_cache = defaultdict(dict)
        frappe.setup_module_map()
        frappe.set_user("Administrator")
        seed_catalogue()
        self.asm_south = SEED_ASM_SOUTH
        self.asm_north = SEED_ASM_NORTH
        self.rsm = SEED_RSM

    def test_cadence_lifecycle_and_escalation(self):
        """Verify 80-day RSM visit cadence calculation, advance warning, grace period, and escalation."""
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
                "financial_assessment": "Healthy",
                "customer_footfall": 25,
                "stock_condition": "Well Maintained",
                "dealer_feedback": "Satisfied with dealer network.",
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

    def test_cadence_report_permissions(self):
        """Verify role and territory scoping for the RSM visit cadence report."""
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

    def test_sis_quarterly_and_monthly_cadence(self):
        """Verify SIS retailer quarterly stock review and monthly general visit cadences and satisfaction."""
        frappe.set_user("Administrator")
        sis_cust = "TEST SIS Retailer Boutique"
        if not frappe.db.exists("Customer", sis_cust):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": sis_cust,
                "customer_group": "SIS (Shop-in-Shop)",
                "territory": "TEST South Sales Territory",
            }).insert(ignore_permissions=True)

        today = nowdate()
        try:
            get_customer_asm_visit_status = frappe.get_attr(
                "sales_erp.cadence.get_customer_asm_visit_status"
            )
            status_list = get_customer_asm_visit_status(sis_cust, target_date=today)

            types = {item["obligation_type"] for item in status_list}
            self.assertIn("Quarterly Stock Review", types)
            self.assertIn("Monthly General Visit", types)

            stock_item = next(it for it in status_list if it["obligation_type"] == "Quarterly Stock Review")
            self.assertEqual(stock_item["retailer_type"], "SIS (Shop-in-Shop)")
            self.assertEqual(stock_item["asm"], self.asm_south)

            # At day 85: quarterly stock review approaches deadline (target is 90 days)
            day_85 = add_days(stock_item["base_date"], 85)
            status_85 = get_customer_asm_visit_status(sis_cust, target_date=day_85)
            stk_85 = next(it for it in status_85 if it["obligation_type"] == "Quarterly Stock Review")
            self.assertEqual(stk_85["status"], STATUS_APPROACHING)

            # Sync obligation
            sync_fn = frappe.get_attr("sales_erp.cadence.sync_asm_visit_obligation")
            obl_name = sync_fn(stk_85, target_date=day_85)
            self.assertIsNotNone(obl_name)
            obl_doc = frappe.get_doc("ASM Visit Obligation", obl_name)
            self.assertEqual(obl_doc.status, "Open")
            self.assertEqual(obl_doc.obligation_type, "Quarterly Stock Review")

            # At day 96: beyond grace period (95 days) -> Overdue
            day_96 = add_days(stock_item["base_date"], 96)
            status_96 = get_customer_asm_visit_status(sis_cust, target_date=day_96)
            stk_96 = next(it for it in status_96 if it["obligation_type"] == "Quarterly Stock Review")
            self.assertEqual(stk_96["status"], STATUS_OVERDUE)

            sync_fn(stk_96, target_date=day_96)
            obl_doc.reload()
            self.assertEqual(obl_doc.status, "Overdue / Escalated")

            # Completing a Stock Review visit satisfies the obligation
            frappe.set_user(self.asm_south)
            visit = frappe.get_doc({
                "doctype": "Retailer Visit",
                "customer": sis_cust,
                "visit_date": day_96,
                "visit_type": "Stock Review",
                "outcome": "Closed",
                "notes": "Completed quarterly physical stock check and reconciliation.",
            }).insert()

            obl_doc.reload()
            self.assertEqual(obl_doc.status, "Satisfied")
            self.assertEqual(obl_doc.qualifying_visit, visit.name)

        finally:
            frappe.set_user("Administrator")
            frappe.db.sql("DELETE FROM `tabRetailer Visit` WHERE customer = %s", sis_cust)
            frappe.db.sql("DELETE FROM `tabASM Visit Obligation` WHERE customer = %s", sis_cust)
            frappe.db.sql("DELETE FROM `tabCustomer` WHERE name = %s", sis_cust)
            frappe.db.commit()

    def test_buy_and_sell_monthly_cadence(self):
        """Verify Buy & Sell retailer monthly sample/order visit cadence and satisfaction."""
        frappe.set_user("Administrator")
        bs_cust = "TEST BuySell Retailer Boutique"
        if not frappe.db.exists("Customer", bs_cust):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": bs_cust,
                "customer_group": "Buy & Sell",
                "territory": "TEST South Sales Territory",
            }).insert(ignore_permissions=True)

        today = nowdate()
        try:
            get_asm_status = frappe.get_attr("sales_erp.cadence.get_customer_asm_visit_status")
            status_list = get_asm_status(bs_cust, target_date=today)
            types = {item["obligation_type"] for item in status_list}
            self.assertIn("Monthly Sample & Order", types)

            so_item = next(it for it in status_list if it["obligation_type"] == "Monthly Sample & Order")
            self.assertEqual(so_item["retailer_type"], "Buy & Sell")
            self.assertEqual(so_item["asm"], self.asm_south)

            # At day 27: approaching deadline (target is 30 days)
            day_27 = add_days(so_item["base_date"], 27)
            status_27 = get_asm_status(bs_cust, target_date=day_27)
            so_27 = next(it for it in status_27 if it["obligation_type"] == "Monthly Sample & Order")
            self.assertEqual(so_27["status"], STATUS_APPROACHING)

            sync_fn = frappe.get_attr("sales_erp.cadence.sync_asm_visit_obligation")
            obl_name = sync_fn(so_27, target_date=day_27)
            self.assertIsNotNone(obl_name)
            obl_doc = frappe.get_doc("ASM Visit Obligation", obl_name)
            self.assertEqual(obl_doc.status, "Open")

            # At day 37: overdue (> 35 days)
            day_37 = add_days(so_item["base_date"], 37)
            status_37 = get_asm_status(bs_cust, target_date=day_37)
            so_37 = next(it for it in status_37 if it["obligation_type"] == "Monthly Sample & Order")
            self.assertEqual(so_37["status"], STATUS_OVERDUE)

            sync_fn(so_37, target_date=day_37)
            obl_doc.reload()
            self.assertEqual(obl_doc.status, "Overdue / Escalated")

            # Completing a Sample & Order visit satisfies the obligation
            frappe.set_user(self.asm_south)
            visit = frappe.get_doc({
                "doctype": "Retailer Visit",
                "customer": bs_cust,
                "visit_date": day_37,
                "visit_type": "Sample & Order Taking",
                "outcome": "Order Expected",
                "notes": "Presented new summer line samples and collected seasonal booking.",
            }).insert()

            obl_doc.reload()
            self.assertEqual(obl_doc.status, "Satisfied")
            self.assertEqual(obl_doc.qualifying_visit, visit.name)

        finally:
            frappe.set_user("Administrator")
            frappe.db.sql("DELETE FROM `tabRetailer Visit` WHERE customer = %s", bs_cust)
            frappe.db.sql("DELETE FROM `tabASM Visit Obligation` WHERE customer = %s", bs_cust)
            frappe.db.sql("DELETE FROM `tabCustomer` WHERE name = %s", bs_cust)
            frappe.db.commit()

    def test_collection_workflow_90_120_days(self):
        """Verify unpaid invoices in 90-120 days generate payment collection obligations."""
        frappe.set_user("Administrator")
        cust = "TEST Collection Retailer"
        if not frappe.db.exists("Customer", cust):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": cust,
                "customer_group": "Buy & Sell",
                "territory": "TEST South Sales Territory",
            }).insert(ignore_permissions=True)

        inv_name = "TEST-SINV-CAD-001"
        today = nowdate()
        inv_date = add_days(today, -100)  # 100 days ago (in 90-120 day window)

        try:
            # Create a mock native Sales Invoice row in tabSales Invoice
            frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name = %s", inv_name)
            frappe.db.sql(
                """
                INSERT INTO `tabSales Invoice`
                (name, customer, customer_name, posting_date, due_date, outstanding_amount, grand_total, docstatus, currency, company)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 'INR', %s)
                """,
                (inv_name, cust, cust, inv_date, inv_date, 45000.0, 45000.0, "Windmill Clothing Private Limited"),
            )
            frappe.db.commit()

            get_asm_status = frappe.get_attr("sales_erp.cadence.get_customer_asm_visit_status")
            status_list = get_asm_status(cust, target_date=today)
            col_item = next((it for it in status_list if it["obligation_type"] == "Payment Collection Follow-up"), None)
            self.assertIsNotNone(col_item)
            self.assertEqual(col_item["invoice_no"], inv_name)
            self.assertEqual(col_item["outstanding_amount"], 45000.0)
            self.assertEqual(col_item["status"], STATUS_GRACE)  # Within 90-120 day collection window

            # Sync obligation
            sync_fn = frappe.get_attr("sales_erp.cadence.sync_asm_visit_obligation")
            obl_name = sync_fn(col_item, target_date=today)
            self.assertIsNotNone(obl_name)
            obl_doc = frappe.get_doc("ASM Visit Obligation", obl_name)
            self.assertEqual(obl_doc.status, "Grace Period")
            self.assertEqual(obl_doc.outstanding_amount, 45000.0)

            # Test collection API
            get_collections = frappe.get_attr("sales_erp.cadence.get_collection_obligations")
            frappe.set_user(self.asm_south)
            res = get_collections(target_date=today)
            self.assertTrue(any(row["name"] == inv_name for row in res["collections"]))

            # ASM North cannot see South's collection invoices
            frappe.set_user(self.asm_north)
            res_north = get_collections(target_date=today)
            self.assertFalse(any(row["name"] == inv_name for row in res_north["collections"]))

            # At day 125: beyond 120 days -> Overdue / Escalated
            target_125 = add_days(inv_date, 125)
            status_125 = get_asm_status(cust, target_date=target_125)
            col_125 = next(it for it in status_125 if it["obligation_type"] == "Payment Collection Follow-up")
            self.assertEqual(col_125["status"], STATUS_OVERDUE)

            sync_fn(col_125, target_date=target_125)
            obl_doc.reload()
            self.assertEqual(obl_doc.status, "Overdue / Escalated")

        finally:
            frappe.set_user("Administrator")
            frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name = %s", inv_name)
            frappe.db.sql("DELETE FROM `tabASM Visit Obligation` WHERE customer = %s", cust)
            frappe.db.sql("DELETE FROM `tabCustomer` WHERE name = %s", cust)
            frappe.db.commit()

    def test_asm_visit_obligation_permissions_and_scoping(self):
        """Verify role and territory enforcement on ASM Visit Obligations."""
        frappe.set_user("Administrator")
        cust_south = "TEST South Perm Retailer"
        cust_north = "TEST North Perm Retailer"
        if not frappe.db.exists("Customer", cust_south):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": cust_south,
                "customer_group": "Buy & Sell",
                "territory": "TEST South Sales Territory",
            }).insert(ignore_permissions=True)
        if not frappe.db.exists("Customer", cust_north):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": cust_north,
                "customer_group": "Buy & Sell",
                "territory": "TEST North Sales Territory",
            }).insert(ignore_permissions=True)

        obl_south = frappe.get_doc({
            "doctype": "ASM Visit Obligation",
            "obligation_type": "Monthly Sample & Order",
            "cycle_id": f"{cust_south}-Monthly Sample & Order-2026-11-01",
            "customer": cust_south,
            "territory": "TEST South Sales Territory",
            "assigned_asm": self.asm_south,
            "supervising_rsm": self.rsm,
            "cycle_start": "2026-11-01",
            "due_date": "2026-12-01",
            "status": "Open",
        }).insert(ignore_permissions=True)

        obl_north = frappe.get_doc({
            "doctype": "ASM Visit Obligation",
            "obligation_type": "Monthly Sample & Order",
            "cycle_id": f"{cust_north}-Monthly Sample & Order-2026-11-01",
            "customer": cust_north,
            "territory": "TEST North Sales Territory",
            "assigned_asm": self.asm_north,
            "supervising_rsm": self.rsm,
            "cycle_start": "2026-11-01",
            "due_date": "2026-12-01",
            "status": "Open",
        }).insert(ignore_permissions=True)

        try:
            get_dir = frappe.get_attr("sales_erp.cadence.get_asm_cadence_directory")

            # ASM South sees only South obligations
            frappe.set_user(self.asm_south)
            res_south = get_dir()
            names_south = [o["name"] for o in res_south["obligations"]]
            self.assertIn(obl_south.name, names_south)
            self.assertNotIn(obl_north.name, names_south)

            # ASM South cannot query North territory directly
            with self.assertRaises(frappe.PermissionError):
                get_dir(territory="TEST North Sales Territory")

            # RSM sees both South and North
            frappe.set_user(self.rsm)
            res_rsm = get_dir()
            names_rsm = [o["name"] for o in res_rsm["obligations"]]
            self.assertIn(obl_south.name, names_rsm)
            self.assertIn(obl_north.name, names_rsm)

            # Warehouse operator has no access
            frappe.set_user("test-warehouse-operator@example.invalid")
            with self.assertRaises(frappe.PermissionError):
                get_dir()

        finally:
            frappe.set_user("Administrator")
            frappe.db.sql("DELETE FROM `tabASM Visit Obligation` WHERE name IN (%s, %s)", (obl_south.name, obl_north.name))
            frappe.db.sql("DELETE FROM `tabCustomer` WHERE name IN (%s, %s)", (cust_south, cust_north))
            frappe.db.commit()

