#!/usr/bin/env python3
"""Exercise real SQL/config/attachment backup and restore using an isolated TEST database.
Requires a local MariaDB admin socket. Never selects or changes an existing application DB.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "release"))
from lifecycle import Manager


def run(socket):
    os.umask(0o077)
    name = "_" + uuid.uuid4().hex[:16]
    created = False
    command = [
        "mariadb",
        "--user=root",
        f"--socket={socket}",
        "--batch",
        "--skip-column-names",
    ]
    with tempfile.TemporaryDirectory(prefix="clothing-recovery-test-") as directory:
        home = Path(directory) / "home"
        site = home / "shared/clothing.local"
        (site / "private/files").mkdir(parents=True)
        (site / "public/files").mkdir(parents=True)
        (home / "frappe-bench/sites").mkdir(parents=True)
        (home / "frappe-bench/sites/clothing.local").symlink_to(site)
        (site / "site_config.json").write_text(
            json.dumps({"db_name": name, "encryption_key": "TEST-ENCRYPTION-KEY"})
        )
        (site / "private/files/test.txt").write_text("TEST before update")
        manager = Manager(
            home,
            Path(directory) / "state",
            database_socket=socket,
            application_user="root" if os.geteuid() == 0 else "frappe",
        )
        manager.state["current"] = {
            "bench": str(home / "frappe-bench"),
            "manifest": None,
        }
        manager.save()
        try:
            subprocess.run(
                command, input=f"CREATE DATABASE `{name}`;", text=True, check=True
            )
            created = True
            subprocess.run(
                [*command, name],
                input="CREATE TABLE test_rows (id INT PRIMARY KEY, note VARCHAR(80)); INSERT INTO test_rows VALUES (1,'TEST before update');",
                text=True,
                check=True,
            )
            backup = manager.backup()
            subprocess.run(
                [*command, name],
                input="UPDATE test_rows SET note='TEST after update'; CREATE TABLE test_new_table (id INT);",
                text=True,
                check=True,
            )
            (site / "private/files/test.txt").write_text("TEST after update")
            manager.restore(backup)
            result = subprocess.check_output(
                [*command, name, "-e", "SELECT note FROM test_rows;"], text=True
            ).strip()
            assert result == "TEST before update", result
            result = subprocess.check_output(
                [*command, name, "-e", "SHOW TABLES LIKE 'test_new_table';"], text=True
            ).strip()
            assert result == "", "Post-upgrade table survived schema restoration"
            assert (site / "private/files/test.txt").read_text() == "TEST before update"
            assert (
                json.loads((site / "site_config.json").read_text())["encryption_key"]
                == "TEST-ENCRYPTION-KEY"
            )
            # Current data is retained in a displaced-files snapshot for manual recovery.
            assert list(backup.glob("displaced-files-*/private/files/test.txt"))
            print(
                "PASS: native MariaDB schema/data + attachment + encryption-key recovery"
            )
        finally:
            if created:
                subprocess.run(
                    command, input=f"DROP DATABASE `{name}`;", text=True, check=True
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True, type=Path)
    run(parser.parse_args().socket)
