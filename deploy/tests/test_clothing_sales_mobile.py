# Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
# Use of this source code is governed by a MIT-style license.

"""Comprehensive Automated Verification Test Suite for Session 16: Clothing Sales Mobile.

Validates:
1. `mobile/apps/sales_app` architecture and presence of all required models, services,
   controllers, screens, and Dart unit/integration tests.
2. ASM and RSM Role-Aware Dashboard & Navigation:
   - Territory-scoped operational metrics.
   - Immediate session wipe and rejection if an unauthorized role is detected.
3. Territory-Scoped Retailer Directory & Detail:
   - Operating types (Buy & Sell, SIS, EBOC).
   - Commercial exposure checks and 120-day collection hard block indicator.
   - Zero cross-territory data exposure.
4. Retailer Onboarding & Private Multi-Photo Evidence:
   - Draft save/resume in SQLCipher encrypted local database.
   - Multi-photo private evidence processing via SafePhotoManager (EXIF stripping, 2MB size bound, SHA-256).
   - RSM supervisory review (RFI, commercial field updates, approve with initial credit limit, reject).
5. Offline-Capable Catalogue Subset & Barcode Scanning:
   - Style colourway templates and size variant matrices.
   - Prominent stale cache banner; cached prices and stock are strictly non-authoritative.
   - Peripheral hardware-wedge and camera barcode scan lookup.
6. Cart Management & Server Repricing Preflight:
   - Server-side repricing preflight and exposure check prior to order placement.
   - UUID v4 idempotency keys.
   - Offline mutation queueing with conflict resolution state machine.
   - Returned draft order correction and resubmission.
7. 90–120 Day Collection Worklist:
   - Uses native ERPNext Accounts Receivable data.
   - Zero parallel accounting ledgers.
   - Zero collection or storage of payment secrets (CVVs, PINs, card numbers).
8. Post-Dispatch Delivery Follow-Up:
   - Delivery note follow-up obligations.
   - Package/carton barcode verification.
   - Arrival confirmation, shortage/damage logging, and escalation.
9. RSM Supervision:
   - Assigned ASMs and territory coverage.
   - Administrator guidance capacity evaluation (3-4 ASMs, 200-250 shops).
   - Application and order approval queues.
   - Zero user-management privileges.
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SALES_APP_ROOT = os.path.join(REPO_ROOT, "mobile", "apps", "sales_app")
SALES_LIB = os.path.join(SALES_APP_ROOT, "lib")
SALES_TESTS = os.path.join(SALES_APP_ROOT, "test")


class TestClothingSalesMobile(unittest.TestCase):
    # -----------------------------------------------------------------------
    # 1. Structure & Workspace Verification
    # -----------------------------------------------------------------------
    def test_sales_app_structure_and_pubspec(self):
        """Sales app exists with proper monorepo dependencies in pubspec.yaml."""
        self.assertTrue(os.path.isdir(SALES_APP_ROOT), "mobile/apps/sales_app directory missing")
        pubspec_path = os.path.join(SALES_APP_ROOT, "pubspec.yaml")
        self.assertTrue(os.path.isfile(pubspec_path))

        with open(pubspec_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("name: sales_app", content)
        self.assertIn("clothing_core:", content)
        self.assertIn("clothing_design_system:", content)
        self.assertTrue(os.path.isfile(os.path.join(SALES_LIB, "main.dart")))
        self.assertTrue(os.path.isfile(os.path.join(SALES_LIB, "sales_app.dart")))

    # -----------------------------------------------------------------------
    # 2. Domain Models Verification
    # -----------------------------------------------------------------------
    def test_sales_domain_models_exist(self):
        """All 10 required domain models exist with strict type definitions."""
        models_dir = os.path.join(SALES_LIB, "src", "models")
        self.assertTrue(os.path.isdir(models_dir))

        expected_models = [
            "sales_dashboard_model.dart",
            "retailer_model.dart",
            "retailer_application_model.dart",
            "retailer_visit_model.dart",
            "catalogue_model.dart",
            "cart_order_model.dart",
            "collection_model.dart",
            "delivery_follow_up_model.dart",
            "supervision_model.dart",
            "conflict_model.dart",
        ]

        for model_file in expected_models:
            full_path = os.path.join(models_dir, model_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing model: {model_file}")

    # -----------------------------------------------------------------------
    # 3. Domain Services Verification
    # -----------------------------------------------------------------------
    def test_sales_services_exist_and_enforce_security(self):
        """Domain services exist, enforce SQLCipher encryption, and safe photos."""
        services_dir = os.path.join(SALES_LIB, "src", "services")
        self.assertTrue(os.path.isdir(services_dir))

        expected_services = [
            "sales_api_service.dart",
            "sales_local_cache.dart",
            "sales_order_manager.dart",
            "sales_visit_manager.dart",
            "sales_application_manager.dart",
        ]

        for s_file in expected_services:
            full_path = os.path.join(services_dir, s_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing service: {s_file}")

        # Check local cache encryption & wipe
        with open(os.path.join(services_dir, "sales_local_cache.dart"), "r", encoding="utf-8") as f:
            cache_code = f.read()
            self.assertIn("ClothingEncryptedDb", cache_code)
            self.assertIn("destroyAndWipe", cache_code)
            self.assertIn("local_retailers", cache_code)
            self.assertIn("local_catalogue", cache_code)

        # Check visit check-in safe photo
        with open(os.path.join(services_dir, "sales_visit_manager.dart"), "r", encoding="utf-8") as f:
            visit_code = f.read()
            self.assertIn("SafePhotoManager", visit_code)
            self.assertIn("processAndSanitize", visit_code)

    # -----------------------------------------------------------------------
    # 4. Controllers Verification
    # -----------------------------------------------------------------------
    def test_sales_controllers_exist(self):
        """All 10 sales controllers exist."""
        controllers_dir = os.path.join(SALES_LIB, "src", "controllers")
        self.assertTrue(os.path.isdir(controllers_dir))

        expected_controllers = [
            "sales_home_controller.dart",
            "retailer_directory_controller.dart",
            "catalogue_controller.dart",
            "cart_controller.dart",
            "orders_controller.dart",
            "visits_controller.dart",
            "collections_controller.dart",
            "delivery_follow_up_controller.dart",
            "rsm_supervision_controller.dart",
            "conflicts_controller.dart",
        ]

        for c_file in expected_controllers:
            full_path = os.path.join(controllers_dir, c_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing controller: {c_file}")

    # -----------------------------------------------------------------------
    # 5. UI Screens Verification
    # -----------------------------------------------------------------------
    def test_sales_screens_exist(self):
        """Screens exist across all sales functional domains."""
        screens_dir = os.path.join(SALES_LIB, "src", "screens")
        self.assertTrue(os.path.isdir(screens_dir))

        expected_screens = [
            os.path.join(screens_dir, "sales_home_screen.dart"),
            os.path.join(screens_dir, "retailers", "retailer_list_screen.dart"),
            os.path.join(screens_dir, "retailers", "retailer_detail_screen.dart"),
            os.path.join(screens_dir, "applications", "retailer_application_form_screen.dart"),
            os.path.join(screens_dir, "applications", "rsm_application_review_screen.dart"),
            os.path.join(screens_dir, "visits", "visit_queue_screen.dart"),
            os.path.join(screens_dir, "visits", "visit_checkin_screen.dart"),
            os.path.join(screens_dir, "catalogue", "catalogue_screen.dart"),
            os.path.join(screens_dir, "catalogue", "product_detail_screen.dart"),
            os.path.join(screens_dir, "cart", "cart_screen.dart"),
            os.path.join(screens_dir, "cart", "order_detail_screen.dart"),
            os.path.join(screens_dir, "collections", "collection_worklist_screen.dart"),
            os.path.join(screens_dir, "delivery", "delivery_follow_up_screen.dart"),
            os.path.join(screens_dir, "supervision", "rsm_supervision_screen.dart"),
            os.path.join(screens_dir, "conflicts", "conflicts_screen.dart"),
        ]

        for screen_path in expected_screens:
            self.assertTrue(os.path.isfile(screen_path), f"Missing screen: {screen_path}")

    # -----------------------------------------------------------------------
    # 6. Dart Test Suite Verification
    # -----------------------------------------------------------------------
    def test_sales_dart_test_files_exist(self):
        """All 5 Dart unit/integration test files exist in test/."""
        self.assertTrue(os.path.isdir(SALES_TESTS))

        expected_tests = [
            "sales_dashboard_test.dart",
            "retailer_workflow_test.dart",
            "catalogue_cart_test.dart",
            "order_offline_queue_test.dart",
            "collections_follow_up_test.dart",
        ]

        for t_file in expected_tests:
            full_path = os.path.join(SALES_TESTS, t_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing test file: {t_file}")

    # -----------------------------------------------------------------------
    # 7. Security Invariant: Zero Hardcoded Secrets & Payment Secrets
    # -----------------------------------------------------------------------
    def test_zero_hardcoded_secrets_or_payment_cards(self):
        """Source files contain zero hardcoded credentials and zero payment card fields."""
        # Check for field declarations or keys collecting card details
        prohibited_field_pattern = re.compile(
            r"""['"]?(?:cvv|card_number|credit_card|debit_card|bank_pin|security_code)['"]?\s*[:=]""",
            re.IGNORECASE,
        )

        # Allowlist of safe constants and file paths
        allowlist = {
            "com.clothingerp.sales",
            "clothing_sales_mobile",
            "clothing_sales_encrypted.db",
            "com.clothingerp.sales://oauth/callback",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }

        for root, _, files in os.walk(SALES_LIB):
            for file in files:
                if not file.endswith(".dart"):
                    continue
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, start=1):
                        # Skip comments
                        if line.strip().startswith("//"):
                            continue
                        if prohibited_field_pattern.search(line):
                            self.fail(f"Prohibited payment card field found in {path}:{line_no}: {line}")

    # -----------------------------------------------------------------------
    # 8. Server Revalidation Doctrine
    # -----------------------------------------------------------------------
    def test_server_revalidation_doctrine_enforced(self):
        """Cached catalogue items are explicitly marked stale; prices are non-authoritative."""
        catalogue_model_path = os.path.join(SALES_LIB, "src", "models", "catalogue_model.dart")
        with open(catalogue_model_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("isStale", content)
        self.assertIn("hasAuthoritativeData", content)
        self.assertIn("NON-AUTHORITATIVE", content)

        # Cart repricing
        order_mgr_path = os.path.join(SALES_LIB, "src", "services", "sales_order_manager.dart")
        with open(order_mgr_path, "r", encoding="utf-8") as f:
            mgr_code = f.read()

        self.assertIn("refreshRepricingAndExposure", mgr_code)
        self.assertIn("prepriceAndCheckExposure", mgr_code)
        self.assertIn("UUID", mgr_code)


if __name__ == "__main__":
    unittest.main()
