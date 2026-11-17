"""Tests for RSM 80-day visit cadence, tracking, obligations and escalations."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from clothing_erp.cadence import (
    STATUS_APPROACHING,
    STATUS_COMPLIANT,
    STATUS_GRACE,
    STATUS_OVERDUE,
    close_rsm_visit_obligation,
    evaluate_rsm_visit_cadence,
    get_customer_rsm_visit_status,
    get_rsm_visit_cadence_report,
)
from clothing_erp.seed import SEED_ASM_NORTH, SEED_ASM_SOUTH, SEED_RSM, seed_catalogue


class TestCadence(FrappeTestCase):
    def setUp(self):
        super().setUp()
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
