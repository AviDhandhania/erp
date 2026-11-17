"""Automated unit and integration tests for supply chain security, provenance, and DR."""

import gzip
import json
import re
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from deploy.release.encrypted_backup import (
    create_encrypted_backup_bundle,
    decrypt_backup_bundle,
    enforce_retention_policy,
    generate_backup_key,
    get_key_id,
    verify_isolated_restore,
)
from deploy.release.provenance import (
    check_revocation,
    validate_redirect_url,
    verify_provenance_attestation,
    verify_release_integrity,
)
from deploy.supply_chain.license_scanner import scan_lockfile
from deploy.supply_chain.sast import run_sast_scan
from deploy.supply_chain.sbom import generate_cyclonedx, generate_spdx
from deploy.supply_chain.secrets_scanner import scan_files, scan_text


class TestWorkflowHardening(unittest.TestCase):
    """Verify GitHub Actions workflows enforce immutable commit pinning and least privilege."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent.parent
        self.workflows_dir = self.repo_root / ".github/workflows"

    def test_github_workflows_pin_immutable_commit_shas(self):
        """All third-party GitHub Actions must be pinned to 40-character hex commit SHAs."""
        workflow_files = list(self.workflows_dir.glob("*.yml"))
        self.assertTrue(len(workflow_files) >= 3, "Expected at least 3 workflow files")

        sha_regex = re.compile(r"^[a-f0-9]{40}$")

        for wf in workflow_files:
            content = wf.read_text()
            for line_no, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if line.startswith("- uses:") or line.startswith("uses:"):
                    action_ref = line.split("uses:")[1].strip()
                    # Skip local workflow or action calls like ./.github/...
                    if action_ref.startswith("./"):
                        continue
                    # Must contain @
                    self.assertIn("@", action_ref, f"{wf.name}:{line_no} action missing version ref: {action_ref}")
                    action_name, ref_part = action_ref.split("@", 1)
                    ref = ref_part.split("#")[0].strip()
                    self.assertTrue(
                        sha_regex.fullmatch(ref),
                        f"{wf.name}:{line_no} action {action_name} must use 40-char commit SHA, got: {ref}",
                    )

    def test_github_workflows_declare_minimal_permissions(self):
        """Every workflow file must define top-level permissions: contents: read."""
        workflow_files = list(self.workflows_dir.glob("*.yml"))
        for wf in workflow_files:
            content = wf.read_text()
            self.assertIn("permissions:", content, f"{wf.name} missing permissions block")
            self.assertIn("contents: read", content, f"{wf.name} must declare contents: read")


class TestSupplyChainScanners(unittest.TestCase):
    """Verify secret scanning, SAST, SBOM generation, and license auditing."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent.parent

    def test_secret_scanner_detects_credentials(self):
        """Secret scanner must detect AWS keys, private keys and tokens."""
        synthetic_secret = "AKIA" + "1" * 16
        findings = scan_text(f"AWS_KEY = '{synthetic_secret}'", "test_source")
        self.assertTrue(len(findings) > 0)
        self.assertEqual(findings[0]["rule"], "AWS Access Key ID")

        # Allowlisted strings must not trigger findings
        safe_line = "PASSWORD = 'test-only-ephemeral-password'"
        safe_findings = scan_text(safe_line, "test_source")
        self.assertEqual(len(safe_findings), 0)

    def test_repository_has_zero_committed_secrets(self):
        """Repository files must contain zero committed credentials."""
        findings = scan_files(self.repo_root)
        self.assertEqual(len(findings), 0, f"Found unexpected secrets: {findings}")

    def test_sast_engine_detects_dangerous_patterns(self):
        """SAST engine must detect eval(), exec(), and subprocess(shell=True)."""
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            vuln_file = temp_path / "vuln.py"
            vuln_file.write_text(
                "import os, subprocess, yaml\n"
                "eval('1+1')\n"
                "exec('pass')\n"
                "subprocess.Popen('ls', shell=True)\n"
                "os.system('id')\n"
                "yaml.load('foo: bar')\n"
            )
            findings = run_sast_scan(temp_path, targets=["."])
            rules_found = {f["rule"] for f in findings}
            self.assertIn("DYNAMIC_CODE_EXECUTION", rules_found)
            self.assertIn("SUBPROCESS_SHELL_TRUE", rules_found)
            self.assertIn("OS_COMMAND_EXECUTION", rules_found)
            self.assertIn("UNSAFE_YAML_DESERIALIZATION", rules_found)

    def test_sbom_generation_spdx_and_cyclonedx(self):
        """SBOM generator must output valid SPDX 2.3 and CycloneDX 1.5 JSON structures."""
        spdx = generate_spdx(self.repo_root)
        self.assertEqual(spdx["spdxVersion"], "SPDX-2.3")
        self.assertIn("packages", spdx)
        pkg_names = {p["name"] for p in spdx["packages"]}
        for expected in ("clothing-erp", "sales_erp", "warehouse_erp", "quality_erp", "frappe", "erpnext"):
            self.assertIn(expected, pkg_names)

        cdx = generate_cyclonedx(self.repo_root)
        self.assertEqual(cdx["bomFormat"], "CycloneDX")
        self.assertEqual(cdx["specVersion"], "1.5")
        self.assertIn("components", cdx)
        comp_names = {c["name"] for c in cdx["components"]}
        for expected in ("sales_erp", "warehouse_erp", "quality_erp", "frappe", "erpnext"):
            self.assertIn(expected, comp_names)


