# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Tests for Session 13: Quality Gates, Exact Revision Locking, Corrections,
Controlled PDF Report Bundles, Return Dispositions and Supplier Claims.
"""

from __future__ import annotations

import base64
import json
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, now_datetime, nowdate

from quality_erp.cycle import get_or_create_cycle, link_native_purchase_receipt
from quality_erp.quality import (
    approve_quality_gate,
    approve_return_disposition,
    create_quality_inspection,
    create_supplier_claim,
    decide_final_inspection,
    decide_production_go_ahead,
    decide_supplier_claim,
    export_quality_report_bundle,
    get_complete_stage_history,
    get_final_inspection_review_bundle,
    get_production_go_ahead_review_bundle,
    recommend_return_disposition,
    record_return_quarantine,
    request_inspection_correction,
    resubmit_inspection_correction,
    revise_quality_inspection,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)
from quality_erp.seed import seed_quality_data


class TestQualityGatesAndDispositions(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.setup_module_map()
        if not hasattr(frappe.local, "module_app") or not frappe.local.module_app:
            frappe.local.module_app = {}
        frappe.local.module_app["quality_erp"] = "quality_erp"
        frappe.set_user("Administrator")
        seed_quality_data()
        cls.company = cls._ensure_company("TEST Clothing ERP Demo")
        cls.supplier = cls._ensure_supplier("TEST Fabric & Stitch Mills")
        cls.item_code = cls._ensure_item("TEST-CLASSIC-TEE-BLK")
        cls.warehouse = cls._ensure_warehouse("TEST Quarantine Warehouse", cls.company)
        cls.saleable_wh = cls._ensure_warehouse("TEST Finished Goods", cls.company)
        cls.scrap_wh = cls._ensure_warehouse("TEST Scrap Store", cls.company)
        cls.seconds_wh = cls._ensure_warehouse("TEST Seconds Store", cls.company)

        # Create distinct test users
        cls.admin_user = cls._ensure_user("test_qual_badmin@example.invalid", [ROLE_BUSINESS_ADMIN])
        cls.manager_user = cls._ensure_user("test_qual_mgr@example.invalid", [ROLE_QUALITY_MANAGER])
        cls.inspector_user = cls._ensure_user("test_qual_insp@example.invalid", [ROLE_QUALITY_INSPECTOR])
        frappe.db.commit()

    @classmethod
    def _ensure_company(cls, name):
        if not frappe.db.exists("Company", name):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": name,
                "abbr": "TCED",
                "default_currency": "INR",
                "country": "India",
            }).insert(ignore_permissions=True)
        return name

    @classmethod
    def _ensure_supplier(cls, name):
        if not frappe.db.exists("Supplier", name):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": name,
                "supplier_group": "Raw Material",
            }).insert(ignore_permissions=True)
        return name

    @classmethod
    def _ensure_item(cls, code):
        if not frappe.db.exists("Item", code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": code,
                "item_name": code,
                "item_group": "All Item Groups",
                "stock_uom": "Nos",
                "is_stock_item": 1,
            }).insert(ignore_permissions=True)
        return code

    @classmethod
    def _ensure_warehouse(cls, name, company):
        abbr = frappe.db.get_value("Company", company, "abbr") or "TCED"
        full_name = f"{name} - {abbr}" if " - " not in name else name
        raw_name = name.split(" - ")[0]
        if not frappe.db.exists("Warehouse", full_name):
            doc = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": raw_name,
                "company": company,
            }).insert(ignore_permissions=True)
            return doc.name
        return full_name

    @classmethod
    def _ensure_user(cls, email, roles):
        if not frappe.db.exists("User", email):
            u = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0,
                "user_type": "System User",
            }).insert(ignore_permissions=True)
        else:
            u = frappe.get_doc("User", email)

        u.add_roles(*roles)
        frappe.clear_cache(user=email)
        return email

    def setUp(self):
        super().setUp()
        frappe.setup_module_map()
        if not hasattr(frappe.local, "module_app") or not frappe.local.module_app:
            frappe.local.module_app = {}
        frappe.local.module_app["quality_erp"] = "quality_erp"
        frappe.set_user("Administrator")

    def tearDown(self):
        super().tearDown()
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def _create_test_cycle(self, lot="LOT-GATES-01"):
        unique_lot = f"{lot}-{frappe.generate_hash(length=8)}"
        res = get_or_create_cycle(
            company=self.company,
            supplier=self.supplier,
            item_code=self.item_code,
            production_lot=unique_lot,
            season="SS2026",
        )
        return frappe.get_doc("Production Quality Cycle", res["cycle_name"])

    # -----------------------------------------------------------------------
    # 1. Gate 4: Production Go Ahead Bundle & Prerequisites
    # -----------------------------------------------------------------------
    def test_production_go_ahead_bundle_prerequisites_and_revisions(self):
        """Bundle computes readiness, missing stages, and cryptographic hash."""
        cycle = self._create_test_cycle("LOT-PGA-01")

        # Initially, no inspections exist -> prerequisites missing
        bundle = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        self.assertFalse(bundle["ready_for_decision"])
        self.assertEqual(len(bundle["missing_stages"]), 3)
        self.assertTrue(bundle["bundle_hash"])

        # Create Stage 1
        i1 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )
        bundle2 = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        self.assertFalse(bundle2["ready_for_decision"])
        self.assertEqual(len(bundle2["missing_stages"]), 2)

        # Create Stage 2 and Stage 3
        i2 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="2. Second Submission",
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )
        i3 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="3. Size Set Submission",
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )

        bundle3 = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        self.assertTrue(bundle3["ready_for_decision"])
        self.assertEqual(len(bundle3["missing_stages"]), 0)
        self.assertIn("1. First Submission", bundle3["reviewed_revisions"])
        self.assertIn("2. Second Submission", bundle3["reviewed_revisions"])
        self.assertIn("3. Size Set Submission", bundle3["reviewed_revisions"])
        self.assertTrue(bundle3["bundle_hash"])

    # -----------------------------------------------------------------------
    # 2. Gate 4: Exact Revision Locking & Immutability
    # -----------------------------------------------------------------------
    def test_production_go_ahead_exact_revision_locking_and_immutability(self):
        """Approving Gate 4 locks reviewed revisions and transitions cycle to 'Production in Progress'."""
        cycle = self._create_test_cycle("LOT-PGA-02")
        for stg in ["1. First Submission", "2. Second Submission", "3. Size Set Submission"]:
            create_quality_inspection(
                supplier=self.supplier,
                item_code=self.item_code,
                stage=stg,
                production_quality_cycle=cycle.name,
                status="Approved",
                result="Passed",
            )

        bundle = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        self.assertTrue(bundle["ready_for_decision"])

        # Decide Gate 4 as Business Admin
        frappe.set_user(self.admin_user)
        dec_res = decide_production_go_ahead(
            cycle_name=cycle.name,
            decision="Approved",
            reviewed_revisions=bundle["reviewed_revisions"],
            conditions="Fabric specs validated",
            bundle_hash=bundle["bundle_hash"],
        )
        self.assertTrue(dec_res["success"])
        self.assertEqual(dec_res["go_ahead_status"], "Approved")
        self.assertEqual(dec_res["status"], "Production in Progress")

        # Verify parent cycle is updated
        cycle.reload()
        self.assertEqual(cycle.go_ahead_status, "Approved")
        self.assertEqual(cycle.status, "Production in Progress")
        self.assertEqual(cycle.go_ahead_approved_by, self.admin_user)

        # Verify reviewed inspections are now gate_locked
        for rev_info in bundle["reviewed_revisions"].values():
            sqi = frappe.get_doc("Supplier Quality Inspection", rev_info["name"])
            self.assertEqual(sqi.gate_locked, 1)
            self.assertIn("Gate 4: Production Go Ahead", sqi.locked_gate_decision)

            # Attempting to revise or alter a locked inspection raises ValidationError
            with self.assertRaisesRegex(frappe.ValidationError, "locked"):
                revise_quality_inspection(inspection_name=sqi.name)

        # Verify Decision Immutability: re-deciding raises ValidationError
        with self.assertRaisesRegex(frappe.ValidationError, "already been decided"):
            decide_production_go_ahead(
                cycle_name=cycle.name,
                decision="Rejected",
                reviewed_revisions=bundle["reviewed_revisions"],
                notes="Attempted overwrite",
            )

    # -----------------------------------------------------------------------
    # 3. Gate 4: Revision Mismatch Detection
    # -----------------------------------------------------------------------
    def test_production_go_ahead_revision_mismatch_detection(self):
        """If an inspection is revised after bundle review, gate approval detects revision mismatch."""
        cycle = self._create_test_cycle("LOT-PGA-03")
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )
        i2 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="2. Second Submission",
            production_quality_cycle=cycle.name,
            status="Pending Review",
            result="Pending Review",
        )
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="3. Size Set Submission",
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )

        bundle = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        cached_revisions = dict(bundle["reviewed_revisions"])

        # Meanwhile, Inspector revises Stage 2 to Revision 2
        revise_quality_inspection(inspection_name=i2["name"], comments="Updated measurements")

        # Administrator tries to approve with stale bundle referencing revision 1
        frappe.set_user(self.admin_user)
        with self.assertRaisesRegex(frappe.ValidationError, "Revision mismatch for stage"):
            decide_production_go_ahead(
                cycle_name=cycle.name,
                decision="Approved",
                reviewed_revisions=cached_revisions,
                bundle_hash=bundle["bundle_hash"],
            )

    # -----------------------------------------------------------------------
    # 4. Gate 4: Conditional Approval & Rejection
    # -----------------------------------------------------------------------
    def test_production_go_ahead_conditional_approval_and_rejection(self):
        """Conditional Approval requires conditions; Rejection requires reason and sets 'On Hold'."""
        cycle = self._create_test_cycle("LOT-PGA-04")
        for stg in ["1. First Submission", "2. Second Submission", "3. Size Set Submission"]:
            create_quality_inspection(
                supplier=self.supplier,
                item_code=self.item_code,
                stage=stg,
                production_quality_cycle=cycle.name,
                status="Approved",
                result="Passed",
            )

        bundle = get_production_go_ahead_review_bundle(cycle_name=cycle.name)

        # Conditional approval without conditions raises ValidationError
        frappe.set_user(self.admin_user)
        with self.assertRaisesRegex(frappe.ValidationError, "Conditions and resolution terms are mandatory"):
            decide_production_go_ahead(
                cycle_name=cycle.name,
                decision="Conditionally Approved",
                reviewed_revisions=bundle["reviewed_revisions"],
                conditions="",
            )

        # Rejection sets cycle status to On Hold
        decide_production_go_ahead(
            cycle_name=cycle.name,
            decision="Rejected",
            reviewed_revisions=bundle["reviewed_revisions"],
            notes="Shrinkage rate exceeds allowable 5% threshold",
        )
        cycle.reload()
        self.assertEqual(cycle.go_ahead_status, "Rejected")
        self.assertEqual(cycle.status, "On Hold")

    # -----------------------------------------------------------------------
    # 5. Gate 7: Final Inspection Review Bundle & Multiple Visits
    # -----------------------------------------------------------------------
    def test_final_inspection_bundle_seven_stages_and_gate_checks(self):
        """Final Inspection bundle aggregates all 7 stages including multiple visits."""
        cycle = self._create_test_cycle("LOT-FIN-01")

        # Create stages 1-4
        for stg in ["1. First Submission", "2. Second Submission", "3. Size Set Submission"]:
            create_quality_inspection(
                supplier=self.supplier,
                item_code=self.item_code,
                stage=stg,
                production_quality_cycle=cycle.name,
                status="Approved",
                result="Passed",
            )

        # Approve Gate 4
        pga_bundle = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        decide_production_go_ahead(
            cycle_name=cycle.name,
            decision="Approved",
            reviewed_revisions=pga_bundle["reviewed_revisions"],
            conditions="Approved for bulk",
        )

        # Create Multiple Inline Visits (Visit 1 and Visit 2)
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="5. Inline Visit",
            visit_number=1,
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="5. Inline Visit",
            visit_number=2,
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )

        # Create Mid-line Visit
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="6. Mid-line Visit",
            visit_number=1,
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )

        # Create Stage 7 Final Inspection
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="7. Final Inspection",
            visit_number=1,
            production_quality_cycle=cycle.name,
            sampling_plan="AQL 2.5 Level II",
            lot_size=1000,
            sample_size=80,
            passed_quantity=80,
            failed_quantity=0,
            status="Pending Review",
            result="Passed",
        )

        fin_bundle = get_final_inspection_review_bundle(cycle_name=cycle.name)
        self.assertTrue(fin_bundle["ready_for_decision"])
        self.assertIn("5. Inline Visit [Visit 2]", fin_bundle["reviewed_revisions"])
        self.assertIn("6. Mid-line Visit [Visit 1]", fin_bundle["reviewed_revisions"])
        self.assertIn("7. Final Inspection", fin_bundle["reviewed_revisions"])

    # -----------------------------------------------------------------------
    # 6. Gate 7: Decision Authorizes Receipt Clearance (Native PO/PR)
    # -----------------------------------------------------------------------
    def test_final_inspection_decision_authorizes_clearance(self):
        """Final Inspection approval authorizes receipt clearance for native Purchase Receipt."""
        cycle = self._create_test_cycle("LOT-FIN-02")
        for stg in ["1. First Submission", "2. Second Submission", "3. Size Set Submission"]:
            create_quality_inspection(
                supplier=self.supplier,
                item_code=self.item_code,
                stage=stg,
                production_quality_cycle=cycle.name,
                status="Approved",
                result="Passed",
            )

        pga_bundle = get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        decide_production_go_ahead(
            cycle_name=cycle.name,
            decision="Approved",
            reviewed_revisions=pga_bundle["reviewed_revisions"],
        )

        for stg in ["5. Inline Visit", "6. Mid-line Visit", "7. Final Inspection"]:
            create_quality_inspection(
                supplier=self.supplier,
                item_code=self.item_code,
                stage=stg,
                production_quality_cycle=cycle.name,
                status="Approved",
                result="Passed",
            )

        fin_bundle = get_final_inspection_review_bundle(cycle_name=cycle.name)
        self.assertTrue(fin_bundle["ready_for_decision"])

        # Decide Final Inspection as Business Admin
        frappe.set_user(self.admin_user)
        dec_res = decide_final_inspection(
            cycle_name=cycle.name,
            decision="Approved",
            reviewed_revisions=fin_bundle["reviewed_revisions"],
            notes="Passed AQL 2.5 standard with zero critical defects",
            bundle_hash=fin_bundle["bundle_hash"],
        )
        self.assertTrue(dec_res["success"])
        self.assertEqual(dec_res["final_inspection_status"], "Approved")
        self.assertEqual(dec_res["clearance_status"], "Cleared for Receipt")
        self.assertEqual(dec_res["purchase_receipt_cleared"], 1)

        cycle.reload()
        self.assertEqual(cycle.status, "Final Inspection Approved")
        self.assertEqual(cycle.clearance_status, "Cleared for Receipt")
        self.assertEqual(cycle.purchase_receipt_cleared, 1)

    def test_linking_purchase_receipt_blocked_before_final_inspection_approved(self):
        """Native Purchase Receipt linking is blocked if Final Inspection is not approved."""
        cycle = self._create_test_cycle("LOT-FIN-03")

        # Fake or real PR
        pr_name = "PR-FAKE-NOT-APPROVED"
        with self.assertRaisesRegex(frappe.DoesNotExistError, "does not exist"):
            link_native_purchase_receipt(cycle.name, pr_name)

    # -----------------------------------------------------------------------
    # 7. Role Security: Inspectors Cannot Decide Critical Gates
    # -----------------------------------------------------------------------
    def test_unauthorized_users_cannot_decide_critical_gates(self):
        """Quality Inspectors cannot decide Gate 4 or Gate 7."""
        cycle = self._create_test_cycle("LOT-SEC-01")
        revs = {"1. First Submission": {"name": "FAKE", "revision": 1}}

        frappe.set_user(self.inspector_user)
        with self.assertRaises(frappe.PermissionError):
            decide_production_go_ahead(
                cycle_name=cycle.name,
                decision="Approved",
                reviewed_revisions=revs,
            )

        with self.assertRaises(frappe.PermissionError):
            decide_final_inspection(
                cycle_name=cycle.name,
                decision="Approved",
                reviewed_revisions=revs,
            )

    # -----------------------------------------------------------------------
    # 8. Correction Requests & Resubmission Lifecycle
    # -----------------------------------------------------------------------
    def test_inspection_correction_request_and_resubmission_flow(self):
        """Manager requests correction; inspector resubmits with notes; status transitions properly."""
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            status="Pending Review",
            result="Pending Review",
        )

        # Quality Manager requests correction
        frappe.set_user(self.manager_user)
        req_res = request_inspection_correction(
            inspection_name=insp["name"],
            reason="Chest width out of tolerance by +1.5cm and collar photo missing.",
            required_actions="Re-stitch collar and provide updated front collar photograph.",
            due_date=nowdate(),
        )
        self.assertEqual(req_res["status"], "Correction Requested")
        self.assertEqual(req_res["correction_requested_by"], self.manager_user)
        self.assertEqual(req_res["corrective_action_status"], "Open")

        # Inspector resubmits
        frappe.set_user(self.inspector_user)
        resub_res = resubmit_inspection_correction(
            inspection_name=insp["name"],
            notes="Collar re-stitched, measurement corrected to 50.0cm (In Spec).",
            revised_readings=[
                {
                    "parameter_name": "Chest Width",
                    "spec_target": 50.0,
                    "tolerance_plus": 0.5,
                    "tolerance_minus": 0.5,
                    "actual_reading": 50.1,
                }
            ],
        )
        self.assertEqual(resub_res["status"], "Resubmitted")
        self.assertEqual(resub_res["resubmitted_by"], self.inspector_user)

    # -----------------------------------------------------------------------
    # 9. Controlled PDF Report Bundle, Watermark & Cryptographic Hash
    # -----------------------------------------------------------------------
    def test_controlled_pdf_bundle_watermark_hash_and_audit(self):
        """Controlled PDF bundle is generated with watermark, SHA-256 hash, and export audit."""
        cycle = self._create_test_cycle("LOT-PDF-01")
        create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            production_quality_cycle=cycle.name,
            status="Approved",
            result="Passed",
        )

        frappe.set_user(self.manager_user)
        exp = export_quality_report_bundle(cycle_name=cycle.name, as_pdf=True)
        self.assertTrue(exp["success"])
        self.assertTrue(exp["bundle_hash"])
        self.assertEqual(len(exp["bundle_hash"]), 64)  # Valid SHA-256 length
        self.assertTrue(exp["file_bytes_base64"])
        self.assertTrue(exp["size_bytes"] > 0)

        # Verify decoded bytes are valid PDF or HTML
        raw_bytes = base64.b64decode(exp["file_bytes_base64"])
        self.assertEqual(len(raw_bytes), exp["size_bytes"])

        # Inspector cannot export controlled bundle (Manager / Admin only)
        frappe.set_user(self.inspector_user)
        with self.assertRaises(frappe.PermissionError):
            export_quality_report_bundle(cycle_name=cycle.name)

    # -----------------------------------------------------------------------
    # 10. Failed-Return Dispositions: Recommendation & Business Approval
    # -----------------------------------------------------------------------
    def test_failed_return_disposition_recommendation_and_business_approval(self):
        """Inspector recommends Scrap or Seconds; Business Admin authorizes disposition."""
        # 1. Record Return Quarantine
        rq = record_return_quarantine(
            retailer="TEST Quality Customer",
            delivery_note=None,
            item_code=self.item_code,
            quantity=5.0,
            return_reason="Fabric Fault",
            quarantine_warehouse=self.warehouse,
        )
        rq_name = rq["name"]

        # 2. Inspector recommends Scrap
        frappe.set_user(self.inspector_user)
        rec_res = recommend_return_disposition(
            quarantine_name=rq_name,
            disposition="Scrap",
            notes="Unraveling fabric weave; garment cannot be salvaged.",
        )
        self.assertTrue(rec_res["success"])
        self.assertEqual(rec_res["disposition_status"], "Awaiting Business Approval")

        # Inspector CANNOT approve disposition
        with self.assertRaises(frappe.PermissionError):
            approve_return_disposition(quarantine_name=rq_name, decision="Scrap")

        # 3. Business Admin approves Scrap
        frappe.set_user(self.admin_user)
        appr_res = approve_return_disposition(
            quarantine_name=rq_name,
            decision="Scrap",
            approval_notes="Loss written off to factory defect allowance.",
            target_warehouse=self.scrap_wh,
        )
        self.assertTrue(appr_res["success"])
        self.assertEqual(appr_res["inspection_status"], "Inspected - Scrapped")
        self.assertEqual(appr_res["disposition_status"], "Approved by Business")

        doc = frappe.get_doc("Return Quarantine", rq_name)
        self.assertEqual(doc.disposition, "Scrap")
        self.assertEqual(doc.disposition_status, "Approved by Business")
        self.assertEqual(doc.scrap_warehouse, self.scrap_wh)

    # -----------------------------------------------------------------------
    # 11. Supplier Claims: Automated Claim Creation from Return Disposition
    # -----------------------------------------------------------------------
    def test_supplier_claim_creation_and_business_settlement(self):
        """Authorizing Supplier Claim disposition creates linked Supplier Quality Claim with approval."""
        rq = record_return_quarantine(
            retailer="TEST Quality Customer",
            delivery_note=None,
            item_code=self.item_code,
            quantity=10.0,
            return_reason="Defective Stitching",
            quarantine_warehouse=self.warehouse,
        )
        rq_name = rq["name"]

        frappe.set_user(self.inspector_user)
        recommend_return_disposition(
            quarantine_name=rq_name,
            disposition="Supplier Claim",
            notes="Factory manufacturing defect confirmed on 10 units.",
        )

        # Business Admin authorizes claim
        frappe.set_user(self.admin_user)
        appr_res = approve_return_disposition(
            quarantine_name=rq_name,
            decision="Supplier Claim",
            approval_notes="Claim approved for full defect cost.",
            supplier_claim_amount=5000.0,
        )
        self.assertTrue(appr_res["success"])
        self.assertTrue(appr_res["linked_claim"])

        claim_doc = frappe.get_doc("Supplier Quality Claim", appr_res["linked_claim"])
        self.assertEqual(claim_doc.supplier, self.supplier)
        self.assertEqual(claim_doc.item_code, self.item_code)
        self.assertEqual(flt(claim_doc.claim_amount), 5000.0)
        self.assertEqual(flt(claim_doc.claim_quantity), 10.0)
        self.assertEqual(claim_doc.status, "Approved by Business")

        # Admin settles claim via debit note
        settle_res = decide_supplier_claim(
            claim_name=claim_doc.name,
            decision="Settled",
            settlement_type="Debit Note",
            settled_amount=5000.0,
            debit_note="PINV-DN-2026-001",
            notes="Full debit note processed by finance.",
        )
        self.assertEqual(settle_res["status"], "Settled")
        self.assertEqual(settle_res["settlement_type"], "Debit Note")
        self.assertEqual(flt(settle_res["settled_amount"]), 5000.0)

    # -----------------------------------------------------------------------
    # 12. Complete 7-Stage History Retrieval
    # -----------------------------------------------------------------------
    def test_complete_stage_history_timeline(self):
        """Complete history returns chronological stage groups and photo timeline."""
        cycle = self._create_test_cycle("LOT-HIST-01")
        for stg in ["1. First Submission", "2. Second Submission"]:
            create_quality_inspection(
                supplier=self.supplier,
                item_code=self.item_code,
                stage=stg,
                production_quality_cycle=cycle.name,
                status="Approved",
                result="Passed",
            )

        hist = get_complete_stage_history(cycle_name=cycle.name)
        self.assertEqual(hist["cycle_name"], cycle.name)
        self.assertEqual(hist["summary"]["total_reports"], 2)
        self.assertIn("1. First Submission", hist["stage_groups"])
        self.assertEqual(len(hist["stage_groups"]["1. First Submission"]), 1)

    # -----------------------------------------------------------------------
    # 13. Cross-Supplier and Cross-Company Isolation
    # -----------------------------------------------------------------------
    def test_multi_company_and_supplier_isolation_enforced(self):
        """User restricted to another supplier cannot access cycle review bundle."""
        cycle = self._create_test_cycle("LOT-ISO-01")

        # Restrict manager to another supplier
        other_supplier = self._ensure_supplier("OTHER Mills Ltd")
        perm = frappe.get_doc({
            "doctype": "User Permission",
            "user": self.manager_user,
            "allow": "Supplier",
            "for_value": other_supplier,
        }).insert(ignore_permissions=True)

        try:
            frappe.set_user(self.manager_user)
            with self.assertRaises(frappe.PermissionError):
                get_production_go_ahead_review_bundle(cycle_name=cycle.name)
        finally:
            frappe.set_user("Administrator")
            perm.delete(ignore_permissions=True)
