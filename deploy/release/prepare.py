#!/usr/bin/env python3
"""Called by the GitHub release form. No tag rewriting and no release from dirty source."""

import argparse
from pathlib import Path
import subprocess
from common import version_tuple

parser = argparse.ArgumentParser()
parser.add_argument("version")
parser.add_argument("--frappe", default="")
parser.add_argument("--erpnext", default="")
args = parser.parse_args()
version_tuple(args.version)
if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
    raise SystemExit("Release preparation requires a clean checkout")
path = Path("clothing_erp/__init__.py")
old = path.read_text().split('"')[1]
if version_tuple(args.version) < version_tuple("v" + old):
    raise SystemExit("Cannot release an older version")
path.write_text(f'__version__ = "{args.version[1:]}"\n')
pins = Path("deploy/versions.env")
text = pins.read_text()
import re

for name, value in (("FRAPPE", args.frappe), ("ERPNEXT", args.erpnext)):
    if value:
        if not re.fullmatch(r"v16\.[0-9]+\.[0-9]+", value):
            raise SystemExit("Only stable v16 upstream releases are supported")
        text = re.sub(rf"^{name}_REF=.*$", f"{name}_REF={value}", text, flags=re.M)
pins.write_text(text)
