#!/usr/bin/env python3
"""Called by the GitHub release form. No tag rewriting and no release from dirty source."""

import argparse
from pathlib import Path
import re
import subprocess
from common import version_tuple


VERSION_ASSIGNMENT = re.compile(
    r'^__version__\s*=\s*["\']([0-9]+\.[0-9]+\.[0-9]+)["\']\s*$', re.M
)


def replace_version(contents, version):
    match = VERSION_ASSIGNMENT.search(contents)
    if not match:
        raise ValueError("Clothing ERP __version__ is missing or invalid")
    updated, count = VERSION_ASSIGNMENT.subn(
        f'__version__ = "{version[1:]}"', contents, count=1
    )
    if count != 1:
        raise ValueError("Clothing ERP __version__ could not be updated")
    return match.group(1), updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--frappe", default="")
    parser.add_argument("--erpnext", default="")
    parser.add_argument("--insights", default="")
    parser.add_argument("--india-compliance", default="")
    args = parser.parse_args()
    version_tuple(args.version)
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise SystemExit("Release preparation requires a clean checkout")
    path = Path("clothing_erp/__init__.py")
    old, updated = replace_version(path.read_text(), args.version)
    if version_tuple(args.version) < version_tuple("v" + old):
        raise SystemExit("Cannot release an older version")
    path.write_text(updated)
    pins = Path("deploy/versions.env")
    text = pins.read_text()
    for name, value in (
        ("FRAPPE", args.frappe),
        ("ERPNEXT", args.erpnext),
        ("INSIGHTS", args.insights),
        ("INDIA_COMPLIANCE", args.india_compliance),
    ):
        if value:
            pattern = (
                r"v3\.[0-9]+\.[0-9]+"
                if name == "INSIGHTS"
                else r"v16\.[0-9]+\.[0-9]+"
            )
            if not re.fullmatch(pattern, value):
                raise SystemExit(
                    f"Only stable upstream releases are supported for {name}"
                )
            text = re.sub(
                rf"^{name}_REF=.*$", f"{name}_REF={value}", text, flags=re.M
            )
    pins.write_text(text)


if __name__ == "__main__":
    main()
