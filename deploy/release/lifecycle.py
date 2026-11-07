#!/usr/bin/env python3
"""Manage tested, independent native benches; preserve both database and file recovery points."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import gzip
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

from common import (
    extract_archive,
    fetch_release,
    sha256,
    validate_manifest,
    version_tuple,
)

SERVICES = [
    f"clothing-erp-{name}.service" for name in ("schedule", "worker", "socketio", "web")
]
HERE = Path(__file__).resolve().parent


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    with temporary.open("rb") as file:
        os.fsync(file.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Manager:
    def __init__(
        self,
        home=Path("/home/frappe"),
        state_dir=Path("/var/lib/clothing-erp"),
        database_socket=Path("/run/mysqld/mysqld.sock"),
        application_user="frappe",
        manage_queue=True,
    ):
        self.manage_queue = manage_queue
        self.database_socket = Path(database_socket)
        self.home = Path(home)
        self.active = self.home / "frappe-bench"
        self.releases = self.home / "releases"
        self.shared = self.home / "shared/clothing.local"
        self.directory = Path(state_dir)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o755)
        self.file = self.directory / "state.json"
        self.state = json.loads(self.file.read_text()) if self.file.exists() else {}
        self.uid = (
            pwd.getpwnam(application_user).pw_uid if os.geteuid() == 0 else os.getuid()
        )
        self.gid = (
            pwd.getpwnam(application_user).pw_gid if os.geteuid() == 0 else os.getgid()
        )

    def save(self):
        atomic_json(self.file, self.state)

    def run(self, command, *, bench=None, as_frappe=False, **kwargs):
        command = list(map(str, command))
        if bench:
            bench = Path(bench)
            runtime = bench / ".platform"
            env = os.environ | {
                "PATH": f"{runtime}/tools/bin:{runtime}/node/bin:{runtime}/bin:/usr/local/bin:/usr/bin:/bin",
                "FRAPPE_BENCH_ROOT": str(bench),
                "SITES_PATH": str(bench / "sites"),
            }
            command = [
                "env",
                *[
                    f"{k}={v}"
                    for k, v in env.items()
                    if k in ("PATH", "FRAPPE_BENCH_ROOT", "SITES_PATH")
                ],
                *command,
            ]
        if as_frappe:
            command = ["runuser", "-u", "frappe", "--", *command]
        return subprocess.run(command, cwd=bench, check=True, **kwargs)

    def bench(self, bench, *arguments, **kwargs):
        bench = Path(bench)
        tooling = bench / ".platform/tools/bin/bench"
        if not tooling.exists():  # Previous native installer layout.
            tooling = self.home / ".tooling/bin/bench"
        return self.run(
            [tooling, "--site", "clothing.local", *arguments],
            bench=bench,
            as_frappe=True,
            **kwargs,
        )

    @contextmanager
    def lock(self):
        with (self.directory / "operation.lock").open("w") as file:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    "Another install/update/backup operation is running"
                ) from None
            yield

    def installed(self):
        if not (self.active / "sites/clothing.local/site_config.json").exists():
            raise RuntimeError(
                "No supported production installation at /home/frappe/frappe-bench"
            )
        if not self.state.get("current"):
            manifest = self.active / ".clothing-release.json"
            self.state["current"] = {
                "bench": str(self.active.resolve()),
                "manifest": json.loads(manifest.read_text())
                if manifest.exists()
                else None,
            }
            self.save()
        return self.state["current"]

    def ensure_clean(self):
        for name in ("frappe", "erpnext", "clothing_erp"):
            result = self.run(
                ["git", "status", "--porcelain"],
                bench=self.active / "apps" / name,
                as_frappe=True,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                raise RuntimeError(
                    f"Local changes in {name}; preserve/commit them before updating"
                )

    def validate_site_paths(self):
        site = (self.active / "sites/clothing.local").resolve()
        if self.shared.is_symlink():
            raise RuntimeError("Shared site must be a real directory")
        if self.shared.exists() and site != self.shared:
            raise RuntimeError("Active site does not match managed shared data")
        for name in (
            "public",
            "private",
            "public/files",
            "private/files",
            "site_config.json",
        ):
            candidate = site / name
            if candidate.is_symlink() or (
                candidate.exists() and not candidate.resolve().is_relative_to(site)
            ):
                raise RuntimeError("Site data contains an unsupported symlink")
        return site

    def snapshot_config(self):
        self.validate_site_paths()
        return json.loads(
            (self.active / "sites/clothing.local/site_config.json").read_text()
        )

    def quiesce(self):
        # nginx returns 503 even while gunicorn is stopped; no new user writes enter.
        maintenance = self.directory / "maintenance"
        maintenance.touch(mode=0o644)
        maintenance.chmod(0o644)
        self.run(["systemctl", "stop", *SERVICES])

    def start_frontend(self):
        self.run(
            [
                "systemctl",
                "start",
                "clothing-erp-web.service",
                "clothing-erp-socketio.service",
            ]
        )

    def start(self):
        self.run(["systemctl", "start", *reversed(SERVICES)])

    def resume(self):
        (self.directory / "maintenance").unlink(missing_ok=True)

    def database_name(self, configuration):
        name = configuration["db_name"]
        # Installer-generated dedicated site DBs only; never select system or arbitrary databases.
        if not re.fullmatch(r"_[a-f0-9]{16}", name):
            raise RuntimeError(
                "Unsupported site database name; refusing privileged backup/restore"
            )
        return name

    def dump_database(self, name, path):
        with tempfile.TemporaryFile() as errors, path.open("wb") as target:
            process = subprocess.Popen(
                [
                    "mariadb-dump",
                    "--user=root",
                    f"--socket={self.database_socket}",
                    "--single-transaction",
                    "--quick",
                    "--routines",
                    "--events",
                    "--triggers",
                    "--hex-blob",
                    "--default-character-set=utf8mb4",
                    name,
                ],
                stdout=subprocess.PIPE,
                stderr=errors,
            )
            try:
                with gzip.GzipFile(fileobj=target, mode="wb") as output:
                    shutil.copyfileobj(process.stdout, output)
                if process.wait():
                    errors.seek(0)
                    raise RuntimeError(
                        "Database backup failed: "
                        + errors.read().decode(errors="replace")
                    )
            finally:
                process.stdout.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def dump_queue(self, path):
        # This platform dedicates one local Redis instance to this site. Preserve
        # pending jobs as well as DB state so failed migrations cannot leak jobs
        # requiring the abandoned code/schema into the restored old release.
        result = self.run(
            ["redis-cli", "--raw", "CONFIG", "GET", "appendonly"],
            capture_output=True,
            text=True,
        )
        if result.stdout.splitlines() != ["appendonly", "no"]:
            raise RuntimeError(
                "Queue recovery requires the managed Redis RDB configuration (appendonly=no)"
            )
        self.run(["redis-cli", "--rdb", path])

    def check_queue(self, path):
        self.run(["redis-check-rdb", path], capture_output=True, text=True)

    def restore_queue(self, path):
        # A previous interrupted restore may have stopped Redis. The active RDB
        # remains valid because replacement below is atomic. No app writer is running.
        self.run(["systemctl", "start", "redis-server"])
        # Fixed distribution-managed paths only; the app cannot supply a restore destination.
        for key, expected in (
            ("dir", "/var/lib/redis"),
            ("dbfilename", "dump.rdb"),
            ("appendonly", "no"),
        ):
            result = self.run(
                ["redis-cli", "--raw", "CONFIG", "GET", key],
                capture_output=True,
                text=True,
            )
            if result.stdout.splitlines() != [key, expected]:
                raise RuntimeError(
                    "Unexpected Redis persistence configuration; maintenance remains enabled"
                )
        self.run(["systemctl", "stop", "redis-server"])
        target = Path("/var/lib/redis/dump.rdb")
        temporary = target.with_name(".clothing-restore.rdb")
        shutil.copyfile(path, temporary)
        redis = pwd.getpwnam("redis")
        os.chown(temporary, redis.pw_uid, redis.pw_gid)
        temporary.chmod(0o600)
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        os.replace(temporary, target)
        descriptor = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.run(["systemctl", "start", "redis-server"])

    def backup(self):
        self.installed()
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.directory / "backups" / identifier
        backup.mkdir(parents=True, mode=0o700)
        configuration = self.snapshot_config()
        database = self.database_name(configuration)
        atomic_json(backup / "site_config.json", configuration)
        self.dump_database(database, backup / "database.sql.gz")
        site = self.active / "sites/clothing.local"
        with tarfile.open(backup / "files.tar.gz", "w:gz", dereference=False) as output:
            for directory in ("public/files", "private/files"):
                if (site / directory).exists():
                    # Attachments must not point outside their site.
                    for child in (site / directory).rglob("*"):
                        if child.is_symlink():
                            raise RuntimeError(
                                "File backup contains symlinks; use a storage-aware backup before updating"
                            )
                    output.add(site / directory, arcname=directory)
        artifacts = ["database.sql.gz", "files.tar.gz", "site_config.json"]
        if self.manage_queue:
            self.dump_queue(backup / "redis.rdb")
            self.check_queue(backup / "redis.rdb")
            artifacts.append("redis.rdb")
        for artifact in artifacts:
            with (backup / artifact).open("rb") as file:
                os.fsync(file.fileno())
        metadata = {
            "database": database,
            "created_at": identifier,
            "current": self.state["current"],
            "queue": self.manage_queue,
            "sha256": {name: sha256(backup / name) for name in artifacts},
        }
        atomic_json(backup / "backup.json", metadata)
        print(f"Recovery point: {backup}", flush=True)
        return backup

    def verify_backup(self, backup):
        backup = Path(backup).resolve()
        if not backup.is_relative_to((self.directory / "backups").resolve()):
            raise RuntimeError("Recovery point is outside the managed backup directory")
        metadata = json.loads((backup / "backup.json").read_text())
        configuration = json.loads((backup / "site_config.json").read_text())
        if self.database_name(configuration) != metadata["database"]:
            raise RuntimeError("Recovery database mismatch")
        artifacts = ["database.sql.gz", "files.tar.gz", "site_config.json"]
        if metadata.get("queue"):
            artifacts.append("redis.rdb")
        for name in artifacts:
            if sha256(backup / name) != metadata["sha256"][name]:
                raise RuntimeError(f"Recovery point checksum mismatch: {name}")
        if metadata.get("queue"):
            self.check_queue(backup / "redis.rdb")
        # Detect truncated/corrupt gzip before touching the live database.
        with gzip.open(backup / "database.sql.gz", "rb") as sql:
            while sql.read(1024 * 1024):
                pass
        with tempfile.TemporaryDirectory(dir=self.directory) as test:
            extract_archive(
                backup / "files.tar.gz", test, max_bytes=None, max_members=None
            )
        return metadata, configuration

    def restore_database(self, name, path):
        self.run(
            ["mariadb", "--user=root", f"--socket={self.database_socket}"],
            input=f"DROP DATABASE `{name}`; CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n",
            text=True,
        )
        # The existing site's DB-user grants survive a DROP/CREATE of that same database.
        with gzip.open(path, "rb") as source:
            process = subprocess.Popen(
                [
                    "mariadb",
                    "--user=root",
                    f"--socket={self.database_socket}",
                    "--default-character-set=utf8mb4",
                    name,
                ],
                stdin=subprocess.PIPE,
            )
            try:
                shutil.copyfileobj(source, process.stdin)
                process.stdin.close()
                if process.wait():
                    raise RuntimeError(
                        "Database restore failed; keep maintenance mode enabled"
                    )
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def restore(self, backup):
        backup = Path(backup)
        metadata, configuration = self.verify_backup(backup)
        # Preserve post-upgrade attachments as well; never delete a user's files to roll back.
        self.validate_site_paths()
        site = self.shared
        preserved = backup / (
            "displaced-files-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        for directory in ("public/files", "private/files"):
            if (site / directory).exists():
                (preserved / directory).parent.mkdir(
                    parents=True, exist_ok=True, mode=0o700
                )
                shutil.move(str(site / directory), preserved / directory)
        self.restore_database(metadata["database"], backup / "database.sql.gz")
        extract_archive(backup / "files.tar.gz", site, max_bytes=None, max_members=None)
        atomic_json(site / "site_config.json", configuration)
        if metadata.get("queue"):
            self.restore_queue(backup / "redis.rdb")
        for directory, dirs, files in os.walk(site):
            os.chown(directory, self.uid, self.gid)
            for name in dirs + files:
                os.chown(
                    Path(directory) / name, self.uid, self.gid, follow_symlinks=False
                )

    def adopt(self):
        """One-time conversion of the previous installer, without discarding its bench/data."""
        self.releases.mkdir(exist_ok=True, mode=0o755)
        os.chown(self.releases, self.uid, self.gid)
        if not self.active.is_symlink():
            parent = self.releases / (
                "legacy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            )
            parent.mkdir(mode=0o755)
            old = parent / "bench"
            self.state["current"]["bench"] = str(old)
            self.save()  # Record the destination before a potentially interrupted rename.
            self.active.rename(old)
            self.active.symlink_to(old)
        old = self.active.resolve()
        if not (old / ".platform").exists():
            platform = old / ".platform"
            platform.mkdir(mode=0o755, exist_ok=True)
            for name, target in (
                ("tools", self.home / ".tooling"),
                ("node", Path("/usr/local")),
                ("bin", self.home / ".local/bin"),
            ):
                if not (platform / name).exists():
                    (platform / name).symlink_to(target)
        self.shared.parent.mkdir(parents=True, exist_ok=True, mode=0o751)
        self.shared.parent.chmod(0o751)
        os.chown(
            self.shared.parent,
            0 if os.geteuid() == 0 else self.uid,
            0 if os.geteuid() == 0 else self.gid,
        )
        site = old / "sites/clothing.local"
        if not self.shared.exists():
            site.rename(self.shared)
            site.symlink_to(self.shared)
        if not site.is_symlink() or site.resolve() != self.shared:
            raise RuntimeError("Unexpected shared-site layout")
        self.save()
        return old

    def stage(self, source, version):
        if shutil.disk_usage(self.home).free < 5 * 1024**3:
            raise RuntimeError(
                "At least 5 GiB free is required for release staging; keep additional space for site backups"
            )
        destination = self.releases / version
        self.releases.mkdir(exist_ok=True, mode=0o755)
        os.chown(self.releases, self.uid, self.gid)
        if destination.exists():
            marker = destination / "bench/.stage-complete"
            if marker.exists() and json.loads(
                (destination / "bench/.clothing-release.json").read_text()
            ) == json.loads((source / "release.json").read_text()):
                for app in ("frappe", "erpnext", "clothing_erp"):
                    result = self.run(
                        ["git", "status", "--porcelain"],
                        bench=destination / "bench/apps" / app,
                        as_frappe=True,
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout.strip():
                        raise RuntimeError(
                            "Staged release has local changes; refusing to reuse it"
                        )
                return destination / "bench"
            referenced = {
                self.state.get(key, {}).get("bench") for key in ("current", "previous")
            }
            if str(destination / "bench") in referenced:
                raise RuntimeError(
                    "Incomplete release is referenced by a recovery point; inspect it before retrying"
                )
            destination.rename(
                destination.with_name(f"failed-{version}-{time.time_ns()}")
            )
        self.run(
            ["bash", source / "deploy/stage-release.sh", source, destination],
            as_frappe=True,
        )
        return destination / "bench"

    def configure_target(self, target, old):
        shutil.copy2(
            old / "sites/common_site_config.json",
            target / "sites/common_site_config.json",
        )
        os.chown(target / "sites/common_site_config.json", self.uid, self.gid)
        site = target / "sites/clothing.local"
        if site.is_symlink() and site.resolve() == self.shared:
            return
        if site.exists() or site.is_symlink():
            raise RuntimeError(
                "Target contains an unexpected site; refusing to overwrite it"
            )
        site.symlink_to(self.shared)

    def activate(self, target):
        temporary = self.active.with_name(".frappe-bench-next")
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(target)
        os.replace(temporary, self.active)

    def configure_services(self, source):
        self.run(
            [
                sys.executable,
                source / "deploy/render-services.py",
                "/etc/systemd/system",
            ]
        )
        shutil.copy2(
            source / "deploy/nginx.conf", "/etc/nginx/sites-available/clothing-erp"
        )
        self.run(["nginx", "-t"])
        self.run(["systemctl", "daemon-reload"])
        self.run(["systemctl", "reload", "nginx"])

    def health(self, target, *, background=True):
        result = self.bench(
            target, "list-apps", "--format", "json", capture_output=True, text=True
        )
        if not {"frappe", "erpnext", "clothing_erp"}.issubset(
            json.loads(result.stdout).get("clothing.local", [])
        ):
            raise RuntimeError("The database is missing an expected installed app")
        for attempt in range(30):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:8000/api/method/ping", timeout=3
                ) as response:
                    if json.load(response).get("message") == "pong":
                        services = (
                            SERVICES
                            if background
                            else [
                                "clothing-erp-web.service",
                                "clothing-erp-socketio.service",
                            ]
                        )
                        self.run(["systemctl", "is-active", "--quiet", *services])
                        return
            except (OSError, ValueError, subprocess.CalledProcessError):
                time.sleep(2)
        raise RuntimeError("Post-update health check failed")

    def deploy_manager(self, source):
        destination = Path("/opt/clothing-erp/manager")
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("common.py", "lifecycle.py"):
            shutil.copy2(source / "deploy/release" / name, destination / name)
            (destination / name).chmod(0o644)

    def update(self, manifest, source, *, app_only=False):
        current = self.installed()
        if self.state.get("operation"):
            raise RuntimeError(
                "An interrupted update exists. Run clothing-erp recover --yes"
            )
        validate_manifest(manifest)
        previous_manifest = current.get("manifest")
        if previous_manifest:
            old_version = version_tuple(previous_manifest["version"])
            new_version = version_tuple(manifest["version"])
            if new_version == old_version:
                print("Already up to date")
                return
            if new_version < old_version:
                raise RuntimeError(
                    "Use rollback --yes to restore an older release with its data"
                )
            for app in ("frappe", "erpnext"):
                if version_tuple(manifest[app]["ref"]) < version_tuple(
                    previous_manifest[app]["ref"]
                ):
                    raise RuntimeError(
                        f"Refusing a {app} schema downgrade; use rollback with its recovery point"
                    )
                if (
                    manifest[app]["ref"] == previous_manifest[app]["ref"]
                    and manifest[app]["commit"] != previous_manifest[app]["commit"]
                ):
                    raise RuntimeError(f"Immutable {app} tag changed its commit")
            for runtime in ("python", "node", "bench", "uv"):
                if version_tuple("v" + manifest["runtime"][runtime]) < version_tuple(
                    "v" + previous_manifest["runtime"][runtime]
                ):
                    raise RuntimeError(f"Refusing runtime downgrade: {runtime}")
            if app_only and any(
                manifest[key] != previous_manifest[key]
                for key in ("frappe", "erpnext", "runtime")
            ):
                raise RuntimeError(
                    "App-only update would change upstream/runtime pins; run a full update"
                )
        elif app_only:
            raise RuntimeError(
                "First update must adopt the complete managed release contract"
            )
        else:
            for app in ("frappe", "erpnext"):
                result = self.run(
                    ["git", "describe", "--tags", "--exact-match", "HEAD"],
                    bench=self.active / "apps" / app,
                    as_frappe=True,
                    capture_output=True,
                    text=True,
                )
                if not re.fullmatch(
                    r"v16\.[0-9]+\.[0-9]+", result.stdout.strip()
                ) or version_tuple(result.stdout.strip()) > version_tuple(
                    manifest[app]["ref"]
                ):
                    raise RuntimeError(
                        "Legacy installation has unsupported/newer upstream code; refusing a schema downgrade"
                    )
        self.ensure_clean()
        print(
            f"Preparing {manifest['version']} while the existing site stays online",
            flush=True,
        )
        target = self.stage(source, manifest["version"])
        self.state["operation"] = {
            "phase": "prepared",
            "old": current,
            "target": str(target),
            "backup": None,
            "migrating": False,
        }
        self.save()
        try:
            self.quiesce()
            backup = self.backup()
            self.state["operation"]["backup"] = str(backup)
            self.save()
            old = self.adopt()
            self.state["operation"]["old"] = dict(self.state["current"])
            self.configure_target(target, old)
            self.configure_services(source)
            self.state["operation"]["phase"] = "migrating"
            self.state["operation"]["migrating"] = True
            self.save()
            self.bench(target, "migrate")
            self.activate(target)
            self.start_frontend()
            self.health(target, background=False)
            self.deploy_manager(source)
            self.state["previous"] = {
                **self.state["operation"]["old"],
                "backup": str(backup),
            }
            self.state["current"] = {"bench": str(target), "manifest": manifest}
            # Commit before releasing background writers. Beyond this boundary a
            # recovery retries the new services; it never silently discards new job writes.
            self.state["operation"]["phase"] = "post-commit"
            self.save()
            self.start()
            self.health(target)
            self.state["operation"] = None
            self.save()
            self.resume()
            print(
                f"Updated all components to release {manifest['version']}", flush=True
            )
        except BaseException:
            print(
                "Update interrupted. Applying the recorded recovery phase.",
                file=sys.stderr,
                flush=True,
            )
            self.recover()
            raise

    def recover(self):
        operation = self.state.get("operation")
        if not operation:
            raise RuntimeError("No interrupted update to recover")
        self.quiesce()
        if operation["phase"] == "post-commit":
            self.start()
            self.health(Path(self.state["current"]["bench"]))
            self.state["operation"] = None
            self.save()
            self.resume()
            print("Activated release services recovered", flush=True)
            return
        old = Path(operation["old"]["bench"])
        # Adoption may have been interrupted after moving the legacy directory.
        if not old.exists() and self.active.exists():
            old = self.active.resolve()
            operation["old"]["bench"] = str(old)
        if operation["migrating"]:
            if not operation.get("backup"):
                raise RuntimeError(
                    "Missing recovery point; maintenance remains enabled"
                )
            self.restore(Path(operation["backup"]))
        if not self.active.exists() or self.active.is_symlink():
            self.activate(old)
        self.start()
        self.health(old)
        self.state["current"] = operation["old"]
        self.state["operation"] = None
        self.save()
        self.resume()
        print("Previous release restored", flush=True)

    def rollback(self):
        if (
            self.state.get("operation")
            and self.state["operation"]["phase"] != "post-commit"
        ):
            raise RuntimeError("Run recover --yes for the interrupted update first")
        previous = self.state.get("previous")
        if not previous:
            raise RuntimeError("No previous managed release/recovery point")
        self.verify_backup(previous["backup"])
        self.quiesce()
        # Retain all writes made since the last upgrade before restoring old data.
        try:
            safety = self.backup()
        except BaseException:
            self.start()
            self.resume()
            raise
        current = self.state["current"]
        self.state["operation"] = {
            "phase": "rollback",
            "old": {k: previous[k] for k in ("bench", "manifest")},
            "target": current["bench"],
            "backup": previous["backup"],
            "migrating": True,
        }
        self.save()
        self.recover()
        self.state["previous"] = {**current, "backup": str(safety)}
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    for command in ("check", "update"):
        sub = commands.add_parser(command)
        sub.add_argument("--version")
        if command == "update":
            sub.add_argument("--app-only", action="store_true")
    commands.add_parser("backup")
    for command in ("recover", "rollback"):
        commands.add_parser(command).add_argument(
            "--yes", action="store_true", required=True
        )
    commands.add_parser("register")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run this command as root inside the Clothing ERP LXC")
    os.umask(0o077)
    manager = Manager()
    with manager.lock():
        manager.installed()
        if args.command in ("status", "register"):
            current = manager.state["current"].get("manifest")
            print(
                f"Clothing ERP: {current['version'] if current else 'legacy (no release manifest)'}"
            )
            if current:
                print(
                    f"ERPNext: {current['erpnext']['ref']} | Frappe: {current['frappe']['ref']}"
                )
                print(
                    f"Python: {current['runtime']['python']} | Node: {current['runtime']['node']} | Bench: {current['runtime']['bench']}"
                )
            print(f"Active bench: {manager.active.resolve()}")
            print(
                f"Previous recovery point: {manager.state.get('previous', {}).get('backup', 'none yet')}"
            )
            if manager.state.get("operation"):
                print(
                    f"Interrupted operation: {manager.state['operation']['phase']} — run clothing-erp recover --yes"
                )
        elif args.command == "backup":
            if manager.state.get("operation"):
                raise RuntimeError(
                    "Interrupted operation exists; run recover --yes before taking another backup"
                )
            manager.quiesce()
            try:
                manager.backup()
            finally:
                manager.start()
                manager.resume()
        elif args.command in ("recover", "rollback"):
            getattr(manager, args.command)()
        else:
            with tempfile.TemporaryDirectory(prefix="clothing-release-") as directory:
                Path(directory).chmod(0o755)
                manifest, source = fetch_release(directory, args.version)
                source.chmod(0o755)
                (source / "release.json").chmod(0o644)
                if args.command == "check":
                    installed = manager.state["current"].get("manifest")
                    print(
                        f"Installed: {installed['version'] if installed else 'legacy'}"
                    )
                    print(f"Available: {manifest['version']} (verified stable release)")
                    print(
                        f"ERPNext {manifest['erpnext']['ref']} | Frappe {manifest['frappe']['ref']}"
                    )
                    print("Update with: clothing-erp update")
                else:
                    manager.update(manifest, source, app_only=args.app_only)


if __name__ == "__main__":

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
