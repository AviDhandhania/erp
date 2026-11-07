"""Release trust boundaries and real-file lifecycle recovery, with only OS/DB services doubled."""

import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

RELEASE = Path(__file__).resolve().parents[1] / "release"
sys.path.insert(0, str(RELEASE))
import common
import lifecycle


def manifest(version="v0.3.0"):
    return {
        "schema": 1,
        "platform": "debian13-native-v1",
        "version": version,
        "repository": "AviDhandhania/erp",
        "source_commit": "a" * 40,
        "frappe": {"ref": "v16.55.2", "commit": "b" * 40},
        "erpnext": {"ref": "v16.54.0", "commit": "c" * 40},
        "runtime": {
            "python": "3.14.9",
            "node": "24.22.2",
            "bench": "5.31.1",
            "uv": "0.13.7",
        },
        "archive": {"name": f"clothing-erp-{version}.tar.gz", "sha256": "d" * 64},
    }


class TestReleaseContract(unittest.TestCase):
    def test_stable_contract_accepts_exact_pins(self):
        self.assertEqual(common.validate_manifest(manifest())["version"], "v0.3.0")

    def test_rejects_unstable_tags_and_unsupported_components(self):
        for bad in ("main", "v0.3.0-rc1", "v00.3.0", "v0.3.0/../../etc"):
            with self.assertRaises(ValueError):
                common.version_tuple(bad)
        for key, value in (
            ("schema", 2),
            ("platform", "docker"),
            ("repository", "other/repo"),
        ):
            data = manifest()
            data[key] = value
            with self.assertRaises(ValueError):
                common.validate_manifest(data)
        data = manifest()
        data["erpnext"]["ref"] = "develop"
        with self.assertRaises(ValueError):
            common.validate_manifest(data)

    def test_catalog_never_installs_drafts_or_incomplete_releases(self):
        release = {
            "draft": False,
            "prerelease": False,
            "tag_name": "v0.3.0",
            "assets": [],
        }
        with patch.object(common, "fetch_json", return_value=release):
            with self.assertRaisesRegex(ValueError, "not ready"):
                common.release_assets()
        release["draft"] = True
        with patch.object(common, "fetch_json", return_value=release):
            with self.assertRaisesRegex(ValueError, "published stable"):
                common.release_assets()

    def test_archive_traversal_and_symlinks_are_rejected(self):
        for filename, link in (
            ("../../escaped", False),
            ("/absolute", False),
            ("normal", True),
        ):
            with tempfile.TemporaryDirectory() as directory:
                archive = Path(directory) / "archive.tar.gz"
                with tarfile.open(archive, "w:gz") as tar:
                    entry = tarfile.TarInfo(filename)
                    if link:
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = "/etc/passwd"
                    tar.addfile(entry)
                with self.assertRaises(ValueError):
                    common.extract_archive(archive, Path(directory) / "source")

    def test_corrupt_manifest_is_rejected_before_archive_download(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)

            def download(url, output):
                Path(output).write_text(
                    "{}"
                    if Path(output).name == "release.json"
                    else "0" * 64 + "  release.json\n"
                )

            with (
                patch.object(
                    common,
                    "release_assets",
                    return_value=(
                        "v0.3.0",
                        {
                            "release.json": "https://test/release.json",
                            "SHA256SUMS": "https://test/SHA256SUMS",
                        },
                    ),
                ),
                patch.object(common, "download", side_effect=download) as fetch,
            ):
                with self.assertRaisesRegex(ValueError, "manifest checksum"):
                    common.fetch_release(destination)
                self.assertEqual(fetch.call_count, 2)


