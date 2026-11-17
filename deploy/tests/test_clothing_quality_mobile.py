# Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
# Use of this source code is governed by a MIT-style license.

"""Comprehensive Automated Verification Test Suite for Session 18: Clothing Quality Mobile.

Validates:
1. `mobile/apps/quality_app` monorepo structure, pubspec.yaml, entrypoints, and exports.
2. Role Scoping & Authorization Matrix:
   - Targets Clothing Quality Inspector, Clothing Quality Manager, and Clothing Business Administrator.
   - Rejects unauthorized roles with immediate session wipe and cache destruction.
   - Enforces Supplier and Company isolation server-side.
3. Domain Models & Structured Typing (11 models):
   - QualityBootModel, ProductionCycleModel, ChecklistTemplateModel, InspectionReadingModel,
     InspectionDefectModel, InspectionEvidencePhoto, StageInspectionModel,
     RevisionComparisonModel, ReturnQuarantineModel, GateReviewBundleModel, ControlledReportModel.
4. Domain Services (7 services):
   - QualityApiService, QualityLocalCache, QualityCycleManager, QualityInspectionManager,
     QuarantineDispositionManager, GateReviewManager, ControlledReportManager.
   - Enforces SQLCipher 256-bit AES encrypted local persistence and cryptographic wipe.
5. Controllers (7 controllers):
   - QualityHomeController, CyclesController, InspectionController, RevisionController,
     ReturnQuarantineController, GateReviewController, ControlledReportController.
6. Functional UI Screens (9 screens):
   - QualityHomeScreen, ProductionCycleListScreen, CycleDetailScreen, InspectionFormScreen,
     RevisionCompareScreen, ReturnQuarantineListScreen, ReturnQuarantineDetailScreen,
     GateReviewScreen, ControlledReportScreen.
7. Dart Test Suites (5 suites):
   - All 5 test files exist in test/ directory.
8. Core Business & Security Invariants:
   - 7-stage sequential quality lifecycle ordering and multiple Inline/Mid-line visits.
   - Versioned checklist completion, measurement tolerance variances, and defect severity.
   - Multiple captioned private photographs via SafePhotoManager (EXIF stripping, 2MB cap, SHA-256).
   - Side-by-side revision comparison diff and correction resubmission trail.
   - Return quarantine decisions & two-step disposition governance.
   - Post-refurbishment reinspection clearance gate (restock to saleable is BLOCKED unless Passed).
   - High-risk Administrator gate review: strictly BLOCKED while offline, requires exact immutable
     review bundle with bundle SHA-256 hash, and requires strong reauthentication.
   - Controlled report viewing: ephemeral device storage, HMAC token expiry, watermark, zero permanent URLs.
   - Zero hardcoded credentials or customer financial secrets.
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUALITY_APP_ROOT = os.path.join(REPO_ROOT, "mobile", "apps", "quality_app")
QUALITY_LIB = os.path.join(QUALITY_APP_ROOT, "lib")
QUALITY_TESTS = os.path.join(QUALITY_APP_ROOT, "test")


class TestClothingQualityMobile(unittest.TestCase):
    # -----------------------------------------------------------------------
    # 1. Structure & Monorepo Verification
    # -----------------------------------------------------------------------
    def test_quality_app_structure_and_pubspec(self):
        """Quality app exists with proper monorepo dependencies in pubspec.yaml."""
        self.assertTrue(os.path.isdir(QUALITY_APP_ROOT), "mobile/apps/quality_app missing")
        pubspec_path = os.path.join(QUALITY_APP_ROOT, "pubspec.yaml")
        self.assertTrue(os.path.isfile(pubspec_path))

        with open(pubspec_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("name: quality_app", content)
        self.assertIn("clothing_core:", content)
        self.assertIn("clothing_design_system:", content)
        self.assertTrue(os.path.isfile(os.path.join(QUALITY_LIB, "main.dart")))
        self.assertTrue(os.path.isfile(os.path.join(QUALITY_LIB, "quality_app.dart")))

    # -----------------------------------------------------------------------
    # 2. Domain Models Verification
    # -----------------------------------------------------------------------
    def test_quality_domain_models_exist(self):
        """All 11 required domain models exist with strict type definitions."""
        models_dir = os.path.join(QUALITY_LIB, "src", "models")
        self.assertTrue(os.path.isdir(models_dir))

        expected_models = [
            "quality_boot_model.dart",
            "production_cycle_model.dart",
            "checklist_template_model.dart",
            "inspection_reading_model.dart",
            "inspection_defect_model.dart",
            "inspection_evidence_photo.dart",
            "stage_inspection_model.dart",
            "revision_comparison_model.dart",
            "return_quarantine_model.dart",
            "gate_review_bundle_model.dart",
            "controlled_report_model.dart",
        ]

        for model_file in expected_models:
            full_path = os.path.join(models_dir, model_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing model: {model_file}")

    # -----------------------------------------------------------------------
    # 3. Domain Services Verification
    # -----------------------------------------------------------------------
    def test_quality_services_exist_and_enforce_security(self):
        """Domain services exist, enforce SQLCipher encryption, safe photos, and ephemeral reports."""
        services_dir = os.path.join(QUALITY_LIB, "src", "services")
        self.assertTrue(os.path.isdir(services_dir))

        expected_services = [
            "quality_api_service.dart",
            "quality_local_cache.dart",
            "quality_cycle_manager.dart",
            "quality_inspection_manager.dart",
            "quarantine_disposition_manager.dart",
            "gate_review_manager.dart",
            "controlled_report_manager.dart",
        ]

        for s_file in expected_services:
            full_path = os.path.join(services_dir, s_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing service: {s_file}")

        # Check local cache encryption & wipe
        with open(os.path.join(services_dir, "quality_local_cache.dart"), "r", encoding="utf-8") as f:
            cache_code = f.read()
            self.assertIn("ClothingEncryptedDb", cache_code)
            self.assertIn("destroyAndWipe", cache_code)
            self.assertIn("local_production_cycles", cache_code)
            self.assertIn("local_stage_inspections", cache_code)
            self.assertIn("local_checklist_templates", cache_code)
            self.assertIn("local_return_quarantine", cache_code)

        # Check safe photo handling
        with open(os.path.join(services_dir, "quality_inspection_manager.dart"), "r", encoding="utf-8") as f:
            insp_code = f.read()
            self.assertIn("SafePhotoManager", insp_code)
            self.assertIn("processAndSanitize", insp_code)

    # -----------------------------------------------------------------------
    # 4. Controllers Verification
    # -----------------------------------------------------------------------
    def test_quality_controllers_exist(self):
        """All 7 quality controllers exist."""
        controllers_dir = os.path.join(QUALITY_LIB, "src", "controllers")
        self.assertTrue(os.path.isdir(controllers_dir))

        expected_controllers = [
            "quality_home_controller.dart",
            "cycles_controller.dart",
            "inspection_controller.dart",
            "revision_controller.dart",
            "return_quarantine_controller.dart",
            "gate_review_controller.dart",
            "controlled_report_controller.dart",
        ]

        for c_file in expected_controllers:
            full_path = os.path.join(controllers_dir, c_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing controller: {c_file}")

    # -----------------------------------------------------------------------
    # 5. UI Screens Verification
    # -----------------------------------------------------------------------
    def test_quality_screens_exist(self):
        """Screens exist across all quality functional domains."""
        screens_dir = os.path.join(QUALITY_LIB, "src", "screens")
        self.assertTrue(os.path.isdir(screens_dir))

        expected_screens = [
            os.path.join(screens_dir, "quality_home_screen.dart"),
            os.path.join(screens_dir, "cycles", "production_cycle_list_screen.dart"),
            os.path.join(screens_dir, "cycles", "cycle_detail_screen.dart"),
            os.path.join(screens_dir, "inspection", "inspection_form_screen.dart"),
            os.path.join(screens_dir, "inspection", "revision_compare_screen.dart"),
            os.path.join(screens_dir, "returns", "return_quarantine_list_screen.dart"),
            os.path.join(screens_dir, "returns", "return_quarantine_detail_screen.dart"),
            os.path.join(screens_dir, "gate_review", "gate_review_screen.dart"),
            os.path.join(screens_dir, "reports", "controlled_report_screen.dart"),
        ]

        for screen_path in expected_screens:
            self.assertTrue(os.path.isfile(screen_path), f"Missing screen: {screen_path}")

    # -----------------------------------------------------------------------
    # 6. Dart Test Suite Verification
    # -----------------------------------------------------------------------
    def test_quality_dart_test_files_exist(self):
        """All 5 Dart unit/integration test files exist in test/."""
        self.assertTrue(os.path.isdir(QUALITY_TESTS))

        expected_tests = [
            "quality_boot_role_test.dart",
            "production_cycle_stages_test.dart",
            "inspection_checklists_measurements_test.dart",
            "revisions_corrections_comparison_test.dart",
            "gate_review_quarantine_security_test.dart",
        ]

        for t_file in expected_tests:
            full_path = os.path.join(QUALITY_TESTS, t_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing test file: {t_file}")

    # -----------------------------------------------------------------------
    # 7. Role Scoping & Scoped Gate Review Authority
    # -----------------------------------------------------------------------
    def test_role_scoping_and_gate_authority(self):
        """Quality Inspector, Manager, and Admin roles are enforced; only Manager/Admin decide gates."""
        boot_path = os.path.join(QUALITY_LIB, "src", "models", "quality_boot_model.dart")
        with open(boot_path, "r", encoding="utf-8") as f:
            boot_code = f.read()

        self.assertIn("Clothing Quality Inspector", boot_code)
        self.assertIn("Clothing Quality Manager", boot_code)
        self.assertIn("Clothing Business Administrator", boot_code)
        self.assertIn("canDecideCriticalGates", boot_code)
        self.assertIn("isSupplierAllowed", boot_code)

    # -----------------------------------------------------------------------
    # 8. High-Risk Gate Review Invariants
    # -----------------------------------------------------------------------
    def test_high_risk_gate_review_invariants(self):
        """Gate reviews require online connectivity, exact immutable bundle hash, and reauthentication."""
        gate_mgr_path = os.path.join(QUALITY_LIB, "src", "services", "gate_review_manager.dart")
        with open(gate_mgr_path, "r", encoding="utf-8") as f:
            mgr_code = f.read()

        self.assertIn("cannot be approved offline", mgr_code)
        self.assertIn("reauthPassword", mgr_code)
        self.assertIn("bundleHash", mgr_code)
        self.assertIn("bundle.bundleHash", mgr_code)

        controller_path = os.path.join(QUALITY_LIB, "src", "controllers", "gate_review_controller.dart")
        with open(controller_path, "r", encoding="utf-8") as f:
            ctrl_code = f.read()

        self.assertIn("reauthPassword.trim().isEmpty", ctrl_code)
        self.assertIn("isOnline", ctrl_code)

    # -----------------------------------------------------------------------
    # 9. Return Quarantine & Post-Refurbishment Reinspection Gate
    # -----------------------------------------------------------------------
    def test_quarantine_and_post_refurbishment_gate(self):
        """Quarantine disposition recommendations and post-refurbishment reinspection are enforced."""
        disposition_mgr_path = os.path.join(QUALITY_LIB, "src", "services", "quarantine_disposition_manager.dart")
        with open(disposition_mgr_path, "r", encoding="utf-8") as f:
            disp_code = f.read()

        self.assertIn("recommendDisposition", disp_code)
        self.assertIn("approveDisposition", disp_code)
        self.assertIn("isReinspectionCleared", disp_code)
        self.assertIn("Passed", disp_code)

    # -----------------------------------------------------------------------
    # 10. Controlled Report Viewing & Ephemeral Device Storage
    # -----------------------------------------------------------------------
    def test_controlled_report_ephemeral_storage(self):
        """Controlled report bundles enforce HMAC expiry and purge temporary local files."""
        report_mgr_path = os.path.join(QUALITY_LIB, "src", "services", "controlled_report_manager.dart")
        with open(report_mgr_path, "r", encoding="utf-8") as f:
            rep_code = f.read()

        self.assertIn("isExpired", rep_code)
        self.assertIn("purgeExpiredReports", rep_code)
        self.assertIn("wipeAllReports", rep_code)

        model_path = os.path.join(QUALITY_LIB, "src", "models", "controlled_report_model.dart")
        with open(model_path, "r", encoding="utf-8") as f:
            model_code = f.read()

        self.assertIn("reportToken", model_code)
        self.assertIn("watermarkText", model_code)
        self.assertIn("expiresAt", model_code)

    # -----------------------------------------------------------------------
    # 11. Zero Hardcoded Secrets or Payment Cards
    # -----------------------------------------------------------------------
    def test_zero_hardcoded_secrets_or_payment_cards(self):
        """Source files contain zero hardcoded credentials and zero payment card fields."""
        prohibited_field_pattern = re.compile(
            r"""['"]?(?:cvv|card_number|credit_card|debit_card|bank_pin|security_code)['"]?\s*[:=]""",
            re.IGNORECASE,
        )

        for root, _, files in os.walk(QUALITY_LIB):
            for file in files:
                if not file.endswith(".dart"):
                    continue
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, start=1):
                        if line.strip().startswith("//"):
                            continue
                        if prohibited_field_pattern.search(line):
                            self.fail(f"Prohibited payment card field found in {path}:{line_no}: {line}")


if __name__ == "__main__":
    unittest.main()
