"""Release contract shared by the builder, installer and update manager (stdlib only)."""

import hashlib
import json
from pathlib import Path
import re
import tarfile
import urllib.request

REPOSITORY = "AviDhandhania/erp"
API = f"https://api.github.com/repos/{REPOSITORY}"
SEMVER = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA = re.compile(r"^[a-f0-9]{40}$")


def version_tuple(value):
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError("Release must be a stable vMAJOR.MINOR.PATCH tag")
    return tuple(map(int, match.groups()))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(data):
    if data.get("schema") != 1 or data.get("platform") != "debian13-native-v1":
        raise ValueError("Unsupported release platform/schema")
    version_tuple(data["version"])
    if data.get("repository") != REPOSITORY or not SHA.fullmatch(
        data.get("source_commit", "")
    ):
        raise ValueError("Invalid Clothing ERP provenance")
    for app in ("frappe", "erpnext"):
        component = data[app]
        if not re.fullmatch(
            r"v16\.[0-9]+\.[0-9]+", component["ref"]
        ) or not SHA.fullmatch(component["commit"]):
            raise ValueError(f"Invalid or unsupported {app} pin")
        minimum = "v16.55.2" if app == "frappe" else "v16.54.0"
        if version_tuple(component["ref"]) < version_tuple(minimum):
            raise ValueError(f"{app} pin is older than the supported baseline")
    for key in ("python", "node", "bench", "uv"):
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", data["runtime"][key]):
            raise ValueError(f"Invalid {key} pin")
    if not data["runtime"]["python"].startswith("3.14."):
        raise ValueError("This platform supports Python 3.14")
    if not data["runtime"]["node"].startswith("24."):
        raise ValueError("This platform supports Node 24 LTS")
    if data["archive"]["name"] != f"clothing-erp-{data['version']}.tar.gz":
        raise ValueError("Unexpected release archive name")
    if not re.fullmatch(r"[a-f0-9]{64}", data["archive"]["sha256"]):
        raise ValueError("Missing archive checksum")
    return data


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "clothing-erp-lifecycle",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def release_assets(tag=None):
    # Latest means a published, stable GitHub Release, never the main branch.
    release = fetch_json(
        f"{API}/releases/tags/{tag}" if tag else f"{API}/releases/latest"
    )
    if release["draft"] or release["prerelease"]:
        raise ValueError("Only published stable releases can be installed")
    version_tuple(release["tag_name"])
    if tag and release["tag_name"] != tag:
        raise ValueError("GitHub returned a different release")
    assets = {
        asset["name"]: asset["browser_download_url"] for asset in release["assets"]
    }
    for name in (
        "release.json",
        "SHA256SUMS",
        f"clothing-erp-{release['tag_name']}.tar.gz",
    ):
        if name not in assets:
            raise ValueError(
                f"Release {release['tag_name']} is not ready: missing {name}"
            )
    return release["tag_name"], assets


def download(url, destination):
    # Assets may redirect to GitHub's release-asset CDN. Always require HTTPS.
    if not url.startswith("https://"):
        raise ValueError("Release assets must use HTTPS")
    with (
        urllib.request.urlopen(
            urllib.request.Request(
                url, headers={"User-Agent": "clothing-erp-lifecycle"}
            ),
            timeout=120,
        ) as source,
        Path(destination).open("wb") as output,
    ):
        if not source.url.startswith("https://"):
            raise ValueError("Insecure release redirect")
        while chunk := source.read(1024 * 1024):
            output.write(chunk)


def extract_archive(
    archive, destination, *, max_bytes=512 * 1024 * 1024, max_members=100000
):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if (max_members is not None and len(members) > max_members) or (
            max_bytes is not None and sum(m.size for m in members) > max_bytes
        ):
            raise ValueError("Release archive is unexpectedly large")
        for member in members:
            path = Path(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("Unsafe release archive member")
        source.extractall(destination, members=members, filter="data")


def fetch_release(destination, tag=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    version, assets = release_assets(tag)
    for name in ("release.json", "SHA256SUMS"):
        download(assets[name], destination / name)
    checksums = {}
    for line in (destination / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.strip().lstrip("*")
        if (
            Path(name).name != name
            or name in checksums
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("Malformed release checksums")
        checksums[name] = digest
    if checksums.get("release.json") != sha256(destination / "release.json"):
        raise ValueError("Release manifest checksum mismatch")
    manifest = validate_manifest(json.loads((destination / "release.json").read_text()))
    if manifest["version"] != version:
        raise ValueError("Manifest does not match the selected GitHub release")
    name = manifest["archive"]["name"]
    if checksums.get(name) != manifest["archive"]["sha256"]:
        raise ValueError("Archive checksum disagrees with manifest")
    download(assets[name], destination / name)
    if sha256(destination / name) != manifest["archive"]["sha256"]:
        raise ValueError("Release archive checksum mismatch")
    extract_archive(destination / name, destination / "source")
    (destination / "source/release.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest, destination / "source"
