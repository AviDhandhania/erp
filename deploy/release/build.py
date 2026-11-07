#!/usr/bin/env python3
"""Build immutable source archive + resolved upstream commits + checksum manifest."""

import argparse
import gzip
import json
from pathlib import Path
import subprocess
from common import REPOSITORY, sha256, validate_manifest, version_tuple

ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def resolve(repo, tag):
    output = subprocess.check_output(
        [
            "git",
            "ls-remote",
            f"https://github.com/frappe/{repo}.git",
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
        text=True,
    )
    refs = dict(line.split()[::-1] for line in output.splitlines())
    value = refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")
    if not value:
        raise ValueError(f"Upstream tag not found: {repo} {tag}")
    return value


def build(version, output):
    version_tuple(version)
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Release build requires clean tracked source")
    actual = (ROOT / "clothing_erp/__init__.py").read_text().strip()
    if actual != f'__version__ = "{version[1:]}"':
        raise ValueError("Release version and clothing_erp/__init__.py must match")
    pins = dict(
        line.split("=", 1)
        for line in (ROOT / "deploy/versions.env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    name = f"clothing-erp-{version}.tar.gz"
    # git archive excludes every untracked site, credential, build and local environment.
    raw = subprocess.check_output(
        ["git", "-C", str(ROOT), "archive", "--format=tar", "HEAD"]
    )
    with (
        (output / name).open("wb") as target,
        gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as compressed,
    ):
        compressed.write(raw)
    manifest = {
        "schema": 1,
        "platform": "debian13-native-v1",
        "version": version,
        "repository": REPOSITORY,
        "source_commit": git("rev-parse", "HEAD"),
        "frappe": {
            "ref": pins["FRAPPE_REF"],
            "commit": resolve("frappe", pins["FRAPPE_REF"]),
        },
        "erpnext": {
            "ref": pins["ERPNEXT_REF"],
            "commit": resolve("erpnext", pins["ERPNEXT_REF"]),
        },
        "runtime": {
            key: pins[f"{key.upper()}_VERSION"]
            for key in ("python", "node", "bench", "uv")
        },
        "archive": {"name": name, "sha256": sha256(output / name)},
    }
    validate_manifest(manifest)
    (output / "release.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(output / entry)}  {entry}\n" for entry in ("release.json", name)
        )
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--output", default=str(ROOT / "dist/release"))
    args = parser.parse_args()
    print(json.dumps(build(args.version, args.output), indent=2))
