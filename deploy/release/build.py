#!/usr/bin/env python3
"""Build immutable source archive + resolved upstream commits + checksum manifest."""

import argparse
import gzip
import io
import tarfile
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


def build(version, output, *, locks=None, resolve_for_ci=False):
    version_tuple(version)
    if locks is None and not resolve_for_ci:
        raise ValueError(
            "Published releases require dependency locks from the passing CI build"
        )
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
    lock_metadata = {}
    if locks is not None:
        buffer = io.BytesIO(raw)
        with tarfile.open(fileobj=buffer, mode="a") as archive:
            existing = set(archive.getnames())
            for filename in ("python.txt", "tools.txt"):
                path = Path(locks) / filename
                relative = f"deploy/locks/{filename}"
                if relative in existing:
                    raise ValueError(
                        "Dependency locks are CI artifacts, not tracked source files"
                    )
                contents = path.read_bytes()
                entry = tarfile.TarInfo(relative)
                entry.size = len(contents)
                entry.mode = 0o644
                entry.mtime = 0
                archive.addfile(entry, io.BytesIO(contents))
                lock_metadata[filename] = {"path": relative, "sha256": sha256(path)}
        raw = buffer.getvalue()
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
        "locks": lock_metadata,
    }
    validate_manifest(manifest, allow_unlocked=resolve_for_ci)
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
    parser.add_argument("--locks", type=Path)
    parser.add_argument("--resolve-for-ci", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.version,
                args.output,
                locks=args.locks,
                resolve_for_ci=args.resolve_for_ci,
            ),
            indent=2,
        )
    )
