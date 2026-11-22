# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from quality_erp.quality import (
    create_quality_inspection,
    get_quality_review_bundle,
    inspect_return_quarantine,
    record_return_quarantine,
    revise_quality_inspection,
)
from quality_erp.seed import seed_quality_data


class TestQualityEvidence(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.setup_module_map()
        if not hasattr(frappe.local, "module_app") or not frappe.local.module_app:
            frappe.local.module_app = {}
        frappe.local.module_app["quality_erp"] = "quality_erp"
        frappe.set_user("Administrator")
        seed_quality_data()
        self.supplier = "TEST Fabric & Stitch Mills"
        self.item_code = "TEST-CLASSIC-TEE-BLK"
        self.customer = "TEST Quality Customer"

        if not frappe.db.exists("Supplier", self.supplier):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": self.supplier,
                "supplier_group": "Raw Material",
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Customer", self.customer):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": self.customer,
                "customer_group": "Commercial",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_create_inspection_with_multi_photo_evidence(self):
        frappe.set_user("Administrator")
        evidence = [
            {"file": "/private/files/fit1.jpg", "caption": "Collar stitching", "evidence_type": "Fit Sample", "display_order": 0},
            {"file": "/private/files/fit2.jpg", "caption": "Buttonhole alignment", "evidence_type": "Stitching Defect", "display_order": 1},
        ]
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            spec_notes="Collar 14.5 inch",
            photo_evidence=None,
            evidence_photos=evidence,
        )

        doc = frappe.get_doc("Supplier Quality Inspection", insp["name"])
        self.assertEqual(len(doc.evidence_photos), 2)
        self.assertEqual(doc.evidence_photos[0].file, "/private/files/fit1.jpg")
        self.assertEqual(doc.evidence_photos[0].evidence_type, "Fit Sample")
        self.assertEqual(doc.evidence_photos[0].uploader, "Administrator")
        self.assertEqual(doc.evidence_photos[0].revision, 1)
        self.assertEqual(doc.photo_evidence, "/private/files/fit1.jpg")

    def test_revise_inspection_preserves_historical_evidence(self):
        frappe.set_user("Administrator")
        initial_photos = [
            {"file": "/private/files/rev1_defect.jpg", "caption": "Initial defect", "evidence_type": "Fabric Defect"},
        ]
        insp1 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            evidence_photos=initial_photos,
        )

        # Revise report with corrected photo
        revised_photos = [
            {"file": "/private/files/rev2_fixed.jpg", "caption": "Corrected fabric patch", "evidence_type": "Refit Sample"},
        ]
        insp2 = revise_quality_inspection(
            inspection_name=insp1["name"],
            spec_notes="Fabric replaced with 100% combed cotton",
            evidence_photos=revised_photos,
        )

        doc2 = frappe.get_doc("Supplier Quality Inspection", insp2["name"])
        self.assertEqual(doc2.revision, 2)
        self.assertEqual(doc2.supersedes, insp1["name"])
        # Both prior and new photos must be preserved!
        self.assertEqual(len(doc2.evidence_photos), 2)
        self.assertEqual(doc2.evidence_photos[0].file, "/private/files/rev1_defect.jpg")
        self.assertEqual(doc2.evidence_photos[0].revision, 1)  # Preserved original revision
        self.assertEqual(doc2.evidence_photos[1].file, "/private/files/rev2_fixed.jpg")
        self.assertEqual(doc2.evidence_photos[1].revision, 2)  # New revision tag

    def test_return_quarantine_multi_photo_inspection(self):
        frappe.set_user("Administrator")
        quarantine = record_return_quarantine(
            retailer=self.customer,
            delivery_note=None,
            item_code=self.item_code,
            quantity=5,
            return_reason="Defective Stitching",
        )

        defect_photos = [
            {"file": "/private/files/tear1.jpg", "caption": "Sleeve tear", "evidence_type": "Quarantine Defect"},
            {"file": "/private/files/stain2.jpg", "caption": "Ink stain on back", "evidence_type": "Fabric Defect"},
        ]
        inspected = inspect_return_quarantine(
            quarantine_name=quarantine["name"],
            decision="Passed Refurbishment",
            notes="Tear repairable in refurbishment workshop",
            evidence_photos=defect_photos,
        )

        q_doc = frappe.get_doc("Return Quarantine", quarantine["name"])
        self.assertEqual(len(q_doc.evidence_photos), 2)
        self.assertEqual(q_doc.photo_evidence, "/private/files/tear1.jpg")
        self.assertIn("Inspected - Passed Refurbishment", q_doc.inspection_status)

    def test_review_bundle_includes_all_evidence_photos(self):
        frappe.set_user("Administrator")
        evidence = [
            {"file": "/private/files/stage1_1.jpg", "caption": "Pre-production fit", "evidence_type": "Fit Sample"},
        ]
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            evidence_photos=evidence,
        )
        frappe.db.set_value("Supplier Quality Inspection", insp["name"], "status", "Approved")

        bundle = get_quality_review_bundle(
            supplier=self.supplier,
            item_code=self.item_code,
            gate="4. Production Go Ahead",
        )
        stage_report = bundle["stage_reports"].get("1. First Submission")
        self.assertIsNotNone(stage_report)
        self.assertTrue(len(stage_report.get("evidence_photos", [])) >= 1)
        self.assertEqual(stage_report["evidence_photos"][0]["file"], "/private/files/stage1_1.jpg")
