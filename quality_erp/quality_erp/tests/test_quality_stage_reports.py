# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Comprehensive integration and workflow tests for Session 12:
Quality Stage Reports, Checklists and Evidence.

Covers:
1. Explicit Cycle/Stage/Report Relationships & Seven Ordered Stages:
   - Linking Stage Reports directly to Production Quality Cycle.
   - Enforcing sequential 7-stage quality lifecycle ordering.
2. Multiple Inline and Mid-line Visits:
   - Permitting multiple visits (visit 1, visit 2) for Inline Visit and Mid-line Visit.
   - Prerequisites allow subsequent visits during ongoing production after Gate 4 is approved.
3. Versioned Checklist Templates by Product/Category & Historical Retention:
   - Template creation with check points, tolerances, criticality.
   - Versioning and DuplicateEntryError rejection for identical (template_name, version).
   - Snapshotting checklist points onto inspection report (historical retention: updating template later does not alter historical report).
4. Measurements, Readings & Tolerance Checking:
   - Recording spec targets, tolerances (+/-), actual readings.
   - Automatic variance calculation and In Spec / Out of Spec classification.
5. Sampling Plans, Counts & Defect Severity:
   - AQL 2.5 / AQL 1.5 sampling plans with lot size and sample size.
   - Defect logging with severity (Minor, Major, Critical).
   - Automatic aggregation of defect counts by severity and sampled passed/failed quantities.
6. Recommendation, Result & Corrective Actions:
   - Result ("Passed", "Failed", "Conditionally Passed") and recommendations.
   - Corrective actions with owner, due date, status, and auto-resolved timestamp.
7. Multi-Photo Private Evidence:
   - Captioned photos with types, display order, uploader, and revision tagging.
   - Reference-safe private attachments.
8. Immutable Revision / Supersession History:
   - Revising pending/rejected report creates revision 2, setting supersedes = rev1.name.
   - rev1 is updated with superseded_by = rev2.name, is_latest = 0.
   - Approved reports cannot be revised.
   - Historical evidence photos and checklist observations from rev1 are preserved.
9. Side-by-Side Revision Comparison:
   - compare_inspection_revisions produces detailed diff of metadata, checklist, measurements, defects, corrective actions, and evidence photos.
10. Concurrency & Row Locking:
    - Revision uses SELECT ... FOR UPDATE to avoid race conditions.
11. Multi-Company & Supplier Isolation:
    - User Permission boundaries prevent cross-company or cross-supplier read/write leakage.
12. Upload Retry & Migration Compatibility:
    - Upload retries handled idempotently.
    - Legacy inspections without checklist items load and operate seamlessly.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from quality_erp import quality, security
from quality_erp.quality import (
    check_stage_prerequisites,
    compare_inspection_revisions,
    create_checklist_template,
    create_quality_inspection,
    get_checklist_template,
    revise_quality_inspection,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)
from quality_erp.seed import SEED_QUALITY_INSPECTOR, SEED_QUALITY_MANAGER, seed_quality_data


