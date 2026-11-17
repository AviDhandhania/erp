# Supply Chain Security, Signed Releases and Dependency Integrity

This document establishes the supply-chain security controls, build provenance verification, and release integrity architecture for the Clothing ERP Suite (`sales_erp`, `warehouse_erp`, and `quality_erp`).

---

## 1. Threat Model & Trust Boundaries

The Clothing ERP supply chain is protected against three primary threat classes:
1. **Upstream Compromise**: Malicious changes or account takeovers in third-party GitHub Actions, PyPI dependencies, or upstream repositories (`frappe`, `erpnext`, `india_compliance`, `insights`).
2. **Build Pipeline Tampering**: Compromised CI runners or intermediate build steps altering binary artifacts, release manifests, or container images before publishing.
3. **Distribution & Man-in-the-Middle (MitM) Attacks**: Forged releases, DNS spoofing, unauthorized mirrors, or tampered checksum manifests delivered to customer installations.

---

## 2. GitHub Actions Security & Immutable Commit Pinning

### 2.1 Immutable SHA Pinning
Mutable tags (e.g. `v4`, `v2`, `main`) in third-party GitHub Actions introduce supply-chain vulnerability because tags can be silently retargeted if an action repository is compromised.

All third-party GitHub Actions across `.github/workflows/` (`checks.yml`, `verify.yml`, `release.yml`) are pinned strictly to immutable 40-character commit SHAs with standard version comments:

```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
- uses: astral-sh/setup-uv@86029dd7c2826cf84be8593361e6c38ceaaae54c # v5.1.0
- uses: actions/upload-artifact@b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882 # v4.4.3
- uses: actions/download-artifact@fa0a91b85d4f404e444e00e005971372dc801d16 # v4.1.8
- uses: actions/attest-build-provenance@c074443f1a5fb4aee83904b711427953c82d61d1 # v2.2.3
```

### 2.2 Minimal Workflow Permissions
Every GitHub Actions workflow declares explicit top-level `permissions:` defaulting to read-only:

```yaml
permissions:
  contents: read
```

Jobs requiring elevated permissions (such as release draft creation or provenance attestation generation) declare scoped job-level permissions:
- `contents: write`: Allowed solely for publishing draft release notes and asset uploads.
- `id-token: write`: Allowed solely for GitHub OIDC token exchange during provenance attestation.
- `attestations: write`: Allowed solely for signing build provenance statements.

### 2.3 Protected Release Environments and Tag Policies
- **Branch Protection**: Direct pushes to `main` are restricted. Merges require reviewed Pull Requests with passing CI (`verify.yml`).
- **Tag Protection**: Tags matching `v*.*.*` require approval from designated release maintainers.
- **Environment Gate**: The `publish` job is bound to a protected `production-release` GitHub environment requiring explicit two-person approval before release artifacts are marked public.

---

## 3. Supply Chain & Code Scanners

Clothing ERP includes automated supply chain scanners in `deploy/supply_chain/`:

```
deploy/supply_chain/
├── secrets_scanner.py     # Detects credentials across files and Git history
├── dependency_scanner.py  # SCA scanner for Python, Node, and mobile builds
├── license_scanner.py     # Audits licenses against approved open-source list
├── sast.py                # AST analysis for command injection, eval, unsafe deserialization
├── sbom.py                # SPDX 2.3 and CycloneDX 1.5 SBOM generator
└── runner.py              # Unified CLI scanner
```

### 3.1 Secret Scanning
- Scans all files and the entire Git history (`git log -p`) for private keys, AWS access keys, GitHub tokens, high-entropy secrets, and hardcoded passwords.
- Enforces zero secrets in source control. Test harnesses must use documented synthetic constants (e.g. `test-only-ephemeral-password`).

### 3.2 Software Composition Analysis (SCA) & Exact Dependency Locks
- Pinned runtime dependencies in `deploy/locks/python.txt` and `deploy/versions.env` are audited for known vulnerabilities (CVEs) and deprecated libraries (e.g. `pycrypto`).
- Floating versions (`^`, `~=`, `*`) are prohibited in production lockfiles. Every dependency is pinned by exact version (`==`) or full 40-character Git commit hash.