class FakeManager(lifecycle.Manager):
    def __init__(self, root):
        super().__init__(Path(root) / "home", Path(root) / "state")
        self.events = []
        self.failure = None
        self.restored = False
        self.previous = self.home / "releases/v0.3.0/bench"
        (self.previous / "sites/clothing.local/public/files").mkdir(parents=True)
        (self.previous / "sites/clothing.local/private/files").mkdir(parents=True)
        (self.previous / "sites/common_site_config.json").write_text("{}")
        (self.previous / "sites/clothing.local/site_config.json").write_text(
            json.dumps({"db_name": "_" + "a" * 16, "encryption_key": "TEST-ONLY-KEY"})
        )
        (self.previous / "sites/clothing.local/private/files/test.txt").write_text(
            "TEST before update"
        )
        self.active.symlink_to(self.previous)
        self.state["current"] = {"bench": str(self.previous), "manifest": manifest()}
        self.save()

    def ensure_clean(self):
        self.events.append("clean")

    def run(self, command, **kwargs):
        self.events.append(tuple(map(str, command)))
        return subprocess.CompletedProcess(command, 0, stdout="")

    def stage(self, source, version):
        self.events.append("stage")
        if self.failure == "stage":
            raise RuntimeError("stage failed")
        target = self.releases / version / "bench"
        (target / "sites").mkdir(parents=True)
        return target

    def quiesce(self):
        self.events.append("stop")
        (self.directory / "maintenance").touch()

    def start_frontend(self):
        self.events.append("frontend")

    def start(self):
        self.events.append("start")

    def dump_database(self, name, path):
        self.events.append("backup")
        if self.failure == "backup":
            raise RuntimeError("backup failed")
        with gzip.open(path, "wb") as file:
            file.write(b"-- TEST database snapshot\n")

    def restore_database(self, name, path):
        self.events.append("restore")
        if self.failure == "restore":
            raise RuntimeError("restore failed")
        self.restored = True

    def configure_services(self, source):
        self.events.append("services")

    def bench(self, bench, *args, **kwargs):
        if args == ("migrate",):
            self.events.append("migrate")
            # Model an upgrade altering attachment data before its health result.
            (self.shared / "private/files/test.txt").write_text("TEST after migration")
            if self.failure in ("migrate", "restore"):
                raise RuntimeError("migration failed")

    def health(self, target, *, background=True):
        self.events.append("health")
        if (
            self.failure == "background"
            and background
            and Path(target) != self.previous
        ):
            raise RuntimeError("background failed")
        if self.failure == "health" and Path(target) != self.previous:
            raise RuntimeError("health failed")

    def deploy_manager(self, source):
        self.events.append("manager")


class TestUpdateRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = FakeManager(self.temp.name)
        self.source = Path(self.temp.name) / "source"
        self.source.mkdir()
        self.next = manifest("v0.3.1")

    def test_success_prepares_before_downtime_and_retains_recovery_point(self):
        m = self.manager
        m.update(self.next, self.source)
        self.assertLess(m.events.index("stage"), m.events.index("stop"))
        self.assertLess(m.events.index("backup"), m.events.index("migrate"))
        self.assertLess(m.events.index("health"), m.events.index("manager"))
        self.assertEqual(m.state["current"]["manifest"]["version"], "v0.3.1")
        self.assertTrue(Path(m.state["previous"]["backup"]).is_dir())
        self.assertFalse((m.directory / "maintenance").exists())
        self.assertEqual(m.active.resolve(), m.releases / "v0.3.1/bench")

    def test_failed_staging_never_stops_live_services(self):
        m = self.manager
        m.failure = "stage"
        with self.assertRaisesRegex(RuntimeError, "stage failed"):
            m.update(self.next, self.source)
        self.assertNotIn("stop", m.events)
        self.assertNotIn("migrate", m.events)

    def test_failed_backup_never_migrates_or_restores(self):
        m = self.manager
        m.failure = "backup"
        with self.assertRaisesRegex(RuntimeError, "backup failed"):
            m.update(self.next, self.source)
        self.assertNotIn("migrate", m.events)
        self.assertNotIn("restore", m.events)
        self.assertFalse((m.directory / "maintenance").exists())

    def test_failed_migration_restores_both_code_and_files(self):
        m = self.manager
        m.failure = "migrate"
        with self.assertRaisesRegex(RuntimeError, "migration failed"):
            m.update(self.next, self.source)
        self.assertTrue(m.restored)
        self.assertEqual(m.active.resolve(), m.previous)
        self.assertEqual(
            (m.shared / "private/files/test.txt").read_text(), "TEST before update"
        )
        self.assertIsNone(m.state["operation"])
        self.assertFalse((m.directory / "maintenance").exists())

    def test_failed_health_also_restores_database(self):
        m = self.manager
        m.failure = "health"
        with self.assertRaisesRegex(RuntimeError, "health failed"):
            m.update(self.next, self.source)
        self.assertTrue(m.restored)
        self.assertEqual(m.state["current"]["manifest"]["version"], "v0.3.0")

    def test_failed_restore_preserves_maintenance_and_durable_recovery_instructions(
        self,
    ):
        m = self.manager
        m.failure = "restore"
        with self.assertRaisesRegex(RuntimeError, "restore failed"):
            m.update(self.next, self.source)
        self.assertTrue((m.directory / "maintenance").exists())
        self.assertTrue(json.loads(m.file.read_text())["operation"]["backup"])
        m.failure = None
        m.recover()
        self.assertFalse((m.directory / "maintenance").exists())

    def test_app_only_cannot_change_upstream_versions(self):
        self.next["erpnext"]["ref"] = "v16.55.0"
        with self.assertRaisesRegex(RuntimeError, "App-only"):
            self.manager.update(self.next, self.source, app_only=True)
        self.assertNotIn("stage", self.manager.events)

    def test_schema_downgrade_is_rejected_before_staging(self):
        self.manager.state["current"]["manifest"]["erpnext"]["ref"] = "v16.55.0"
        with self.assertRaisesRegex(RuntimeError, "schema downgrade"):
            self.manager.update(self.next, self.source)
        self.assertNotIn("stage", self.manager.events)

    def test_mutable_upstream_tag_is_rejected(self):
        self.next["erpnext"]["commit"] = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "Immutable"):
            self.manager.update(self.next, self.source)

    def test_backup_tampering_is_rejected_before_restore(self):
        backup = self.manager.backup()
        (backup / "database.sql.gz").write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.manager.restore(backup)
        self.assertNotIn("restore", self.manager.events)

    def test_manual_rollback_saves_post_upgrade_writes_first(self):
        m = self.manager
        m.update(self.next, self.source)
        (m.shared / "private/files/test.txt").write_text("TEST new order attachment")
        m.rollback()
        self.assertEqual(m.state["current"]["manifest"]["version"], "v0.3.0")
        self.assertEqual(
            (m.shared / "private/files/test.txt").read_text(), "TEST before update"
        )
        redo = Path(m.state["previous"]["backup"])
        with tarfile.open(redo / "files.tar.gz") as archive:
            self.assertEqual(
                archive.extractfile("private/files/test.txt").read(),
                b"TEST new order attachment",
            )

    def test_operation_lock_rejects_concurrent_update(self):
        with self.manager.lock():
            with self.assertRaisesRegex(RuntimeError, "Another"):
                with self.manager.lock():
                    self.fail("must not acquire concurrent lock")


