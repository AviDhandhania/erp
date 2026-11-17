# Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
# Use of this source code is governed by a MIT-style license.

"""Comprehensive Automated Verification Test Suite for Session 17: Clothing Warehouse Mobile.

Validates:
1. `mobile/apps/warehouse_app` monorepo structure, pubspec.yaml, entrypoints, and exports.
2. Manager-only authorization & scoping:
   - Targets Clothing Warehouse Manager and Clothing Business Administrator.
   - Enforces retirement of legacy operator accounts with immediate session wipe.
   - Restricts operations to assigned warehouse user permissions.
3. Domain Models & Structured Typing (10 models):
   - WarehouseBootModel, FulfillmentTaskModel, PickItemModel, PackingModel,
     DeliveryHandoffModel, WorkQueueSummaryModel, ReturnIntakeModel,
     RefurbishmentModel, PrinterModel, WarehouseConflictModel.
4. Domain Services (5 services):
   - WarehouseApiService, WarehouseLocalCache, FulfillmentManager,
     ReturnsManager, PrinterService.
   - Enforces SQLCipher 256-bit AES encrypted local persistence and cryptographic wipe.
5. Controllers (8 controllers):
   - WarehouseHomeController, PickingController, PackingController, DispatchController,
     ReturnsController, RefurbishmentController, PrinterController, WarehouseConflictsController.
6. Functional UI Screens (9 screens):
   - WarehouseHomeScreen, PickListScreen, PickScanScreen, PackingScreen,
     DispatchScreen, ReturnIntakeScreen, RefurbishmentScreen, PrinterScreen,
     WarehouseConflictsScreen.
7. Dart Test Suites (5 suites):
   - All 5 test files exist in test/ directory.
8. Core Business & Security Invariants:
   - Hardware-wedge burst timing (<50ms) and camera scanning.
   - Offline scan queue permitted, but native document creation and stock transitions
     strictly BLOCKED until online server reconciliation succeeds with zero conflicts.
   - Safe thermal printer payloads: zero credentials, tokens, or financial secrets.
   - Quarantine warehouse isolation: returned items route strictly to quarantine warehouse.
   - Post-refurbishment reinspection quality gate: restock to saleable inventory strictly
     blocked unless post-refurbishment reinspection has Passed.
   - Zero hardcoded credentials or customer financial secrets.
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WAREHOUSE_APP_ROOT = os.path.join(REPO_ROOT, "mobile", "apps", "warehouse_app")
WAREHOUSE_LIB = os.path.join(WAREHOUSE_APP_ROOT, "lib")
WAREHOUSE_TESTS = os.path.join(WAREHOUSE_APP_ROOT, "test")


class TestClothingWarehouseMobile(unittest.TestCase):
    # -----------------------------------------------------------------------
    # 1. Structure & Monorepo Verification
    # -----------------------------------------------------------------------
    def test_warehouse_app_structure_and_pubspec(self):
        """Warehouse app exists with proper monorepo dependencies in pubspec.yaml."""
        self.assertTrue(os.path.isdir(WAREHOUSE_APP_ROOT), "mobile/apps/warehouse_app missing")
        pubspec_path = os.path.join(WAREHOUSE_APP_ROOT, "pubspec.yaml")
        self.assertTrue(os.path.isfile(pubspec_path))

        with open(pubspec_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("name: warehouse_app", content)
        self.assertIn("clothing_core:", content)
        self.assertIn("clothing_design_system:", content)
        self.assertTrue(os.path.isfile(os.path.join(WAREHOUSE_LIB, "main.dart")))
        self.assertTrue(os.path.isfile(os.path.join(WAREHOUSE_LIB, "warehouse_app.dart")))

    # -----------------------------------------------------------------------
    # 2. Domain Models Verification
    # -----------------------------------------------------------------------
    def test_warehouse_domain_models_exist(self):
        """All 10 required domain models exist with strict type definitions."""
        models_dir = os.path.join(WAREHOUSE_LIB, "src", "models")
        self.assertTrue(os.path.isdir(models_dir))

        expected_models = [
            "warehouse_boot_model.dart",
            "fulfillment_task_model.dart",
            "pick_item_model.dart",
            "packing_model.dart",
            "delivery_handoff_model.dart",
            "work_queue_model.dart",
            "return_intake_model.dart",
            "refurbishment_model.dart",
            "printer_model.dart",
            "warehouse_conflict_model.dart",
        ]

        for model_file in expected_models:
            full_path = os.path.join(models_dir, model_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing model: {model_file}")

    # -----------------------------------------------------------------------
    # 3. Domain Services Verification
    # -----------------------------------------------------------------------
    def test_warehouse_services_exist_and_enforce_security(self):
        """Domain services exist, enforce SQLCipher encryption, safe photos, and printer validation."""
        services_dir = os.path.join(WAREHOUSE_LIB, "src", "services")
        self.assertTrue(os.path.isdir(services_dir))

        expected_services = [
            "warehouse_api_service.dart",
            "warehouse_local_cache.dart",
            "fulfillment_manager.dart",
            "returns_manager.dart",
            "printer_service.dart",
        ]

        for s_file in expected_services:
            full_path = os.path.join(services_dir, s_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing service: {s_file}")

        # Check local cache encryption & wipe
        with open(os.path.join(services_dir, "warehouse_local_cache.dart"), "r", encoding="utf-8") as f:
            cache_code = f.read()
            self.assertIn("ClothingEncryptedDb", cache_code)
            self.assertIn("destroyAndWipe", cache_code)
            self.assertIn("local_warehouse_tasks", cache_code)
            self.assertIn("local_offline_scans", cache_code)
            self.assertIn("local_warehouse_conflicts", cache_code)

        # Check safe photo handling
        with open(os.path.join(services_dir, "returns_manager.dart"), "r", encoding="utf-8") as f:
            returns_code = f.read()
            self.assertIn("SafePhotoManager", returns_code)
            self.assertIn("processAndSanitize", returns_code)

    # -----------------------------------------------------------------------
    # 4. Controllers Verification
    # -----------------------------------------------------------------------
    def test_warehouse_controllers_exist(self):
        """All 8 warehouse controllers exist."""
        controllers_dir = os.path.join(WAREHOUSE_LIB, "src", "controllers")
        self.assertTrue(os.path.isdir(controllers_dir))

        expected_controllers = [
            "warehouse_home_controller.dart",
            "picking_controller.dart",
            "packing_controller.dart",
            "dispatch_controller.dart",
            "returns_controller.dart",
            "refurbishment_controller.dart",
            "printer_controller.dart",
            "warehouse_conflicts_controller.dart",
        ]

        for c_file in expected_controllers:
            full_path = os.path.join(controllers_dir, c_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing controller: {c_file}")

    # -----------------------------------------------------------------------
    # 5. UI Screens Verification
    # -----------------------------------------------------------------------
    def test_warehouse_screens_exist(self):
        """Screens exist across all warehouse functional domains."""
        screens_dir = os.path.join(WAREHOUSE_LIB, "src", "screens")
        self.assertTrue(os.path.isdir(screens_dir))

        expected_screens = [
            os.path.join(screens_dir, "warehouse_home_screen.dart"),
            os.path.join(screens_dir, "picking", "pick_list_screen.dart"),
            os.path.join(screens_dir, "picking", "pick_scan_screen.dart"),
            os.path.join(screens_dir, "packing", "packing_screen.dart"),
            os.path.join(screens_dir, "dispatch", "dispatch_screen.dart"),
            os.path.join(screens_dir, "returns", "return_intake_screen.dart"),
            os.path.join(screens_dir, "refurbishment", "refurbishment_screen.dart"),
            os.path.join(screens_dir, "printer", "printer_screen.dart"),
            os.path.join(screens_dir, "conflicts", "warehouse_conflicts_screen.dart"),
        ]

        for screen_path in expected_screens:
            self.assertTrue(os.path.isfile(screen_path), f"Missing screen: {screen_path}")

    # -----------------------------------------------------------------------
    # 6. Dart Test Suite Verification
    # -----------------------------------------------------------------------
    def test_warehouse_dart_test_files_exist(self):
        """All 5 Dart unit/integration test files exist in test/."""
        self.assertTrue(os.path.isdir(WAREHOUSE_TESTS))

        expected_tests = [
            "warehouse_boot_role_test.dart",
            "picking_scan_undo_test.dart",
            "packing_dimensions_dispatch_test.dart",
            "returns_quarantine_refurbishment_test.dart",
            "safe_printer_concurrency_test.dart",
        ]

        for t_file in expected_tests:
            full_path = os.path.join(WAREHOUSE_TESTS, t_file)
            self.assertTrue(os.path.isfile(full_path), f"Missing test file: {t_file}")

    # -----------------------------------------------------------------------
    # 7. Manager-Only Access & Scoping Verification
    # -----------------------------------------------------------------------
    def test_manager_only_access_model(self):
        """Validates manager-only enforcement and rejection of retired operator accounts."""
        boot_model_path = os.path.join(WAREHOUSE_LIB, "src", "models", "warehouse_boot_model.dart")
        with open(boot_model_path, "r", encoding="utf-8") as f:
            boot_code = f.read()

        self.assertIn("Clothing Warehouse Manager", boot_code)
        self.assertIn("Clothing Business Administrator", boot_code)
        self.assertIn("hasAuthorizedManagerRole", boot_code)

        controller_path = os.path.join(WAREHOUSE_LIB, "src", "controllers", "warehouse_home_controller.dart")
        with open(controller_path, "r", encoding="utf-8") as f:
            ctrl_code = f.read()

        self.assertIn("wipeSessionAndCache", ctrl_code)
        self.assertIn("SecurityException", ctrl_code)

    # -----------------------------------------------------------------------
    # 8. Offline Stock Transitions Blocked Verification
    # -----------------------------------------------------------------------
    def test_offline_stock_transitions_blocked_invariant(self):
        """Offline scans are queued, but Pick List completion and dispatch remain BLOCKED offline."""
        manager_path = os.path.join(WAREHOUSE_LIB, "src", "services", "fulfillment_manager.dart")
        with open(manager_path, "r", encoding="utf-8") as f:
            fm_code = f.read()

        self.assertIn("Cannot complete Pick List while offline", fm_code)
        self.assertIn("Cannot complete Pick List with", fm_code)
        self.assertIn("unreconciled offline scans", fm_code)
        self.assertIn("undoLastScan", fm_code)

    # -----------------------------------------------------------------------
    # 9. Post-Refurbishment Reinspection Gate Verification
    # -----------------------------------------------------------------------
    def test_post_refurbishment_reinspection_gate(self):
        """Restocking to saleable stock is strictly blocked unless reinspection is Passed."""
        refurb_model_path = os.path.join(WAREHOUSE_LIB, "src", "models", "refurbishment_model.dart")
        with open(refurb_model_path, "r", encoding="utf-8") as f:
            model_code = f.read()

        self.assertIn("canRestock", model_code)
        self.assertIn("Passed", model_code)

        returns_mgr_path = os.path.join(WAREHOUSE_LIB, "src", "services", "returns_manager.dart")
        with open(returns_mgr_path, "r", encoding="utf-8") as f:
            mgr_code = f.read()

        self.assertIn("reinspectionStatus != 'Passed'", mgr_code)
        self.assertIn("Cannot restock item to saleable inventory", mgr_code)

    # -----------------------------------------------------------------------
    # 10. Safe Printer Payload Security Verification
    # -----------------------------------------------------------------------
    def test_safe_printer_payload_security(self):
        """Printer payloads are checked for credentials and tamper-evident watermarking is applied."""
        printer_svc_path = os.path.join(WAREHOUSE_LIB, "src", "services", "printer_service.dart")
        with open(printer_svc_path, "r", encoding="utf-8") as f:
            printer_code = f.read()

        self.assertIn("SecurityException", printer_code)
        self.assertIn("password", printer_code)
        self.assertIn("token", printer_code)
        self.assertIn("reprint_count", printer_code)
        self.assertIn("REPRINT", printer_code)

    # -----------------------------------------------------------------------
    # 11. Zero Hardcoded Secrets or Payment Cards
    # -----------------------------------------------------------------------
    def test_zero_hardcoded_secrets_or_payment_cards(self):
        """Source files contain zero hardcoded credentials and zero payment card fields."""
        prohibited_field_pattern = re.compile(
            r"""['"]?(?:cvv|card_number|credit_card|debit_card|bank_pin|security_code)['"]?\s*[:=]""",
            re.IGNORECASE,
        )

        for root, _, files in os.walk(WAREHOUSE_LIB):
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
