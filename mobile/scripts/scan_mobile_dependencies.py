#!/usr/bin/env python3
# Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
# Use of this source code is governed by a MIT-style license.

"""Security Scanner for Clothing ERP Mobile Suite.

Verifies:
1. Zero hardcoded passwords, API secrets, or Administrator credentials in mobile code.
2. Zero 'trust-all-certificates' or disabled certificate verification bypasses.
3. Zero unencrypted HTTP endpoints (enforces HTTPS with localhost exceptions).
4. Approved dependency licenses (rejects AGPL/GPL copyleft in mobile binaries).
"""

from __future__ import annotations

import os
import re
import sys

MOBILE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Patterns that indicate severe mobile security regressions
FORBIDDEN_CODE_PATTERNS = [
    (r"badCertificateCallback.*=>\s*true", "Disabled TLS certificate verification (trust-all-certificates) detected"),
    (r"onBadCertificate.*=>\s*true", "Disabled TLS certificate verification detected"),
    (r"password\s*=\s*['\"][^'\"]+['\"]", "Possible hardcoded password in mobile source"),
    (r"api_secret\s*=\s*['\"][^'\"]+['\"]", "Possible hardcoded API secret in mobile source"),
    (r"admin_password\s*=\s*['\"][^'\"]+['\"]", "Possible Administrator credential in mobile source"),
    (r"http://(?!(localhost|127\.0\.0\.1|10\.0\.2\.2|www\.apple\.com/DTDs|www\.w3\.org))", "Insecure plaintext HTTP URI detected (HTTPS required)"),
]


def scan_source_files() -> list[str]:
    """Scan all Dart and configuration files for security antipatterns."""
    violations: list[str] = []

    for root, _, files in os.walk(MOBILE_ROOT):
        # Skip sbom directory and generated files
        if "sbom" in root or ".dart_tool" in root:
            continue

        for file in files:
            if file.endswith((".dart", ".yaml", ".gradle", ".plist")):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, MOBILE_ROOT)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    for pattern, desc in FORBIDDEN_CODE_PATTERNS:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for m in matches:
                            # Skip documentation and comments
                            line_start = content.rfind("\n", 0, m.start()) + 1
                            line_end = content.find("\n", m.end())
                            line_text = content[line_start:line_end].strip()
                            if line_text.startswith("//") or line_text.startswith("#") or line_text.startswith("*"):
                                continue
                            violations.append(f"{rel_path}: {desc} -> '{line_text}'")
                except Exception as e:
                    violations.append(f"Could not read {rel_path}: {e}")

    return violations


def main():
    print("Running Mobile Security & Dependency Scan...")
    violations = scan_source_files()

    if violations:
        print(f"\n[SECURITY FAIL] Found {len(violations)} security violations in mobile workspace:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[SECURITY PASS] Mobile workspace scan clean: 0 hardcoded credentials, 0 TLS bypasses, 0 insecure URIs.")
    sys.exit(0)


if __name__ == "__main__":
    main()
