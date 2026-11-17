"""Unit and integration tests for Quality ERP."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase

from quality_erp.boot import restrict_quality_app_visibility
from quality_erp.quality import (
    approve_quality_gate,
    create_quality_inspection,
    get_quality_review_bundle,
    record_return_quarantine,
    reject_quality_gate,
    revise_quality_inspection,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)
from quality_erp.seed import (
    SEED_QUALITY_INSPECTOR,
    SEED_QUALITY_MANAGER,
    seed_quality_data,
)


class TestQualityERP(FrappeTestCase):
    def setUp(self):
        super().setUp()
        from collections import defaultdict
        frappe.local.request_cache = defaultdict(dict)
        frappe.set_user("Administrator")
        frappe.db.sql("DELETE FROM `tabSupplier Quality Inspection`")
        frappe.db.commit()
        seed_quality_data()
        self.inspector = SEED_QUALITY_INSPECTOR
        self.manager = SEED_QUALITY_MANAGER
        self.supplier = "TEST Fabric & Stitch Mills"

        if not frappe.db.exists("Supplier", self.supplier):
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": self.supplier,
                    "supplier_group": "All Supplier Groups",
                }
            ).insert(ignore_permissions=True)

        if not frappe.db.exists("Customer", "TEST Quality Customer"):
            frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": "TEST Quality Customer",
                    "customer_group": "Commercial",
                    "territory": "All Territories",
                }
            ).insert(ignore_permissions=True)

    def test_quality_user_app_isolation(self):
        """Quality inspector must only see Quality ERP on the apps screen."""
        frappe.set_user(self.inspector)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                    {"app_name": "insights", "on_apps_screen": True},
                    {"app_name": "india_compliance", "on_apps_screen": True},
                ]
            }
        )
        restrict_quality_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertEqual(visible, ["quality_erp"])

    def test_admin_sees_all_apps(self):
        """Administrator must retain access to all apps."""
        frappe.set_user("Administrator")
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                ]
            }
        )
        restrict_quality_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertIn("quality_erp", visible)
        self.assertIn("sales_erp", visible)
        self.assertIn("warehouse_erp", visible)
        self.assertIn("erpnext", visible)

    def test_quality_inspection_creation_rejection_and_versioning(self):
        """Inspector can create quality inspections, reject with reason, and submit versioned revisions."""
        frappe.set_user(self.inspector)
        doc = create_quality_inspection(
            supplier=self.supplier,
            item_code="TEST-CLASSIC-TEE-BLK",
            stage="1. First Submission",
            spec_notes="Chest 38cm, Length 68cm",
        )
        self.assertEqual(doc["status"], "Pending Review")
        self.assertEqual(doc["revision"], 1)

        # Rejection requires reason
        with self.assertRaises(frappe.ValidationError):
            reject_quality_gate(doc["name"], reason="")

        rejected = reject_quality_gate(doc["name"], reason="Sleeve length out of spec")
        self.assertEqual(rejected["status"], "Rejected")
        self.assertIn("Sleeve length out of spec", rejected["comments"])

        # Create versioned revision
        rev = revise_quality_inspection(
            doc["name"],
            spec_notes="Chest 38cm, Length 68cm, Sleeve corrected to 22cm",
        )
        self.assertEqual(rev["revision"], 2)
        self.assertEqual(rev["supersedes"], doc["name"])
        self.assertEqual(rev["status"], "Pending Review")

        # Approve the revision
        approved = approve_quality_gate(rev["name"], notes="Correction verified")
        self.assertEqual(approved["status"], "Approved")

    def test_strict_7_stage_lifecycle_and_critical_gates(self):
        """Enforce strict prerequisite ordering across the 7 stages and Admin gate controls."""
        item = "TEST-CLASSIC-TEE-BLK"

        # 1. First submission (Stage 1) - no prerequisites
        frappe.set_user(self.inspector)
        stg1 = create_quality_inspection(self.supplier, item, "1. First Submission")
        # Attempting Stage 2 before Stage 1 approved must fail
        stg2 = create_quality_inspection(self.supplier, item, "2. Second Submission")
        with self.assertRaisesRegex(frappe.ValidationError, "prerequisite stage"):
            approve_quality_gate(stg2["name"])

        # Approve Stage 1
        approve_quality_gate(stg1["name"], notes="Stage 1 approved")

        # Now Stage 2 can be approved
        approve_quality_gate(stg2["name"], notes="Stage 2 approved")

        # Stage 3 (Size Set Submission)
        stg3 = create_quality_inspection(self.supplier, item, "3. Size Set Submission")
        approve_quality_gate(stg3["name"], notes="Stage 3 approved")

        # Review bundle before Stage 4 approval shows prerequisites satisfied
        frappe.set_user(self.manager)
        bundle_pga = get_quality_review_bundle(self.supplier, item, gate="Production Go Ahead")
        self.assertTrue(bundle_pga["ready_for_approval"])
        self.assertEqual(len(bundle_pga["missing_prerequisites"]), 0)

        # Stage 4 (Production Go Ahead) requires Administrator gate sign-off
        frappe.set_user(self.inspector)
        stg4 = create_quality_inspection(self.supplier, item, "4. Production Go Ahead")
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(stg4["name"])

        frappe.set_user(self.manager)
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(stg4["name"])

        frappe.set_user("Administrator")
        appr_stg4 = approve_quality_gate(stg4["name"], notes="Admin PGA sign-off")
        self.assertEqual(appr_stg4["status"], "Approved")

        # Stage 5 (Inline Visit) and Stage 6 (Mid-line Visit)
        frappe.set_user(self.inspector)
        stg5 = create_quality_inspection(self.supplier, item, "5. Inline Visit")
        approve_quality_gate(stg5["name"])

        stg6 = create_quality_inspection(self.supplier, item, "6. Mid-line Visit")
        approve_quality_gate(stg6["name"])

        # Stage 7 (Final Inspection) requires all prior 6 stages + Administrator approval
        stg7 = create_quality_inspection(self.supplier, item, "7. Final Inspection")
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(stg7["name"])

        frappe.set_user("Administrator")
        appr_stg7 = approve_quality_gate(stg7["name"], notes="Final release approved")
        self.assertEqual(appr_stg7["status"], "Approved")

        # Review bundle for Final Inspection shows full history
        bundle_final = get_quality_review_bundle(self.supplier, item, gate="Final Inspection")
        self.assertTrue(bundle_final["ready_for_approval"])
        self.assertEqual(len(bundle_final["missing_prerequisites"]), 0)
        self.assertEqual(len(bundle_final["stage_reports"]), 7)

    def test_return_quarantine_intake(self):
        """Inspector can intake goods into return quarantine."""
        frappe.set_user(self.inspector)
        doc = record_return_quarantine(
            retailer="TEST Quality Customer",
            delivery_note=None,
            item_code="TEST-CLASSIC-TEE-BLK",
            quantity=5,
            return_reason="Defective Stitching",
        )
        self.assertEqual(doc["inspection_status"], "Quarantined")
        self.assertEqual(doc["quantity"], 5.0)
        self.assertEqual(doc["inspected_by"], self.inspector)

    def test_quality_runtime_scoping(self):
        """Quality users only see quality_erp and Quality ERP workspace."""
        from frappe.apps import get_apps
        from frappe.desk.desktop import get_workspaces

        for user in [self.inspector, self.manager]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            apps = [a["name"] for a in get_apps()]
            self.assertEqual(apps, ["quality_erp"])

            ws_pages = [w["name"] for w in get_workspaces()["pages"]]
            self.assertEqual(ws_pages, ["Quality ERP"])

    def test_cross_app_quality_access_denied(self):
        """Users outside quality roles cannot create quality inspections or record quarantine."""
        for user in ["test-asm-south@example.invalid", "test-warehouse-operator@example.invalid"]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            with self.assertRaises(frappe.PermissionError):
                create_quality_inspection(
                    supplier=self.supplier,
                    item_code="TEST-CLASSIC-TEE-BLK",
                    stage="1. First Submission",
                )

            with self.assertRaises(frappe.PermissionError):
                record_return_quarantine(
                    retailer="TEST Quality Customer",
                    delivery_note=None,
                    item_code="TEST-CLASSIC-TEE-BLK",
                    quantity=1,
                    return_reason="Defective Stitching",
                )