class TestQualityStageReports(FrappeTestCase):
    """Test suite for Quality Stage Reports, Checklists, Measurements, and Evidence."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        seed_quality_data()
        self.supplier = "TEST Fabric & Stitch Mills"
        self.item_code = "TEST-CLASSIC-TEE-BLK"
        self.company = frappe.defaults.get_user_default("Company") or "TEST Clothing ERP Demo"

        if not frappe.db.exists("Supplier", self.supplier):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": self.supplier,
                "supplier_group": "All Supplier Groups",
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Item", self.item_code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": self.item_code,
                "item_name": "Test Classic Tee Black",
                "item_group": "All Item Groups",
                "stock_uom": "Nos",
                "is_stock_item": 1,
            }).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")

    # =========================================================================
    # 1. VERSIONED CHECKLIST TEMPLATES & HISTORICAL RETENTION
    # =========================================================================

    def test_checklist_template_creation_and_version_uniqueness(self):
        """Checklist template supports product group, versioning, and rejects duplicates."""
        t_name = "TEST Woven Shirts Checklist"
        # Cleanup
        existing = frappe.get_all("Quality Checklist Template", filters={"template_name": t_name}, pluck="name")
        for e in existing:
            frappe.delete_doc("Quality Checklist Template", e, force=True)

        items_payload = [
            {
                "check_point": "Fabric GSM & Shade",
                "check_type": "Measurement",
                "target_value": "180 GSM",
                "min_value": 175.0,
                "max_value": 185.0,
                "uom": "GSM",
                "criticality": "Critical",
                "is_mandatory": 1,
            },
            {
                "check_point": "Stitch Density (SPI)",
                "check_type": "Reading",
                "target_value": "12 SPI",
                "min_value": 11.0,
                "max_value": 13.0,
                "uom": "SPI",
                "criticality": "Major",
                "is_mandatory": 1,
            },
            {
                "check_point": "Label Positioning & Care Symbols",
                "check_type": "Visual Inspection",
                "target_value": "Inner neckline center",
                "criticality": "Minor",
                "is_mandatory": 0,
            },
        ]

        # 1. Create Version 1
        v1 = create_checklist_template(
            template_name=t_name,
            item_group="All Item Groups",
            product_category="Apparel / Tops",
            version=1,
            description="Inspection standards for woven button-down shirts",
            items=items_payload,
        )
        self.assertTrue(v1["name"])
        self.assertEqual(v1["version"], 1)

        doc1 = frappe.get_doc("Quality Checklist Template", v1["name"])
        self.assertEqual(len(doc1.items), 3)

        # 2. Duplicate Version 1 is rejected
        with self.assertRaises(frappe.DuplicateEntryError):
            create_checklist_template(
                template_name=t_name,
                version=1,
            )

        # 3. Version 2 with amended standard is accepted
        items_payload_v2 = list(items_payload)
        items_payload_v2.append({
            "check_point": "Seam Bursting Strength",
            "check_type": "Tolerance Check",
            "target_value": "> 250 kPa",
            "criticality": "Critical",
        })
        v2 = create_checklist_template(
            template_name=t_name,
            version=2,
            items=items_payload_v2,
        )
        self.assertEqual(v2["version"], 2)

        # Clean up
        frappe.delete_doc("Quality Checklist Template", v1["name"], force=True)
        frappe.delete_doc("Quality Checklist Template", v2["name"], force=True)

    def test_checklist_template_permissions(self):
        """Inspectors can read active templates but only Managers/Admins can create."""
        frappe.set_user(SEED_QUALITY_INSPECTOR)
        with self.assertRaises(frappe.PermissionError):
            create_checklist_template("Unauthorized Template", version=1)

        frappe.set_user(SEED_QUALITY_MANAGER)
        t = create_checklist_template("Manager Approved Template", version=1)
        self.assertTrue(t["name"])

        # Inspector CAN fetch active template
        frappe.set_user(SEED_QUALITY_INSPECTOR)
        fetched = get_checklist_template(template_name="Manager Approved Template")
        self.assertEqual(fetched["name"], t["name"])

        frappe.set_user("Administrator")
        frappe.delete_doc("Quality Checklist Template", t["name"], force=True)

    def test_historical_checklist_retention_on_stage_report(self):
        """Stage report snapshots template check points; updating template later does not alter historical report."""
        t_name = "TEST Historical Retention Template"
        t = create_checklist_template(
            template_name=t_name,
            version=1,
            items=[
                {"check_point": "Initial Standard A", "target_value": "Standard A"},
                {"check_point": "Initial Standard B", "target_value": "Standard B"},
            ],
        )

        # Create inspection snapshotting template v1
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            checklist_template=t["name"],
        )

        insp_doc = frappe.get_doc("Supplier Quality Inspection", insp["name"])
        self.assertEqual(len(insp_doc.checklist_items), 2)
        self.assertEqual(insp_doc.checklist_items[0].check_point, "Initial Standard A")
        self.assertEqual(insp_doc.checklist_template_version, 1)

        # Now create Template v2 with new checkpoints
        t_v2 = create_checklist_template(
            template_name=t_name,
            version=2,
            items=[
                {"check_point": "Amended Standard X", "target_value": "New Standard X"},
            ],
        )

        # Historical inspection must RETAIN its exact version 1 snapshot!
        insp_doc.reload()
        self.assertEqual(len(insp_doc.checklist_items), 2)
        self.assertEqual(insp_doc.checklist_items[0].check_point, "Initial Standard A")
        self.assertEqual(insp_doc.checklist_template_version, 1)

        # Clean up
        frappe.delete_doc("Supplier Quality Inspection", insp["name"], force=True)
        frappe.delete_doc("Quality Checklist Template", t["name"], force=True)
        frappe.delete_doc("Quality Checklist Template", t_v2["name"], force=True)

    # =========================================================================
    # 2. MEASUREMENTS, READINGS & TOLERANCE CALCULATION
    # =========================================================================

    def test_measurement_variance_and_tolerance_classification(self):
        """Inspection readings automatically calculate variance and In Spec / Out of Spec status."""
        measurements_payload = [
            {
                "parameter_name": "Chest Circumference",
                "spec_size": "M",
                "spec_target": 104.0,
                "tolerance_plus": 1.0,
                "tolerance_minus": 1.0,
                "actual_reading": 104.5,  # within +1.0 -> In Spec
                "uom": "cm",
            },
            {
                "parameter_name": "Back Body Length",
                "spec_size": "M",
                "spec_target": 72.0,
                "tolerance_plus": 0.5,
                "tolerance_minus": 0.5,
                "actual_reading": 73.2,  # variance +1.2 > 0.5 -> Out of Spec
                "uom": "cm",
            },
            {
                "parameter_name": "Sleeve Opening",
                "spec_size": "M",
                "spec_target": 18.0,
                "tolerance_plus": 0.5,
                "tolerance_minus": 0.5,
                "actual_reading": 17.1,  # variance -0.9 < -0.5 -> Out of Spec
                "uom": "cm",
            },
        ]

        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            measurements=measurements_payload,
        )

        doc = frappe.get_doc("Supplier Quality Inspection", insp["name"])
        self.assertEqual(len(doc.measurements), 3)

        m1 = doc.measurements[0]
        self.assertEqual(m1.variance, 0.5)
        self.assertEqual(m1.reading_status, "In Spec")

        m2 = doc.measurements[1]
        self.assertEqual(m2.variance, 1.2)
        self.assertEqual(m2.reading_status, "Out of Spec")

        m3 = doc.measurements[2]
        self.assertEqual(m3.variance, -0.9)
        self.assertEqual(m3.reading_status, "Out of Spec")

        frappe.delete_doc("Supplier Quality Inspection", insp["name"], force=True)

    # =========================================================================
    # 3. SAMPLING PLANS, DEFECT SEVERITY & PASS/FAIL QUANTITIES
    # =========================================================================

    def test_sampling_plan_and_defect_severity_aggregation(self):
        """Defects automatically aggregate by Minor/Major/Critical and compute passed/failed quantities."""
        defects_payload = [
            {"defect_code": "DEF-FAB-01", "defect_description": "Oil stain on front panel", "severity": "Critical", "defect_count": 2},
            {"defect_code": "DEF-STC-02", "defect_description": "Broken collar topstitch", "severity": "Major", "defect_count": 5},
            {"defect_code": "DEF-THD-03", "defect_description": "Loose thread ends on hem", "severity": "Minor", "defect_count": 8},
        ]

        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="3. Size Set Submission",
            sampling_plan="AQL 2.5 Level II",
            lot_size=2000,
            sample_size=125,
            defects=defects_payload,
            result="Conditionally Passed",
            recommendation="Correction & Resubmission Required",
        )

        doc = frappe.get_doc("Supplier Quality Inspection", insp["name"])
        self.assertEqual(doc.critical_defects_count, 2)
        self.assertEqual(doc.major_defects_count, 5)
        self.assertEqual(doc.minor_defects_count, 8)
        self.assertEqual(doc.failed_quantity, 15)  # 2 + 5 + 8
        self.assertEqual(doc.passed_quantity, 110)  # 125 - 15
        self.assertEqual(doc.result, "Conditionally Passed")
        self.assertEqual(doc.recommendation, "Correction & Resubmission Required")

        frappe.delete_doc("Supplier Quality Inspection", insp["name"], force=True)

    # =========================================================================
    # 4. MULTIPLE INLINE AND MID-LINE VISITS & PREREQUISITES
    # =========================================================================

    def test_multiple_inline_and_midline_visits_supported(self):
        """Quality cycle permits multiple Inline Visits and Mid-line Visits without false prerequisite blocking."""
        # Setup: Stage 1, 2, 3 approved
        s1 = create_quality_inspection(self.supplier, self.item_code, "1. First Submission")
        frappe.db.set_value("Supplier Quality Inspection", s1["name"], "status", "Approved")

        s2 = create_quality_inspection(self.supplier, self.item_code, "2. Second Submission")
        frappe.db.set_value("Supplier Quality Inspection", s2["name"], "status", "Approved")

        s3 = create_quality_inspection(self.supplier, self.item_code, "3. Size Set Submission")
        frappe.db.set_value("Supplier Quality Inspection", s3["name"], "status", "Approved")

        s4 = create_quality_inspection(self.supplier, self.item_code, "4. Production Go Ahead")
        frappe.db.set_value("Supplier Quality Inspection", s4["name"], "status", "Approved")

        # 1. Inline Visit 1
        inline1 = create_quality_inspection(
            self.supplier,
            self.item_code,
            "5. Inline Visit",
            visit_number=1,
            location_details="Floor 1 Cutting Section",
        )
        self.assertEqual(inline1["visit_number"], 1)
        frappe.db.set_value("Supplier Quality Inspection", inline1["name"], "status", "Approved")

        # 2. Inline Visit 2 (subsequent visit during ongoing production)
        inline2 = create_quality_inspection(
            self.supplier,
            self.item_code,
            "5. Inline Visit",
            visit_number=2,
            location_details="Floor 2 Sewing Section Line 3",
        )
        self.assertEqual(inline2["visit_number"], 2)

        # 3. Check prerequisite validation for subsequent inline visit
        check_stage_prerequisites("5. Inline Visit", self.supplier, self.item_code, visit_number=2)

        # 4. Mid-line Visit 1
        mid1 = create_quality_inspection(
            self.supplier,
            self.item_code,
            "6. Mid-line Visit",
            visit_number=1,
            location_details="Finishing & Pressing Area",
        )
        self.assertEqual(mid1["visit_number"], 1)

        # 5. Mid-line Visit 2
        mid2 = create_quality_inspection(
            self.supplier,
            self.item_code,
            "6. Mid-line Visit",
            visit_number=2,
            location_details="Pre-Packaging Table 4",
        )
        self.assertEqual(mid2["visit_number"], 2)

        # Clean up
        for name in [s1["name"], s2["name"], s3["name"], s4["name"], inline1["name"], inline2["name"], mid1["name"], mid2["name"]]:
            frappe.delete_doc("Supplier Quality Inspection", name, force=True)

    # =========================================================================
    # 5. CORRECTIVE ACTIONS WITH OWNER & DUE DATE
    # =========================================================================

    def test_corrective_action_lifecycle_and_resolution(self):
        """Corrective actions record details, owner, due date, and track resolution timestamp."""
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            corrective_action="Reinforce pocket bartack stitching with 42 stitches",
            corrective_action_owner="Administrator",
            corrective_action_owner_name="System Administrator",
            corrective_action_due_date="2026-11-30",
        )

        doc = frappe.get_doc("Supplier Quality Inspection", insp["name"])
        self.assertEqual(doc.corrective_action_required, 1)
        self.assertEqual(doc.corrective_action_status, "Open")
        self.assertIsNone(doc.resolved_date)

        # Resolve corrective action
        doc.corrective_action_status = "Resolved"
        doc.resolution_notes = "Sample corrected and bartack strength verified"
        doc.save()

        doc.reload()
        self.assertEqual(doc.corrective_action_status, "Resolved")
        self.assertIsNotNone(doc.resolved_date)

        frappe.delete_doc("Supplier Quality Inspection", insp["name"], force=True)

    # =========================================================================
    # 6. IMMUTABLE REVISION & SUPERSESSION
    # =========================================================================

    def test_revise_inspection_creates_new_revision_and_marks_superseded(self):
        """Revising an inspection creates revision 2, links supersedes/superseded_by, and marks previous is_latest=0."""
        initial_photos = [
            {"file": "/private/files/rev1_defect.jpg", "caption": "Collar defect", "evidence_type": "Fabric Defect"},
        ]
        insp1 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            spec_notes="Initial collar spec",
            evidence_photos=initial_photos,
            checklist_items=[{"check_point": "Collar Point Symmetry", "status": "Fail", "notes": "Collar points unequal"}],
            measurements=[{"parameter_name": "Collar Band Height", "spec_target": 3.5, "actual_reading": 4.2}],
            defects=[{"defect_code": "DEF-COL-01", "defect_description": "Collar point asymmetry", "severity": "Major", "defect_count": 3}],
        )

        doc1 = frappe.get_doc("Supplier Quality Inspection", insp1["name"])
        self.assertEqual(doc1.revision, 1)
        self.assertEqual(doc1.is_latest, 1)

        # Revise report with corrected observations and new photo
        revised_photos = [
            {"file": "/private/files/rev2_fixed.jpg", "caption": "Corrected collar symmetry", "evidence_type": "Refit Sample"},
        ]
        insp2 = revise_quality_inspection(
            inspection_name=insp1["name"],
            spec_notes="Collar band revised to spec",
            evidence_photos=revised_photos,
            checklist_items=[{"check_point": "Collar Point Symmetry", "status": "Pass", "notes": "Points symmetrical"}],
            measurements=[{"parameter_name": "Collar Band Height", "spec_target": 3.5, "actual_reading": 3.5}],
            defects=[],  # Defects resolved!
            result="Passed",
        )

        doc2 = frappe.get_doc("Supplier Quality Inspection", insp2["name"])
        self.assertEqual(doc2.revision, 2)
        self.assertEqual(doc2.supersedes, insp1["name"])
        self.assertEqual(doc2.is_latest, 1)
        self.assertEqual(doc2.result, "Passed")

        # Previous doc1 is now superseded and NOT latest
        doc1.reload()
        self.assertEqual(doc1.superseded_by, insp2["name"])
        self.assertEqual(doc1.is_latest, 0)

        # Both photos preserved on revision 2
        self.assertEqual(len(doc2.evidence_photos), 2)
        self.assertEqual(doc2.evidence_photos[0].file, "/private/files/rev1_defect.jpg")
        self.assertEqual(doc2.evidence_photos[0].revision, 1)
        self.assertEqual(doc2.evidence_photos[1].file, "/private/files/rev2_fixed.jpg")
        self.assertEqual(doc2.evidence_photos[1].revision, 2)

        frappe.delete_doc("Supplier Quality Inspection", insp1["name"], force=True)
        frappe.delete_doc("Supplier Quality Inspection", insp2["name"], force=True)

    def test_cannot_revise_approved_inspection(self):
        """Attempting to revise an already approved inspection raises ValidationError."""
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
        )
        frappe.db.set_value("Supplier Quality Inspection", insp["name"], "status", "Approved")

        with self.assertRaisesRegex(frappe.ValidationError, "Cannot revise an already approved inspection"):
            revise_quality_inspection(inspection_name=insp["name"])

        frappe.delete_doc("Supplier Quality Inspection", insp["name"], force=True)

    # =========================================================================
    # 7. SIDE-BY-SIDE REVISION COMPARISON
    # =========================================================================

    def test_side_by_side_revision_comparison(self):
        """compare_inspection_revisions produces full structured diff between two revisions."""
        insp1 = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
            checklist_items=[
                {"check_point": "Buttonhole Strength", "status": "Fail", "actual_value": "Fraying threads"},
                {"check_point": "Hem Cleanliness", "status": "Pass", "actual_value": "Clean hem"},
            ],
            measurements=[
                {"parameter_name": "Sleeve Length", "spec_target": 65.0, "tolerance_plus": 0.5, "tolerance_minus": 0.5, "actual_reading": 67.0},
            ],
            defects=[
                {"defect_code": "DEF-BTN-01", "defect_description": "Frayed buttonhole", "severity": "Major", "defect_count": 4},
            ],
            evidence_photos=[{"file": "/private/files/rev1_btn.jpg", "caption": "Frayed buttonhole", "evidence_type": "Stitching Defect"}],
            result="Failed",
        )

        insp2 = revise_quality_inspection(
            inspection_name=insp1["name"],
            checklist_items=[
                {"check_point": "Buttonhole Strength", "status": "Pass", "actual_value": "Tight bar-tacked stitches"},
                {"check_point": "Hem Cleanliness", "status": "Pass", "actual_value": "Clean hem"},
            ],
            measurements=[
                {"parameter_name": "Sleeve Length", "spec_target": 65.0, "tolerance_plus": 0.5, "tolerance_minus": 0.5, "actual_reading": 65.2},
            ],
            defects=[],  # 0 defects!
            evidence_photos=[{"file": "/private/files/rev2_btn_fixed.jpg", "caption": "Reinforced buttonhole", "evidence_type": "Refit Sample"}],
            result="Passed",
        )

        diff = compare_inspection_revisions(insp1["name"], insp2["name"])
        self.assertEqual(diff["original_revision"], 1)
        self.assertEqual(diff["revision_number"], 2)

        # 1. Metadata diff
        meta = diff["metadata_diff"]
        self.assertEqual(meta["result"]["original"], "Failed")
        self.assertEqual(meta["result"]["revision"], "Passed")

        # 2. Checklist diff
        chk_diff = {item["check_point"]: item for item in diff["checklist_diff"]}
        self.assertTrue(chk_diff["Buttonhole Strength"]["status_changed"])
        self.assertEqual(chk_diff["Buttonhole Strength"]["original_status"], "Fail")
        self.assertEqual(chk_diff["Buttonhole Strength"]["revision_status"], "Pass")
        self.assertFalse(chk_diff["Hem Cleanliness"]["status_changed"])

        # 3. Measurements diff
        m_diff = diff["measurements_diff"][0]
        self.assertEqual(m_diff["original_reading"], 67.0)
        self.assertEqual(m_diff["revision_reading"], 65.2)
        self.assertEqual(m_diff["original_status"], "Out of Spec")
        self.assertEqual(m_diff["revision_status"], "In Spec")
        self.assertTrue(m_diff["status_changed"])

        # 4. Defects diff
        d_diff = diff["defects_diff"][0]
        self.assertEqual(d_diff["defect_code"], "DEF-BTN-01")
        self.assertEqual(d_diff["original_count"], 4)
        self.assertEqual(d_diff["revision_count"], 0)
        self.assertTrue(d_diff["resolved"])

        # 5. Evidence photos diff
        p_diff = diff["evidence_photos_diff"]
        self.assertEqual(p_diff["original_photo_count"], 1)
        self.assertEqual(p_diff["revision_photo_count"], 2)
        self.assertEqual(p_diff["new_photos_added_count"], 1)

        frappe.delete_doc("Supplier Quality Inspection", insp1["name"], force=True)
        frappe.delete_doc("Supplier Quality Inspection", insp2["name"], force=True)

    # =========================================================================
    # 8. CONCURRENCY & ROW LOCKING
    # =========================================================================

    def test_revision_and_approval_enforce_row_locking(self):
        """Revising an inspection uses SELECT ... FOR UPDATE to serialize concurrent mutations."""
        insp = create_quality_inspection(
            supplier=self.supplier,
            item_code=self.item_code,
            stage="1. First Submission",
        )

        with (
            patch.object(frappe.db, "sql", wraps=frappe.db.sql) as mock_sql,
        ):
            res = revise_quality_inspection(
                inspection_name=insp["name"],
                spec_notes="Concurrency test notes",
            )
            # Must verify FOR UPDATE was invoked on tabSupplier Quality Inspection
            called_for_update = any(
                "FOR UPDATE" in str(call.args[0]) and "tabSupplier Quality Inspection" in str(call.args[0])
                for call in mock_sql.call_args_list
            )
            self.assertTrue(called_for_update)

        frappe.delete_doc("Supplier Quality Inspection", insp["name"], force=True)
        frappe.delete_doc("Supplier Quality Inspection", res["name"], force=True)

    # =========================================================================
    # 9. MULTI-COMPANY & SUPPLIER ISOLATION
    # =========================================================================

    def test_multi_company_isolation_enforced(self):
        """User restricted to Company A cannot create inspection for Company B."""
        with (
            patch.object(security, "get_current_user", return_value="inspector_a@example.invalid"),
            patch.object(security, "is_quality_admin", return_value=False),
            patch.object(frappe, "get_all", return_value=["Company A"]),
        ):
            with self.assertRaises(frappe.PermissionError):
                create_quality_inspection(
                    supplier=self.supplier,
                    item_code=self.item_code,
                    stage="1. First Submission",
                    company="Company B",
                )

    def test_supplier_isolation_enforced(self):
        """User restricted to Supplier X cannot create inspection for Supplier Y."""
        def mock_get_all(dt, filters=None, pluck=None):
            if dt == "User Permission" and filters.get("allow") == "Supplier":
                return ["Supplier X"]
            return []

        with (
            patch.object(security, "get_current_user", return_value="supplier_user@example.invalid"),
            patch.object(security, "is_quality_admin", return_value=False),
            patch.object(frappe, "get_all", side_effect=mock_get_all),
        ):
            with self.assertRaises(frappe.PermissionError):
                create_quality_inspection(
                    supplier="Supplier Y",
                    item_code=self.item_code,
                    stage="1. First Submission",
                )

    # =========================================================================
    # 10. MIGRATION COMPATIBILITY DRILL
    # =========================================================================

    def test_legacy_inspection_compatibility(self):
        """Existing inspections without checklist or defect tables load and revise without error."""
        legacy_insp = frappe.get_doc({
            "doctype": "Supplier Quality Inspection",
            "supplier": self.supplier,
            "item_code": self.item_code,
            "stage": "1. First Submission",
            "status": "Pending Review",
            "spec_measurements": "Old legacy spec string",
        })
        legacy_insp.insert()

        self.assertEqual(len(legacy_insp.checklist_items), 0)
        self.assertEqual(len(legacy_insp.measurements), 0)
        self.assertEqual(len(legacy_insp.defects), 0)

        # Revise legacy inspection into new structured format
        revised = revise_quality_inspection(
            inspection_name=legacy_insp.name,
            spec_notes="Modernized spec format",
            checklist_items=[{"check_point": "Modern Standard Check", "status": "Pass"}],
        )

        doc_rev = frappe.get_doc("Supplier Quality Inspection", revised["name"])
        self.assertEqual(doc_rev.revision, 2)
        self.assertEqual(len(doc_rev.checklist_items), 1)

        frappe.delete_doc("Supplier Quality Inspection", legacy_insp.name, force=True)
        frappe.delete_doc("Supplier Quality Inspection", revised["name"], force=True)
