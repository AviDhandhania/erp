"""Software Bill of Materials (SBOM) generator in SPDX 2.3 and CycloneDX 1.5 JSON formats."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


def load_versions_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def generate_spdx(repo_dir: str | Path, release_json: dict | None = None) -> dict:
    root = Path(repo_dir)
    versions_env = load_versions_env(root / "deploy/versions.env")
    version_file = root / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "0.3.1"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_namespace = f"https://github.com/AviDhandhania/erp/spdxdocs/clothing-erp-{version}-{uuid.uuid4().hex[:8]}"

    packages = [
        {
            "SPDXID": "SPDXRef-Package-ClothingERP",
            "name": "clothing-erp",
            "versionInfo": version,
            "downloadLocation": f"https://github.com/AviDhandhania/erp/releases/tag/v{version}",
            "supplier": "Organization: Clothing ERP Suite Contributors",
            "licenseConcluded": "GPL-3.0-or-later",
            "licenseDeclared": "GPL-3.0-or-later",
            "description": "Integrated Clothing ERP Suite: Field Sales, Warehouse Fulfilment, and Quality Control",
        },
        {
            "SPDXID": "SPDXRef-Package-SalesERP",
            "name": "sales_erp",
            "versionInfo": "1.0.0",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "GPL-3.0-or-later",
            "supplier": "Organization: Clothing ERP Suite Contributors",
        },
        {
            "SPDXID": "SPDXRef-Package-WarehouseERP",
            "name": "warehouse_erp",
            "versionInfo": "1.0.0",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "GPL-3.0-or-later",
            "supplier": "Organization: Clothing ERP Suite Contributors",
        },
        {
            "SPDXID": "SPDXRef-Package-QualityERP",
            "name": "quality_erp",
            "versionInfo": "1.0.0",
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": "GPL-3.0-or-later",
            "supplier": "Organization: Clothing ERP Suite Contributors",
        },
        {
            "SPDXID": "SPDXRef-Package-Frappe",
            "name": "frappe",
            "versionInfo": versions_env.get("FRAPPE_REF", "v16.55.2"),
            "downloadLocation": "https://github.com/frappe/frappe.git",
            "licenseConcluded": "GPL-3.0-only",
            "supplier": "Organization: Frappe Technologies Pvt. Ltd.",
        },
        {
            "SPDXID": "SPDXRef-Package-ERPNext",
            "name": "erpnext",
            "versionInfo": versions_env.get("ERPNEXT_REF", "v16.54.0"),
            "downloadLocation": "https://github.com/frappe/erpnext.git",
            "licenseConcluded": "GPL-3.0-only",
            "supplier": "Organization: Frappe Technologies Pvt. Ltd.",
        },
        {
            "SPDXID": "SPDXRef-Package-IndiaCompliance",
            "name": "india-compliance",
            "versionInfo": versions_env.get("INDIA_COMPLIANCE_REF", "v16.10.0"),
            "downloadLocation": "https://github.com/resilient-tech/india-compliance.git",
            "licenseConcluded": "GPL-3.0-only",
            "supplier": "Organization: Resilient Tech",
        },
        {
            "SPDXID": "SPDXRef-Package-Insights",
            "name": "insights",
            "versionInfo": versions_env.get("INSIGHTS_REF", "v3.15.1"),
            "downloadLocation": "https://github.com/frappe/insights.git",
            "licenseConcluded": "GPL-3.0-only",
            "supplier": "Organization: Frappe Technologies Pvt. Ltd.",
        },
    ]

    # Add runtime locks if present
    python_locks = root / "deploy/locks/python.txt"
    if python_locks.exists():
        for line in python_locks.read_text().splitlines():
            line = line.strip()
            if line and "==" in line:
                pkg_name, pkg_ver = line.split("==", 1)
                safe_id = re.sub(r"[^A-Za-z0-9]", "-", pkg_name)
                packages.append({
                    "SPDXID": f"SPDXRef-Package-{safe_id}",
                    "name": pkg_name,
                    "versionInfo": pkg_ver,
                    "downloadLocation": f"https://pypi.org/project/{pkg_name}/{pkg_ver}/",
                    "licenseConcluded": "NOASSERTION",
                })

    relationships = [
        {
            "spdxElementId": "SPDXRef-Package-ClothingERP",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-Package-SalesERP",
        },
        {
            "spdxElementId": "SPDXRef-Package-ClothingERP",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-Package-WarehouseERP",
        },
        {
            "spdxElementId": "SPDXRef-Package-ClothingERP",
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": "SPDXRef-Package-QualityERP",
        },
        {
            "spdxElementId": "SPDXRef-Package-ClothingERP",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-Package-Frappe",
        },
        {
            "spdxElementId": "SPDXRef-Package-ClothingERP",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "SPDXRef-Package-ERPNext",
        },
    ]

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Clothing-ERP-{version}",
        "documentNamespace": doc_namespace,
        "creationInfo": {
            "created": now,
            "creators": ["Tool: clothing-erp-sbom-1.0", "Organization: Clothing ERP"],
        },
        "packages": packages,
        "relationships": relationships,
    }


def generate_cyclonedx(repo_dir: str | Path, release_json: dict | None = None) -> dict:
    root = Path(repo_dir)
    versions_env = load_versions_env(root / "deploy/versions.env")
    version_file = root / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "0.3.1"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    components = [
        {
            "type": "application",
            "bom-ref": "pkg:github/avidhandhania/erp/sales_erp@1.0.0",
            "name": "sales_erp",
            "version": "1.0.0",
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-or-later"}}],
        },
        {
            "type": "application",
            "bom-ref": "pkg:github/avidhandhania/erp/warehouse_erp@1.0.0",
            "name": "warehouse_erp",
            "version": "1.0.0",
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-or-later"}}],
        },
        {
            "type": "application",
            "bom-ref": "pkg:github/avidhandhania/erp/quality_erp@1.0.0",
            "name": "quality_erp",
            "version": "1.0.0",
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-or-later"}}],
        },
        {
            "type": "framework",
            "bom-ref": f"pkg:github/frappe/frappe@{versions_env.get('FRAPPE_REF', 'v16.55.2')}",
            "name": "frappe",
            "version": versions_env.get("FRAPPE_REF", "v16.55.2"),
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-only"}}],
        },
        {
            "type": "application",
            "bom-ref": f"pkg:github/frappe/erpnext@{versions_env.get('ERPNEXT_REF', 'v16.54.0')}",
            "name": "erpnext",
            "version": versions_env.get("ERPNEXT_REF", "v16.54.0"),
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-only"}}],
        },
        {
            "type": "application",
            "bom-ref": f"pkg:github/resilient-tech/india-compliance@{versions_env.get('INDIA_COMPLIANCE_REF', 'v16.10.0')}",
            "name": "india-compliance",
            "version": versions_env.get("INDIA_COMPLIANCE_REF", "v16.10.0"),
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-only"}}],
        },
        {
            "type": "application",
            "bom-ref": f"pkg:github/frappe/insights@{versions_env.get('INSIGHTS_REF', 'v3.15.1')}",
            "name": "insights",
            "version": versions_env.get("INSIGHTS_REF", "v3.15.1"),
            "scope": "required",
            "licenses": [{"license": {"id": "GPL-3.0-only"}}],
        },
    ]

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": now,
            "component": {
                "type": "application",
                "bom-ref": f"pkg:github/avidhandhania/erp@v{version}",
                "name": "clothing-erp",
                "version": version,
                "licenses": [{"license": {"id": "GPL-3.0-or-later"}}],
            },
        },
        "components": components,
    }


def write_sboms(repo_dir: str | Path, output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    spdx_doc = generate_spdx(repo_dir)
    cdx_doc = generate_cyclonedx(repo_dir)

    spdx_path = out / "sbom.spdx.json"
    cdx_path = out / "sbom.cdx.json"

    spdx_path.write_text(json.dumps(spdx_doc, indent=2) + "\n")
    cdx_path.write_text(json.dumps(cdx_doc, indent=2) + "\n")

    return spdx_path, cdx_path