class TestServices(unittest.TestCase):
    def test_units_follow_active_symlink_and_have_graceful_shutdown(self):
        path = Path(__file__).resolve().parents[1] / "render-services.py"
        spec = importlib.util.spec_from_file_location("render_services", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            module.render(directory)
            units = list(Path(directory).glob("*.service"))
            self.assertEqual(len(units), 4)
            for unit in units:
                text = unit.read_text()
                self.assertIn("/home/frappe/frappe-bench", text)
                self.assertIn("TimeoutStopSec=300", text)
                self.assertNotIn("/home/frappe/releases/v", text)


class TestPostCommitRecovery(unittest.TestCase):
    setUp = TestUpdateRecovery.setUp

    def test_background_failure_preserves_new_database_and_retries_services(self):
        m = self.manager
        m.failure = "background"
        with self.assertRaisesRegex(RuntimeError, "background failed"):
            m.update(self.next, self.source)
        self.assertEqual(m.state["current"]["manifest"]["version"], "v0.3.1")
        self.assertEqual(m.state["operation"]["phase"], "post-commit")
        self.assertFalse(m.restored)
        self.assertTrue((m.directory / "maintenance").exists())
        m.failure = None
        m.recover()
        self.assertFalse((m.directory / "maintenance").exists())
        self.assertFalse(m.restored)


class TestReleaseBuilder(unittest.TestCase):
    def test_git_archive_excludes_untracked_credentials_and_is_reproducible(self):
        spec = importlib.util.spec_from_file_location(
            "release_build", RELEASE / "build.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            root.mkdir()
            (root / "clothing_erp").mkdir()
            (root / "deploy").mkdir()
            (root / "clothing_erp/__init__.py").write_text('__version__ = "0.3.0"\n')
            (root / "deploy/versions.env").write_text(
                "FRAPPE_REF=v16.55.2\nERPNEXT_REF=v16.54.0\nPYTHON_VERSION=3.14.9\nNODE_VERSION=24.22.2\nBENCH_VERSION=5.31.1\nUV_VERSION=0.13.7\n"
            )
            subprocess.run(
                ["git", "init", "-b", "main", str(root)],
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=TEST Builder",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "test release",
                ],
                check=True,
                capture_output=True,
            )
            (root / "site_config.json").write_text('{"password":"TEST NEVER PACKAGE"}')
            with (
                patch.object(module, "ROOT", root),
                patch.object(
                    module,
                    "resolve",
                    side_effect=lambda repo, tag: (
                        ("b" if repo == "frappe" else "c") * 40
                    ),
                ),
            ):
                first = module.build("v0.3.0", Path(directory) / "first")
                second = module.build("v0.3.0", Path(directory) / "second")
            self.assertEqual(first, second)
            with tarfile.open(
                Path(directory) / "first" / first["archive"]["name"]
            ) as source:
                self.assertNotIn("site_config.json", source.getnames())
                self.assertIn("clothing_erp/__init__.py", source.getnames())
            self.assertEqual(len(first["source_commit"]), 40)

    def test_annotated_core_tag_uses_peeled_commit(self):
        spec = importlib.util.spec_from_file_location(
            "release_build", RELEASE / "build.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = (
            f"{'a' * 40}\trefs/tags/v16.55.2\n{'b' * 40}\trefs/tags/v16.55.2^{{}}\n"
        )
        with patch.object(module.subprocess, "check_output", return_value=output):
            self.assertEqual(module.resolve("frappe", "v16.55.2"), "b" * 40)