### 3.3 License Compliance
- Clothing ERP Suite and upstream Frappe/ERPNext are distributed under **GPL-3.0**.
- All dependencies must comply with approved open-source licenses: MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, Python PSF, LGPL-2.1/3.0, and GPL-2.0/3.0.
- Proprietary, commercial-only, non-commercial (CC-BY-NC), or SSPL licenses are rejected by the automated license scanner.

### 3.4 Static Application Security Testing (SAST)
- Evaluates the Python AST across `sales_erp`, `warehouse_erp`, `quality_erp`, and `deploy`.
- Detects:
  - Dynamic code execution: `eval()`, `exec()`
  - Shell command injection: `shell=True` in `subprocess`, unquoted `os.system`
  - Unsafe deserialization: `pickle.loads()`, `yaml.load()` without SafeLoader
  - Insecure temporary files: `tempfile.mktemp()`

---

## 4. Software Bill of Materials (SBOM)

During every release verification and build, machine-readable SBOMs are generated:
1. **SPDX 2.3 JSON**: `dist/release/sbom.spdx.json`
2. **CycloneDX 1.5 JSON**: `dist/release/sbom.cdx.json`

The SBOM catalogs:
- Core Suite applications: `clothing-erp`, `sales_erp`, `warehouse_erp`, `quality_erp`
- Pinned upstream frameworks: `frappe` (v16.55.2), `erpnext` (v16.54.0), `india-compliance` (v16.10.0), `insights` (v3.15.1)
- Runtimes: Python 3.14.9, Node 24.22.2 LTS, Bench 5.31.1, uv
- System services: MariaDB 11.8, Redis 7.4, Nginx 1.26
- Direct and transitive Python runtime libraries with exact versions, package download URLs, and declared licenses.

---

## 5. Publisher Provenance & Release Integrity Verification

### 5.1 Publisher Provenance
SHA-256 checksums alone verify artifact download integrity, but they do not prove publisher authenticity if an attacker compromises the distribution channel.

The release client (`deploy/release/common.py` and `deploy/release/provenance.py`) enforces:
1. **Repository Identity**: Releases must originate from the authoritative repository `AviDhandhania/erp`. Any other repository or altered manifest is rejected.
2. **Attestation Verification**: Integrates GitHub Build Provenance (in-toto statement / Sigstore attestation) validating that the release artifact was built on GitHub Actions runner from the authorized workflow and commit.
3. **Strict HTTPS & Domain Validation**: All release downloads and redirects are restricted strictly to authorized domains (`github.com`, `api.github.com`, `objects.githubusercontent.com`, `github-releases.githubusercontent.com`). External or HTTP redirects trigger immediate abort.
4. **SemVer and Archive Name Verification**: Enforces format `clothing-erp-vX.Y.Z.tar.gz` and exact match between manifest version and release tag.

### 5.2 Release Revocation Registry & Procedure
If a published release is discovered to contain a critical security vulnerability or corruption, it is revoked via the Revocation Registry (`deploy/release/revocations.json`).

The update manager and installer inspect the revocation registry before downloading or applying any release:
- If a target version is marked revoked, `clothing-erp update` rejects installation with the revocation reason and suggests the superseded version.
- Rollbacks to a revoked release version are blocked.

```json
{
  "schema": 1,
  "repository": "AviDhandhania/erp",
  "revoked_releases": {
    "v0.1.0": {
      "reason": "Pre-production insecure HTTP prototype with plain-text credentials",
      "revoked_at": "2026-11-07T00:00:00Z",
      "superseded_by": "v0.3.1"
    }
  }
}
```

### 5.3 Emergency Release & Revocation Procedure
In the event of a critical zero-day or compromised signing key:
1. **Publish Hotfix**: Cut an emergency release `vX.Y.(Z+1)` with the remediation.
2. **Revoke Vulnerable Version**: Add the vulnerable version `vX.Y.Z` to `deploy/release/revocations.json` with reason and timestamp.
3. **Notify Customers & Operators**: Issue security advisory with upgrade instructions.
4. **Enforce Update**: On container check, `clothing-erp check` flags the currently installed release as revoked and prompts an immediate update to the hotfix release.
