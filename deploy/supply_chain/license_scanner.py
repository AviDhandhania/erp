"""License compliance scanner for Python, JavaScript and runtime dependencies."""

import json
import re
from pathlib import Path
from importlib import metadata

APPROVED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "Apache 2.0",
    "Apache License 2.0",
    "Apache Software License",
    "BSD",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Python Software Foundation License",
    "PSF",
    "PSF-2.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "GPL-2.0",
    "GPL-3.0",
    "GNU General Public License v3 (GPLv3)",
    "GNU General Public License v2 (GPLv2)",
    "MPL-2.0",
    "CC0-1.0",
    "Public Domain",
    "Unlicense",
    "ZPL 2.1",
    "Historical Permission Notice and Disclaimer (HPND)",
}

PROHIBITED_LICENSES = {
    "Proprietary",
    "All Rights Reserved",
    "CC-BY-NC",
    "CC-BY-NC-SA",
    "SSPL",
}


def normalize_license(raw_license: str | None) -> str:
    if not raw_license or raw_license.strip() in ("", "UNKNOWN", "None"):
        return "UNKNOWN"
    norm = raw_license.strip()
    for approved in APPROVED_LICENSES:
        if approved.lower() == norm.lower():
            return approved
    return norm


def scan_python_packages(package_list: list[str] | None = None) -> list[dict]:
    """Scan licenses of installed or specified Python packages."""
    findings = []
    if package_list:
        pkgs = package_list
    else:
        try:
            pkgs = [dist.metadata.get("Name") for dist in metadata.distributions() if dist.metadata.get("Name")]
        except Exception:
            pkgs = []

    for name in pkgs:
        if not name:
            continue
        try:
            dist = metadata.distribution(name)
            meta = dist.metadata
            lic = meta.get("License") or ""
            classifiers = meta.get_all("Classifier") or []
            license_from_classifiers = []
            for c in classifiers:
                if c.startswith("License ::"):
                    parts = c.split("::")
                    if len(parts) > 2:
                        license_from_classifiers.append(parts[-1].strip())

            effective_lic = lic or (", ".join(license_from_classifiers) if license_from_classifiers else "UNKNOWN")
            
            # Check if any recognized approved license matches
            is_approved = any(
                app.lower() in effective_lic.lower() for app in APPROVED_LICENSES
            )
            is_prohibited = any(
                pro.lower() in effective_lic.lower() for pro in PROHIBITED_LICENSES
            )

            status = "APPROVED" if is_approved and not is_prohibited else ("PROHIBITED" if is_prohibited else "REVIEW_REQUIRED")
            findings.append({
                "package": name,
                "version": dist.version,
                "license": effective_lic,
                "status": status,
            })
        except metadata.PackageNotFoundError:
            findings.append({
                "package": name,
                "version": "unknown",
                "license": "NOT_INSTALLED",
                "status": "REVIEW_REQUIRED",
            })
    return findings


def scan_lockfile(lockfile_path: str | Path) -> list[dict]:
    """Parse python.txt or similar lockfile and scan licenses."""
    path = Path(lockfile_path)
    if not path.exists():
        return []
    packages = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            pkg_name = line.split("==")[0].strip()
            packages.append(pkg_name)
    return scan_python_packages(packages)
