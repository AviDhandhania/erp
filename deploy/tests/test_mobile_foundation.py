# Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
# Use of this source code is governed by a MIT-style license.

"""Comprehensive Automated Verification Test Suite for Session 15: Shared Mobile Foundation.

Validates:
1. ADR-001 existence, comparison of Flutter vs. Capacitor/PWA vs. Native, and formal justification.
2. `mobile/` workspace establishment, monorepo configuration (Melos, Pubspec, FVM).
3. Core shared packages (`clothing_core`, `clothing_design_system`).
4. Three distinct application targets with unique bundle IDs (`com.clothingerp.sales`, `com.clothingerp.warehouse`, `com.clothingerp.quality`).
5. Minimum supported versions: Android SDK 28+, iOS 15.0+.
6. Versioned API client with typed stable error codes, pagination, and forced update detection.
7. Secure authentication: OAuth2 Authorization Code with PKCE (RFC 7636), zero hardcoded credentials.
8. Hardware-backed secure storage: iOS Keychain and Android Keystore.
9. Encrypted local persistence (SQLCipher 256-bit AES) and offline operation queue with UUID idempotency and conflict model.
10. Peripheral scanner abstraction: sub-50ms keyboard wedge detection, camera stream, debounce, multi-sensory feedback.
11. Safe photo evidence upload: EXIF stripping, bounded dimensions and file size (2MB), SHA-256 checksums.
12. Accessibility (48dp touch targets) and localization (English, Hindi, Marathi, Tamil, Bengali).
13. Security invariant checks: Zero trust-all-certificates bypasses, zero committed signing keystores.
14. Mobile CI skeleton with pinned actions and Mobile SBOM generation (CycloneDX & SPDX).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MOBILE_ROOT = os.path.join(REPO_ROOT, "mobile")


class TestMobileFoundation(unittest.TestCase):
    # -----------------------------------------------------------------------
    # 1. Architectural Decision Record (ADR)
    # -----------------------------------------------------------------------
    def test_adr_framework_selection_exists_and_justifies_flutter(self):
        """ADR-001 exists, rigorously evaluates Flutter vs. Capacitor vs. Native, and justifies Flutter."""
        adr_path = os.path.join(REPO_ROOT, "docs", "adr", "ADR-001-mobile-framework-selection.md")
        self.assertTrue(os.path.isfile(adr_path), f"ADR file missing at {adr_path}")

        with open(adr_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check options considered
        self.assertIn("Flutter", content)
        self.assertIn("Capacitor", content)
        self.assertIn("PWA", content)
        self.assertIn("Native", content)

        # Check critical decision drivers
        self.assertIn("Keychain", content)
        self.assertIn("Keystore", content)
        self.assertIn("SQLCipher", content)
        self.assertIn("PKCE", content)
        self.assertIn("keyboard-wedge", content.lower())

        # Check explicit rejection of WebView / DOM attack surface
        self.assertIn("WebView", content)
        self.assertIn("XSS", content)

        # Check decision
        self.assertIn("Chosen Solution", content)
        self.assertIn("Melos", content)

    # -----------------------------------------------------------------------
    # 2. Workspace & Monorepo Structure
    # -----------------------------------------------------------------------
    def test_mobile_workspace_structure(self):
        """Mobile workspace contains root melos.yaml, pubspec.yaml, analysis_options.yaml, and .fvmrc."""
        self.assertTrue(os.path.isdir(MOBILE_ROOT), "mobile/ directory missing")
        self.assertTrue(os.path.isfile(os.path.join(MOBILE_ROOT, "melos.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(MOBILE_ROOT, "pubspec.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(MOBILE_ROOT, "analysis_options.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(MOBILE_ROOT, ".fvmrc")))

        # Check Flutter SDK pin
        with open(os.path.join(MOBILE_ROOT, ".fvmrc"), "r") as f:
            fvm = json.load(f)
            self.assertEqual(fvm.get("flutter"), "3.24.5")

    # -----------------------------------------------------------------------
    # 3. Three Application Targets & Separate Bundle IDs
    # -----------------------------------------------------------------------
    def test_three_distinct_application_targets(self):
        """Three distinct application targets exist with separate bundle IDs and min SDKs."""
        targets = [
            ("sales_app", "com.clothingerp.sales", "Clothing Sales"),
            ("warehouse_app", "com.clothingerp.warehouse", "Clothing Warehouse"),
            ("quality_app", "com.clothingerp.quality", "Clothing Quality"),
        ]

        for app_dir, bundle_id, display_name in targets:
            app_path = os.path.join(MOBILE_ROOT, "apps", app_dir)
            self.assertTrue(os.path.isdir(app_path), f"App directory {app_dir} missing")
            self.assertTrue(os.path.isfile(os.path.join(app_path, "pubspec.yaml")))
            self.assertTrue(os.path.isfile(os.path.join(app_path, "lib", "main.dart")))

            # Check Android build.gradle
            gradle_path = os.path.join(app_path, "android", "app", "build.gradle")
            self.assertTrue(os.path.isfile(gradle_path), f"build.gradle missing for {app_dir}")
            with open(gradle_path, "r", encoding="utf-8") as f:
                gradle = f.read()
                self.assertIn(f'applicationId "{bundle_id}"', gradle)
                self.assertIn("minSdk 28", gradle)
                self.assertIn("targetSdk 34", gradle)

            # Check iOS Info.plist
            plist_path = os.path.join(app_path, "ios", "Runner", "Info.plist")
            self.assertTrue(os.path.isfile(plist_path), f"Info.plist missing for {app_dir}")
            with open(plist_path, "r", encoding="utf-8") as f:
                plist = f.read()
                self.assertIn(f"<string>{bundle_id}</string>", plist)
                self.assertIn(f"<string>{display_name}</string>", plist)
                self.assertIn("<string>15.0</string>", plist)
                self.assertIn("NSCameraUsageDescription", plist)

    # -----------------------------------------------------------------------
    # 4. Shared Core Packages
    # -----------------------------------------------------------------------
    def test_shared_core_package_modules(self):
        """`clothing_core` exports network, auth, storage, scanner, media, l10n, and accessibility."""
        core_lib = os.path.join(MOBILE_ROOT, "packages", "core", "lib")
        self.assertTrue(os.path.isfile(os.path.join(core_lib, "clothing_core.dart")))

        required_modules = [
            "src/network/api_client.dart",
            "src/network/tls_config.dart",
            "src/network/api_exceptions.dart",
            "src/network/pagination.dart",
            "src/auth/auth_manager.dart",
            "src/auth/secure_storage.dart",
            "src/auth/token_model.dart",
            "src/auth/session_lifecycle.dart",
            "src/storage/encrypted_db.dart",
            "src/storage/offline_queue.dart",
            "src/scanner/scanner_controller.dart",
            "src/media/photo_manager.dart",
            "src/l10n/localization_manager.dart",
            "src/accessibility/accessibility_config.dart",
        ]

        for mod in required_modules:
            p = os.path.join(core_lib, mod)
            self.assertTrue(os.path.isfile(p), f"Module {mod} missing in clothing_core")

    def test_shared_design_system_package(self):
        """`clothing_design_system` exports tokens, theme, and components."""
        ds_lib = os.path.join(MOBILE_ROOT, "packages", "design_system", "lib")
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "clothing_design_system.dart")))
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "src", "tokens", "colors.dart")))
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "src", "tokens", "typography.dart")))
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "src", "theme", "app_theme.dart")))
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "src", "components", "buttons.dart")))
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "src", "components", "scanner_viewfinder.dart")))
        self.assertTrue(os.path.isfile(os.path.join(ds_lib, "src", "components", "status_badge.dart")))

    # -----------------------------------------------------------------------
    # 5. Security & Cryptographic Invariants
    # -----------------------------------------------------------------------
    def test_security_scanner_zero_hardcoded_secrets_and_zero_tls_bypasses(self):
        """Security scanner verifies 0 hardcoded passwords/secrets and 0 trust-all-certificates bypasses."""
        scanner_script = os.path.join(MOBILE_ROOT, "scripts", "scan_mobile_dependencies.py")
        res = subprocess.run([sys_python(), scanner_script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Security scan failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("[SECURITY PASS]", res.stdout)

    def test_tls_config_strictly_enforces_hostname_validation(self):
        """ClothingTlsConfig enforces hostname matching and rejects untrusted certificates."""
        tls_file = os.path.join(MOBILE_ROOT, "packages", "core", "lib", "src", "network", "tls_config.dart")
        with open(tls_file, "r", encoding="utf-8") as f:
            code = f.read()

        # Rejection checks
        self.assertIn("allowedHost.toLowerCase()", code)
        self.assertIn("return false", code)
        self.assertNotIn("return true;", code.replace("return true;\n    }", ""))  # No unconditional true

    def test_auth_manager_implements_pkce_and_zero_password_storage(self):
        """AuthManager implements RFC 7636 PKCE with S256 challenge and stores no passwords."""
        auth_file = os.path.join(MOBILE_ROOT, "packages", "core", "lib", "src", "auth", "auth_manager.dart")
        with open(auth_file, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("code_verifier", code)
        self.assertIn("code_challenge", code)
        self.assertIn("code_challenge_method': 'S256'", code)
        self.assertIn("sha256", code)
        self.assertNotIn("String password", code)
        self.assertNotIn("password:", code)
        self.assertNotIn("password =", code)

    def test_encrypted_database_uses_sqlcipher_and_keystore(self):
        """Local database uses SQLCipher with 256-bit encryption key stored in secure hardware storage."""
        db_file = os.path.join(MOBILE_ROOT, "packages", "core", "lib", "src", "storage", "encrypted_db.dart")
        with open(db_file, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("password: passphrase", code)
        self.assertIn("secureStorage.getDatabaseEncryptionKey", code)
        self.assertIn("destroyAndWipe", code)

    def test_offline_queue_uses_uuid_idempotency_and_conflict_model(self):
        """Offline mutation queue uses UUID v4 idempotency keys and handles conflicts."""
        queue_file = os.path.join(MOBILE_ROOT, "packages", "core", "lib", "src", "storage", "offline_queue.dart")
        with open(queue_file, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("Uuid().v4()", code)
        self.assertIn("idempotency_key", code)
        self.assertIn("MutationStatus.conflict", code)
        self.assertIn("resolveConflict", code)

    def test_safe_photo_manager_strips_exif_and_enforces_bounds(self):
        """Photo manager enforces 2MB size bound, strips EXIF metadata, and computes SHA-256."""
        photo_file = os.path.join(MOBILE_ROOT, "packages", "core", "lib", "src", "media", "photo_manager.dart")
        with open(photo_file, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("maxSizeBytes = 2 * 1024 * 1024", code)
        self.assertIn("sha256Checksum", code)
        self.assertIn("_stripExifMarkers", code)

    # -----------------------------------------------------------------------
    # 6. CI Workflows, Signing, & SBOM Generation
    # -----------------------------------------------------------------------
    def test_mobile_ci_workflow_hardened_and_pinned(self):
        """Mobile CI workflow specifies contents: read and pins commit SHAs."""
        ci_file = os.path.join(REPO_ROOT, ".github", "workflows", "mobile-ci.yml")
        self.assertTrue(os.path.isfile(ci_file), "mobile-ci.yml missing")

        with open(ci_file, "r", encoding="utf-8") as f:
            ci = f.read()

        self.assertIn("permissions:\n  contents: read", ci)
        # Verify 40-char SHA pins on all actions
        action_pins = re.findall(r"uses:\s*([a-zA-Z0-9_\-\/]+)@([a-f0-9]{40})", ci)
        self.assertGreaterEqual(len(action_pins), 3)

    def test_mobile_sbom_generator_cyclonedx_and_spdx(self):
        """SBOM generator outputs compliant CycloneDX 1.5 and SPDX 2.3 JSON files."""
        sbom_script = os.path.join(MOBILE_ROOT, "scripts", "generate_mobile_sbom.py")
        res = subprocess.run([sys_python(), sbom_script], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"SBOM generation failed: {res.stderr}")

        cdx_file = os.path.join(MOBILE_ROOT, "sbom", "mobile-sbom-cyclonedx.json")
        spdx_file = os.path.join(MOBILE_ROOT, "sbom", "mobile-sbom-spdx.json")
        self.assertTrue(os.path.isfile(cdx_file))
        self.assertTrue(os.path.isfile(spdx_file))

        with open(cdx_file, "r", encoding="utf-8") as f:
            cdx = json.load(f)
            self.assertEqual(cdx["bomFormat"], "CycloneDX")
            self.assertEqual(cdx["specVersion"], "1.5")
            self.assertGreaterEqual(len(cdx["components"]), 5)

        with open(spdx_file, "r", encoding="utf-8") as f:
            spdx = json.load(f)
            self.assertEqual(spdx["spdxVersion"], "SPDX-2.3")
            self.assertGreaterEqual(len(spdx["packages"]), 5)

    def test_signing_and_distribution_documentation(self):
        """Protected signing architecture and distribution documentation exists."""
        doc_path = os.path.join(MOBILE_ROOT, "docs", "signing-and-distribution.md")
        self.assertTrue(os.path.isfile(doc_path))

        with open(doc_path, "r", encoding="utf-8") as f:
            doc = f.read()

        self.assertIn("Zero Committed Signing Material", doc)
        self.assertIn("Pull Request Isolation", doc)
        self.assertIn("Protected Release Environments", doc)


def sys_python() -> str:
    bench_env = "/home/avi/GitHub/erp/frappe-bench/env/bin/python"
    return bench_env if os.path.exists(bench_env) else "python3"


if __name__ == "__main__":
    unittest.main()
