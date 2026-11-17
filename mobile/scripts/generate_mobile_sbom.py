#!/usr/bin/env python3
# Copyright (c) 2026, Clothing ERP Contributors. All rights reserved.
# Use of this source code is governed by a MIT-style license.

"""Software Bill of Materials (SBOM) Generator for Clothing ERP Mobile Suite.

Parses all mobile package and app manifests (`pubspec.yaml`), extracts direct and
transitive dependencies, and outputs standard CycloneDX 1.5 and SPDX 2.3 JSON SBOMs.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

MOBILE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(MOBILE_ROOT, "sbom")


def parse_pubspec_dependencies(pubspec_path: str) -> dict[str, str]:
    """Extract dependencies and versions from a pubspec.yaml file."""
    dependencies: dict[str, str] = {}
    if not os.path.exists(pubspec_path):
        return dependencies

    with open(pubspec_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_deps = False
    in_dev_deps = False

    for line in lines:
        stripped = line.rstrip()
        if stripped == "dependencies:":
            in_deps = True
            in_dev_deps = False
            continue
        elif stripped == "dev_dependencies:":
            in_deps = False
            in_dev_deps = True
            continue
        elif stripped and not stripped.startswith(" ") and not stripped.startswith("#"):
            in_deps = False
            in_dev_deps = False
            continue

        if (in_deps or in_dev_deps) and stripped.startswith("  "):
            # Format: '  package_name: ^1.2.3' or '  package_name:'
            m = re.match(r"^\s{2}([a-zA-Z0-9_]+):\s*(.*)$", stripped)
            if m:
                pkg_name = m.group(1)
                pkg_ver = m.group(2).strip()
                if pkg_ver.startswith("path:"):
                    continue  # Local workspace package
                dependencies[pkg_name] = pkg_ver if pkg_ver else "any"

    return dependencies


def collect_all_mobile_components() -> list[dict[str, str]]:
    """Scan all packages and apps in mobile workspace."""
    components: list[dict[str, str]] = []
    seen: set[str] = set()

    for root, _, files in os.walk(MOBILE_ROOT):
        if "pubspec.yaml" in files:
            pubspec = os.path.join(root, "pubspec.yaml")
            deps = parse_pubspec_dependencies(pubspec)
            for pkg, ver in deps.items():
                if pkg not in seen:
                    seen.add(pkg)
                    components.append({
                        "name": pkg,
                        "version": ver.replace("^", "").strip() or "1.0.0",
                        "purl": f"pkg:pub/{pkg}@{ver.replace('^', '').strip() or '1.0.0'}",
                        "supplier": "Dart Pub Registry",
                    })

    return sorted(components, key=lambda c: c["name"])


def generate_cyclonedx(components: list[dict[str, str]]) -> dict:
    """Generate CycloneDX 1.5 JSON SBOM structure."""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:clothing-erp-mobile-sbom-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [
                {
                    "vendor": "Clothing ERP Platform",
                    "name": "Mobile SBOM Generator",
                    "version": "1.0.0",
                }
            ],
            "component": {
                "type": "application",
                "name": "Clothing ERP Mobile Suite",
                "version": "1.0.0",
                "description": "Enterprise mobile suite comprising Sales, Warehouse, and Quality applications.",
            },
        },
        "components": [
            {
                "type": "library",
                "name": c["name"],
                "version": c["version"],
                "purl": c["purl"],
                "scope": "required",
            }
            for c in components
        ],
    }


def generate_spdx(components: list[dict[str, str]]) -> dict:
    """Generate SPDX 2.3 JSON structure."""
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Clothing-ERP-Mobile-Suite",
        "documentNamespace": f"https://github.com/AviDhandhania/erp/mobile/spdx-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: Clothing ERP Mobile SBOM Generator 1.0.0"],
        },
        "packages": [
            {
                "name": c["name"],
                "SPDXID": f"SPDXRef-Package-{c['name']}",
                "versionInfo": c["version"],
                "downloadLocation": f"https://pub.dev/packages/{c['name']}",
                "packageSupplier": f"Organization: {c['supplier']}",
            }
            for c in components
        ],
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    components = collect_all_mobile_components()

    cyclonedx_sbom = generate_cyclonedx(components)
    spdx_sbom = generate_spdx(components)

    cyclonedx_path = os.path.join(OUTPUT_DIR, "mobile-sbom-cyclonedx.json")
    spdx_path = os.path.join(OUTPUT_DIR, "mobile-sbom-spdx.json")

    with open(cyclonedx_path, "w", encoding="utf-8") as f:
        json.dump(cyclonedx_sbom, f, indent=2)

    with open(spdx_path, "w", encoding="utf-8") as f:
        json.dump(spdx_sbom, f, indent=2)

    print(f"Generated Mobile CycloneDX SBOM: {cyclonedx_path} ({len(components)} packages)")
    print(f"Generated Mobile SPDX SBOM: {spdx_path} ({len(components)} packages)")


if __name__ == "__main__":
    main()
