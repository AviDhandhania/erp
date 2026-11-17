"""Tests for Retailer Credit Limit Request workflow, server-side approval, and audit integrity."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from sales_erp.sales_erp.doctype.retailer_credit_limit_request.retailer_credit_limit_request import (
    approve_credit_limit_request,
    get_customer_current_credit_limit,
    propose_credit_limit,
    reject_credit_limit_request,
    set_customer_credit_limit,
)
from sales_erp.seed import SEED_ASM_NORTH, SEED_ASM_SOUTH, SEED_RSM, seed_catalogue


class TestCreditLimitRequest(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.setup_module_map()
        frappe.set_user("Administrator")
        seed_catalogue()
        self.asm_south = SEED_ASM_SOUTH
        self.asm_north = SEED_ASM_NORTH
        self.rsm = SEED_RSM

    def test_credit_limit_request_lifecycle(self):
        """Verify RSM proposal, live limit preservation until approval, and immutable audit tracking."""
        customer = "TEST Catalogue Boutique"
        frappe.set_user("Administrator")
        frappe.db.sql(
            "DELETE FROM `tabRetailer Credit Limit Request` WHERE customer = %s", customer
        )
        frappe.db.commit()
        initial_limit = get_customer_current_credit_limit(customer)

        try:
            # 1. RSM proposes a limit adjustment
            frappe.set_user(self.rsm)
            prop = propose_credit_limit(
                customer=customer,
                proposed_limit=initial_limit + 50000.0,
                reason="Retailer doubled floor space and demonstrated consistent monthly clearance.",
            )
            req_name = prop["name"]
            req_doc = frappe.get_doc("Retailer Credit Limit Request", req_name)
            self.assertEqual(req_doc.status, "Pending Approval")
            self.assertEqual(req_doc.proposer, self.rsm)
            self.assertEqual(flt(req_doc.current_credit_limit), flt(initial_limit))
            self.assertEqual(flt(req_doc.proposed_credit_limit), flt(initial_limit + 50000.0))

            # Live customer credit limit MUST NOT change while request is pending
            frappe.set_user("Administrator")
            self.assertEqual(flt(get_customer_current_credit_limit(customer)), flt(initial_limit))

            # Cannot propose another pending request while one is active
            frappe.set_user(self.rsm)
            with self.assertRaises(frappe.ValidationError):
                propose_credit_limit(customer, proposed_limit=initial_limit + 60000.0, reason="Duplicate attempt")

            # 2. Non-administrator cannot approve the request
            with self.assertRaises(frappe.PermissionError):
                approve_credit_limit_request(req_name)

            # Non-administrator cannot reject the request
            with self.assertRaises(frappe.PermissionError):
                reject_credit_limit_request(req_name, reason="Unauthorized reject attempt")

            # 3. Administrator approves the request
            frappe.set_user("Administrator")
            appr_res = approve_credit_limit_request(req_name)
            self.assertEqual(appr_res["status"], "Approved")

            req_doc.reload()
            self.assertEqual(req_doc.status, "Approved")
            self.assertEqual(req_doc.approver, "Administrator")
            self.assertTrue(bool(req_doc.decided_on))

            # Live customer limit in ERPNext is now updated
            updated_limit = get_customer_current_credit_limit(customer)
            self.assertEqual(flt(updated_limit), flt(initial_limit + 50000.0))

            # 4. Decided request is immutable
            frappe.set_user(self.rsm)
            with self.assertRaises(frappe.PermissionError):
                req_doc.reason = "Tampering with approved justification"
                req_doc.save()

            # 5. Rejection workflow: RSM proposes further increase
            prop2 = propose_credit_limit(
                customer=customer,
                proposed_limit=updated_limit + 100000.0,
                reason="Festive season pre-booking inventory requirement.",
            )
            req2_name = prop2["name"]

            frappe.set_user("Administrator")
            # Empty rejection reason is rejected
            with self.assertRaises(frappe.ValidationError):
                reject_credit_limit_request(req2_name, reason="")

            rej_res = reject_credit_limit_request(req2_name, reason="Insufficient audited bank statements.")
            self.assertEqual(rej_res["status"], "Rejected")

            req2_doc = frappe.get_doc("Retailer Credit Limit Request", req2_name)
            self.assertEqual(req2_doc.status, "Rejected")
            self.assertEqual(req2_doc.rejection_reason, "Insufficient audited bank statements.")

            # 6. Live limit change while pending approval prevents approval
            prop3 = propose_credit_limit(
                customer=customer,
                proposed_limit=updated_limit + 60000.0,
                reason="Further growth expansion.",
            )
            req3_name = prop3["name"]
            # Change live customer credit limit behind the scenes
            set_customer_credit_limit(customer, updated_limit + 10000.0)
            with self.assertRaisesRegex(frappe.ValidationError, "live credit limit for customer"):
                approve_credit_limit_request(req3_name)
            # Revert back
            set_customer_credit_limit(customer, updated_limit)

            # Live customer limit remains at the approved value
            self.assertEqual(flt(get_customer_current_credit_limit(customer)), flt(updated_limit))

        finally:
            frappe.set_user("Administrator")
            frappe.db.sql(
                "DELETE FROM `tabRetailer Credit Limit Request` WHERE customer = %s", customer
            )
            set_customer_credit_limit(customer, initial_limit)
            frappe.db.commit()

    def test_credit_limit_request_permissions(self):
        """Verify role, supervisory, and territory constraints for credit limit requests."""
        customer_north = "TEST Catalogue Boutique"  # North territory

        # 1. ASM cannot propose credit limit requests
        frappe.set_user(self.asm_north)
        with self.assertRaises(frappe.PermissionError):
            propose_credit_limit(customer_north, proposed_limit=99000.0, reason="ASM proposal attempt")

        # 2. Operational warehouse users cannot propose or access requests
        frappe.set_user("test-warehouse-operator@example.invalid")
        with self.assertRaises(frappe.PermissionError):
            propose_credit_limit(customer_north, proposed_limit=99000.0, reason="Warehouse attempt")

        # 3. Proposing identical credit limit is rejected
        frappe.set_user("Administrator")
        current = get_customer_current_credit_limit(customer_north)

        frappe.set_user(self.rsm)
        with self.assertRaises(frappe.ValidationError):
            propose_credit_limit(customer_north, proposed_limit=current, reason="No change attempt")

    def test_visit_auto_proposes_credit_limit_request(self):
        """RSM periodic visit with recommended credit limit creates an audited pending request."""
        customer = "TEST Catalogue Boutique"
        frappe.set_user("Administrator")
        frappe.db.sql(
            "DELETE FROM `tabRetailer Credit Limit Request` WHERE customer = %s", customer
        )
        frappe.db.commit()
        current_limit = get_customer_current_credit_limit(customer)
        recommended = current_limit + 40000.0

        try:
            frappe.set_user(self.rsm)
            visit = frappe.get_doc({
                "doctype": "Retailer Visit",
                "customer": customer,
                "visit_date": frappe.utils.now_datetime(),
                "visit_type": "RSM Periodic Review",
                "outcome": "Order Expected",
                "notes": "Reviewed dealer footfall and financials.",
                "recommended_credit_limit": recommended,
                "financial_assessment": "Healthy",
                "customer_footfall": 25,
                "stock_condition": "Well Maintained",
                "dealer_feedback": "Dealer confirmed strong demand.",
            }).insert()

            # Check that pending request was automatically created linked to this visit
            frappe.set_user("Administrator")
            requests = frappe.get_all(
                "Retailer Credit Limit Request",
                filters={"source_visit": visit.name, "customer": customer},
                fields=["name", "proposed_credit_limit", "status", "proposer"],
            )
            self.assertEqual(len(requests), 1)
            self.assertEqual(flt(requests[0].proposed_credit_limit), flt(recommended))
            self.assertEqual(requests[0].status, "Pending Approval")
            self.assertEqual(requests[0].proposer, self.rsm)

            # Live customer limit must not change until approved
            self.assertEqual(flt(get_customer_current_credit_limit(customer)), flt(current_limit))
        finally:
            frappe.set_user("Administrator")
            frappe.db.sql(
                "DELETE FROM `tabRetailer Credit Limit Request` WHERE customer = %s", customer
            )
            frappe.db.sql(
                "DELETE FROM `tabRetailer Visit` WHERE customer = %s AND notes = 'Reviewed dealer footfall and financials.'", customer
            )
            frappe.db.commit()
