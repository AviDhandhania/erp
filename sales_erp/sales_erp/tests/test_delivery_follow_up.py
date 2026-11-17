"""Tests for delivery follow-up obligations, lifecycle, and permissions."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from sales_erp.delivery_follow_up import (
    create_delivery_follow_up_obligation,
    delivery_follow_up_has_permission,
    delivery_follow_up_query_conditions,
    get_delivery_follow_up_obligations,
    record_delivery_follow_up,
)
from sales_erp.seed import (
    SEED_ASM_NORTH,
    SEED_ASM_SOUTH,
    SEED_BUSINESS_ADMIN,
    SEED_RETAILER,
    SEED_RSM,
    seed_catalogue,
)


class TestDeliveryFollowUp(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        seed_catalogue()
        self.asm_north = SEED_ASM_NORTH
        self.asm_south = SEED_ASM_SOUTH
        self.rsm = SEED_RSM
        self.admin = SEED_BUSINESS_ADMIN
        self.retailer = SEED_RETAILER

        # Create a real test delivery note record in the database
        self.dn_name = "TEST-DN-" + frappe.generate_hash(length=8)
        frappe.db.sql(
            """
            INSERT INTO `tabDelivery Note` (name, customer, posting_date, docstatus, company, creation, modified, modified_by, owner)
            VALUES (%s, %s, %s, 1, %s, NOW(), NOW(), 'Administrator', 'Administrator')
            """,
            (self.dn_name, self.retailer, nowdate(), "TEST Company"),
        )
        self.dn = frappe.get_doc("Delivery Note", self.dn_name)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete(
            "Delivery Follow-Up Obligation",
            {"delivery_note": ["like", "TEST-DN-%"]},
        )
        frappe.db.delete(
            "Retailer Visit",
            {"visit_type": "Delivery Follow-up", "customer": self.retailer},
        )
        frappe.db.sql("DELETE FROM `tabDelivery Note` WHERE name LIKE 'TEST-DN-%'")
        super().tearDown()

    def test_obligation_created_from_submitted_delivery_note(self):
        """Obligation is created with correct customer, territory, ASM, RSM, and due date."""
        obligation = create_delivery_follow_up_obligation(self.dn)
        self.assertIsNotNone(obligation)
        self.assertEqual(obligation.delivery_note, self.dn_name)
        self.assertEqual(obligation.customer, self.retailer)
        self.assertEqual(obligation.territory, "TEST North Sales Territory")
        self.assertEqual(obligation.assigned_asm, self.asm_north)
        self.assertEqual(obligation.assigned_rsm, self.rsm)
        self.assertEqual(obligation.status, "Pending Contact")
        self.assertEqual(
            getdate(obligation.due_date),
            getdate(add_days(obligation.posting_date, 3)),
        )

    def test_creation_is_idempotent(self):
        """Calling create_delivery_follow_up_obligation again returns existing record without duplicating."""
        first = create_delivery_follow_up_obligation(self.dn)
        second = create_delivery_follow_up_obligation(self.dn)
        self.assertEqual(first.name, second.name)
        count = frappe.db.count(
            "Delivery Follow-Up Obligation",
            {"delivery_note": self.dn_name},
        )
        self.assertEqual(count, 1)

    def test_unsubmitted_delivery_note_produces_no_obligation(self):
        """Draft delivery note does not generate an obligation."""
        draft_dn = frappe._dict(name="TEST-DRAFT-DN", docstatus=0, customer=self.retailer)
        result = create_delivery_follow_up_obligation(draft_dn)
        self.assertIsNone(result)

    def test_territory_and_role_scoping(self):
        """ASM assigned to territory and supervising RSM have permission; foreign ASM is denied."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        # Assigned North ASM has read/write permission
        self.assertTrue(delivery_follow_up_has_permission(obligation, "read", user=self.asm_north))
        self.assertTrue(delivery_follow_up_has_permission(obligation, "write", user=self.asm_north))

        # Supervising RSM has read/write permission
        self.assertTrue(delivery_follow_up_has_permission(obligation, "read", user=self.rsm))
        self.assertTrue(delivery_follow_up_has_permission(obligation, "write", user=self.rsm))

        # Business Admin has read/write/delete permission
        self.assertTrue(delivery_follow_up_has_permission(obligation, "read", user=self.admin))
        self.assertTrue(delivery_follow_up_has_permission(obligation, "delete", user=self.admin))

        # South ASM does NOT have permission for North territory obligation
        self.assertFalse(delivery_follow_up_has_permission(obligation, "read", user=self.asm_south))
        self.assertFalse(delivery_follow_up_has_permission(obligation, "write", user=self.asm_south))

    def test_query_conditions_enforce_territory_filtering(self):
        """Query conditions filter by assigned territory/RSM."""
        admin_cond = delivery_follow_up_query_conditions(user=self.admin)
        self.assertEqual(admin_cond, "")

        north_cond = delivery_follow_up_query_conditions(user=self.asm_north)
        self.assertIn("TEST North Sales Territory", north_cond)

        rsm_cond = delivery_follow_up_query_conditions(user=self.rsm)
        self.assertIn("TEST North Sales Territory", rsm_cond)
        self.assertIn(self.rsm, rsm_cond)

    def test_record_delivery_follow_up_success_creates_visit_and_satisfies(self):
        """Recording successful delivery creates audit visit and marks obligation Satisfied."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        frappe.set_user(self.asm_north)
        result = record_delivery_follow_up(
            obligation=obligation.name,
            outcome="Delivered in Full & Good Condition",
            contact_person="Ramesh Patel",
            issue_notes="Delivered on time, all 50 boxes verified.",
        )

        self.assertEqual(result["status"], "Satisfied")
        self.assertEqual(result["outcome"], "Delivered in Full & Good Condition")
        self.assertTrue(result["qualifying_visit"])

        updated = frappe.get_doc("Delivery Follow-Up Obligation", obligation.name)
        self.assertEqual(updated.status, "Satisfied")
        self.assertEqual(updated.contact_person, "Ramesh Patel")
        self.assertEqual(updated.satisfied_by, self.asm_north)
        self.assertIsNotNone(updated.satisfied_on)

        # Verify linked Retailer Visit was created with correct audit trail
        visit = frappe.get_doc("Retailer Visit", updated.qualifying_visit)
        self.assertEqual(visit.customer, self.retailer)
        self.assertEqual(visit.visit_type, "Delivery Follow-up")
        self.assertEqual(visit.outcome, "Closed")
        self.assertIn("Delivered in Full & Good Condition", visit.notes)
        self.assertIn("Ramesh Patel", visit.notes)

    def test_record_delivery_follow_up_with_shortage_escalates_issue(self):
        """Recording shortage creates audit visit with Issue Reported and marks obligation Issue Escalated."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        frappe.set_user(self.asm_north)
        result = record_delivery_follow_up(
            obligation=obligation.name,
            outcome="Shortage Reported",
            contact_person="Suresh Shah",
            issue_notes="Box #3 missing 5 units of T-Shirt M.",
        )

        self.assertEqual(result["status"], "Issue Escalated")
        self.assertEqual(result["outcome"], "Shortage Reported")

        updated = frappe.get_doc("Delivery Follow-Up Obligation", obligation.name)
        self.assertEqual(updated.status, "Issue Escalated")

        visit = frappe.get_doc("Retailer Visit", updated.qualifying_visit)
        self.assertEqual(visit.visit_type, "Delivery Follow-up")
        self.assertEqual(visit.outcome, "Issue Reported")

    def test_record_delivery_follow_up_unavailable_remains_pending(self):
        """Recording retailer unavailable keeps obligation Pending Contact without creating a visit."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        frappe.set_user(self.asm_north)
        result = record_delivery_follow_up(
            obligation=obligation.name,
            outcome="Retailer Unavailable",
            contact_person="Store Manager",
            issue_notes="Store closed for inventory counting, will retry tomorrow.",
        )

        self.assertEqual(result["status"], "Pending Contact")
        self.assertIsNone(result.get("qualifying_visit"))

        updated = frappe.get_doc("Delivery Follow-Up Obligation", obligation.name)
        self.assertEqual(updated.status, "Pending Contact")
        self.assertIsNone(updated.qualifying_visit)

    def test_record_cannot_modify_already_satisfied_obligation(self):
        """Satisfied obligation cannot be recorded again."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        frappe.set_user(self.asm_north)
        record_delivery_follow_up(
            obligation=obligation.name,
            outcome="Delivered in Full & Good Condition",
        )

        with self.assertRaises(frappe.ValidationError):
            record_delivery_follow_up(
                obligation=obligation.name,
                outcome="Shortage Reported",
            )

    def test_unauthorized_asm_cannot_record_follow_up(self):
        """ASM from another territory is denied permission to record follow-up."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        frappe.set_user(self.asm_south)
        with self.assertRaises(frappe.PermissionError):
            record_delivery_follow_up(
                obligation=obligation.name,
                outcome="Delivered in Full & Good Condition",
            )

    def test_invalid_outcome_throws_validation_error(self):
        """Invalid outcome string is rejected."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        frappe.set_user(self.asm_north)
        with self.assertRaises(frappe.ValidationError):
            record_delivery_follow_up(
                obligation=obligation.name,
                outcome="Random Outcome",
            )

    def test_get_delivery_follow_up_obligations_scoped_to_user(self):
        """Directory query applies territory scoping and filters."""
        obligation = create_delivery_follow_up_obligation(self.dn)

        # North ASM sees it
        frappe.set_user(self.asm_north)
        res_north = get_delivery_follow_up_obligations()
        names_north = [o["name"] for o in res_north["obligations"]]
        self.assertIn(obligation.name, names_north)

        # South ASM does NOT see it
        frappe.set_user(self.asm_south)
        res_south = get_delivery_follow_up_obligations()
        names_south = [o["name"] for o in res_south["obligations"]]
        self.assertNotIn(obligation.name, names_south)

        # Admin sees it
        frappe.set_user(self.admin)
        res_admin = get_delivery_follow_up_obligations()
        names_admin = [o["name"] for o in res_admin["obligations"]]
        self.assertIn(obligation.name, names_admin)