class TestPublisherProvenance(unittest.TestCase):
    """Verify publisher provenance, redirect domain security, and revocation checks."""

    def test_redirect_url_validation(self):
        """Downloads must use HTTPS and allowed publisher domains."""
        # Allowed domains
        validate_redirect_url("https://github.com/AviDhandhania/erp/releases")
        validate_redirect_url("https://objects.githubusercontent.com/github-production-release-asset-12345")

        # Insecure HTTP must fail
        with self.assertRaises(ValueError):
            validate_redirect_url("http://github.com/AviDhandhania/erp")

        # Unauthorized external domain must fail
        with self.assertRaises(ValueError):
            validate_redirect_url("https://malicious-mirror.evil/release.tar.gz")

    def test_revocation_registry_rejects_revoked_releases(self):
        """Revocation check must block known revoked versions."""
        with self.assertRaises(ValueError) as ctx:
            check_revocation("v0.1.0")
        self.assertIn("REVOKED", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            check_revocation("v0.2.0")
        self.assertIn("REVOKED", str(ctx.exception))

        # Valid unrevoked version passes
        check_revocation("v0.3.1")

    def test_provenance_attestation_verification(self):
        """Attestation verification checks repository and subject SHA-256 match."""
        archive_sha = "a" * 64
        with tempfile.NamedTemporaryFile("w+", suffix=".jsonl") as tf:
            statement = {
                "predicateType": "https://slsa.dev/provenance/v1",
                "subject": [{"name": "clothing-erp-v0.3.1.tar.gz", "digest": {"sha256": archive_sha}}],
                "predicate": {
                    "buildDefinition": {
                        "internalParameters": {"github": {"repository": "AviDhandhania/erp"}}
                    }
                },
            }
            tf.write(json.dumps(statement) + "\n")
            tf.flush()

            # Valid attestation passes
            self.assertTrue(
                verify_provenance_attestation(
                    {"version": "v0.3.1"},
                    archive_sha,
                    attestation_path=tf.name,
                    expected_repo="AviDhandhania/erp",
                )
            )

            # Mismatched SHA-256 fails
            with self.assertRaises(ValueError):
                verify_provenance_attestation(
                    {"version": "v0.3.1"},
                    "b" * 64,
                    attestation_path=tf.name,
                    expected_repo="AviDhandhania/erp",
                )

            # Mismatched repository fails
            with self.assertRaises(ValueError):
                verify_provenance_attestation(
                    {"version": "v0.3.1"},
                    archive_sha,
                    attestation_path=tf.name,
                    expected_repo="OtherOrg/evil-repo",
                )


class TestEncryptedBackupAndDisasterRecovery(unittest.TestCase):
    """Verify encrypted backup pipeline, key segregation, and isolated restore drills."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test-dr-")
        self.work_path = Path(self.temp_dir)
        self.raw_backup = self.work_path / "raw_backup"
        self.raw_backup.mkdir()

        # Seed synthetic backup contents
        with gzip.open(self.raw_backup / "database.sql.gz", "wb") as f:
            f.write(b"CREATE TABLE tabUser (name VARCHAR(140));\nINSERT INTO tabUser VALUES ('test-user');\n")

        with tarfile.open(self.raw_backup / "files.tar.gz", "w:gz") as tar:
            f_txt = self.work_path / "evidence.txt"
            f_txt.write_text("synthetic evidence attachment")
            tar.add(f_txt, arcname="private/files/evidence.txt")

        (self.raw_backup / "site_config.json").write_text(
            json.dumps({"db_name": "clothing_local", "encryption_key": "frappe_secret_key_123"})
        )
        (self.raw_backup / "backup.json").write_text(
            json.dumps({
                "database": "clothing_local",
                "created_at": "20261117T180000Z",
                "current": {"version": "v0.3.1"},
                "sha256": {},
            })
        )

        self.key = generate_backup_key()
        self.key_id = get_key_id(self.key)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_encrypted_backup_creation_and_key_segregation(self):
        """Encrypted bundle must encrypt all artifacts and NOT contain the encryption key."""
        out_store = self.work_path / "encrypted_store"
        bundle = create_encrypted_backup_bundle(self.raw_backup, out_store, self.key)

        manifest_path = bundle / "encrypted_manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text())

        # Verify key_id matches fingerprint, and the actual key is NEVER in manifest
        self.assertEqual(manifest["key_id"], self.key_id)
        self.assertNotIn("key", manifest)
        self.assertNotIn(self.key, manifest_path.read_text())

        # Verify all artifacts in bundle have .enc extension
        for artifact_name in manifest["artifacts"]:
            self.assertTrue(artifact_name.endswith(".enc"))
            self.assertTrue((bundle / artifact_name).exists())

    def test_tampered_encrypted_artifact_is_rejected(self):
        """Tampering with an encrypted artifact must fail authentication tag check."""
        out_store = self.work_path / "encrypted_store"
        bundle = create_encrypted_backup_bundle(self.raw_backup, out_store, self.key)

        # Alter one byte in encrypted file
        enc_db = bundle / "database.sql.gz.enc"
        data = bytearray(enc_db.read_bytes())
        data[-1] ^= 0xFF
        enc_db.write_bytes(bytes(data))

        restore_dest = self.work_path / "restore_test"
        with self.assertRaises(ValueError):
            decrypt_backup_bundle(bundle, restore_dest, self.key)

    def test_wrong_key_fails_decryption(self):
        """Attempting restore with mismatched key must raise ValueError."""
        out_store = self.work_path / "encrypted_store"
        bundle = create_encrypted_backup_bundle(self.raw_backup, out_store, self.key)

        wrong_key = generate_backup_key()
        restore_dest = self.work_path / "restore_test"
        with self.assertRaises(ValueError):
            decrypt_backup_bundle(bundle, restore_dest, wrong_key)

    def test_automated_isolated_restore_verification_drill(self):
        """Isolated restore drill validates SQL tables, files, and config without touching live site."""
        out_store = self.work_path / "encrypted_store"
        bundle = create_encrypted_backup_bundle(self.raw_backup, out_store, self.key)

        drill = verify_isolated_restore(bundle, self.key, isolated_scratch_dir=self.work_path)
        self.assertEqual(drill["status"], "PASSED")
        self.assertTrue(drill["checks"]["database_sql"]["valid_gzip"])
        self.assertTrue(drill["checks"]["database_sql"]["has_table_definitions"])
        self.assertTrue(drill["checks"]["files_archive"]["valid_tar"])
        self.assertEqual(drill["checks"]["files_archive"]["member_count"], 1)
        self.assertTrue(drill["checks"]["site_config"]["has_encryption_key"])

    def test_retention_policy_pruning(self):
        """Retention policy prunes older backups beyond configured limit."""
        backups_store = self.work_path / "retention_store"
        backups_store.mkdir()

        # Create 10 synthetic backup directories
        for i in range(10):
            d = backups_store / f"clothing-encrypted-backup-20261117T18{i:02d}00Z"
            d.mkdir()

        pruned = enforce_retention_policy(backups_store, keep_daily=5)
        self.assertEqual(len(pruned), 5)
        remaining = list(backups_store.iterdir())
        self.assertEqual(len(remaining), 5)


if __name__ == "__main__":
    unittest.main()
