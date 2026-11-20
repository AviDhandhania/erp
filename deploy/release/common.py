"""Release contract shared by the builder, installer and update manager (stdlib only)."""

import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import urllib.request
from urllib.parse import urlparse

REPOSITORY = "AviDhandhania/erp"
API = f"https://api.github.com/repos/{REPOSITORY}"
SEMVER = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA = re.compile(r"^[a-f0-9]{40}$")
REQUIRED_EXTENSION_PINS = {
    "insights": (r"v3\.[0-9]+\.[0-9]+", "v3.15.1", "Insights"),
    "india_compliance": (
        r"v16\.[0-9]+\.[0-9]+",
        "v16.10.0",
        "India Compliance",
    ),
}


def _github_token():
    """Return the optional read-only credential for the release repository."""
    return (
        os.environ.get("CLOTHING_ERP_GITHUB_TOKEN", "").strip()
        or os.environ.get("GITHUB_TOKEN", "").strip()
        or os.environ.get("GH_TOKEN", "").strip()
    )


def _request_headers(url, *, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "User-Agent": "clothing-erp-lifecycle",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _github_token()
    hostname = (urlparse(url).hostname or "").lower()
    if token and hostname in {
        "api.github.com",
        "github.com",
        "objects.githubusercontent.com",
        "github-releases.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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


def validate_manifest(data, *, allow_unlocked=False):
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
    for app, (pattern, minimum, label) in REQUIRED_EXTENSION_PINS.items():
        component = data.get(app, {})
        if not re.fullmatch(
            pattern, component.get("ref", "")
        ) or not SHA.fullmatch(component.get("commit", "")):
            raise ValueError(f"A pinned, supported {label} release is required")
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
    locks = data.get("locks", {})
    if not locks and allow_unlocked:
        return data
    for name in ("python.txt", "tools.txt"):
        entry = locks.get(name, {})
        if entry.get("path") != f"deploy/locks/{name}" or not re.fullmatch(
            r"[a-f0-9]{64}", entry.get("sha256", "")
        ):
            raise ValueError("Verified runtime dependency locks are required")
    return data


def verify_locks(source, manifest):
    source = Path(source)
    for name in ("python.txt", "tools.txt"):
        path = source / manifest["locks"][name]["path"]
        if sha256(path) != manifest["locks"][name]["sha256"]:
            raise ValueError(f"Dependency lock checksum mismatch: {name}")
        lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]

        def exact(line):
            return re.fullmatch(
                r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.!+-]+", line
            ) or re.fullmatch(
                r"[A-Za-z0-9_.-]+ @ git\+https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[a-f0-9]{40}",
                line,
            )

        invalid = next((line for line in lines if not exact(line)), None)
        if not lines or invalid is not None:
            raise ValueError(
                f"Dependency locks require exact versions or full Git commit pins: {name}: {invalid!r}"
            )


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers=_request_headers(url),
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def release_assets(tag=None):
    # Latest means a published, stable GitHub Release, never the main branch.
    try:
        release = fetch_json(
            f"{API}/releases/tags/{tag}" if tag else f"{API}/releases/latest"
        )
    except urllib.error.HTTPError as err:
        if err.code in (403, 404) and not _github_token():
            # Fallback for unauthenticated access to public repository releases:
            # Resolve the release tag via the public GitHub redirect
            req = urllib.request.Request(
                f"https://github.com/{REPOSITORY}/releases/tags/{tag}" if tag else f"https://github.com/{REPOSITORY}/releases/latest",
                headers={"User-Agent": "clothing-erp-lifecycle"},
            )
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                    return None
            opener = urllib.request.build_opener(NoRedirect)
            resolved_url = None
            try:
                with opener.open(req, timeout=30) as resp:
                    resolved_url = resp.url
            except urllib.error.HTTPError as redir_err:
                resolved_url = redir_err.headers.get("Location") or redir_err.url
            if not resolved_url or "/releases/tag/" not in resolved_url:
                raise
            resolved_tag = resolved_url.split("/releases/tag/")[-1].strip("/")
            version_tuple(resolved_tag)
            base = f"https://github.com/{REPOSITORY}/releases/download/{resolved_tag}"
            assets = {
                "release.json": f"{base}/release.json",
                "SHA256SUMS": f"{base}/SHA256SUMS",
                f"clothing-erp-{resolved_tag}.tar.gz": f"{base}/clothing-erp-{resolved_tag}.tar.gz",
            }
            return resolved_tag, assets
        raise

    if release["draft"] or release["prerelease"]:
        raise ValueError("Only published stable releases can be installed")
    version_tuple(release["tag_name"])
    if tag and release["tag_name"] != tag:
        raise ValueError("GitHub returned a different release")
    authenticated = bool(_github_token())
    assets = {
        asset["name"]: (
            asset["url"] if authenticated else asset["browser_download_url"]
        )
        for asset in release["assets"]
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
    # Assets may redirect to GitHub's release-asset CDN. Always require HTTPS and allowed domains.
    if not url.startswith("https://"):
        raise ValueError("Release assets must use HTTPS")
    try:
        from provenance import validate_redirect_url
        validate_redirect_url(url)
    except ImportError:
        pass
    with (
        urllib.request.urlopen(
            urllib.request.Request(
                url,
                headers=_request_headers(url, accept="application/octet-stream"),
            ),
            timeout=120,
        ) as source,
        Path(destination).open("wb") as output,
    ):
        if not source.url.startswith("https://"):
            raise ValueError("Insecure release redirect")
        try:
            from provenance import validate_redirect_url
            validate_redirect_url(source.url)
        except ImportError:
            pass
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
    try:
        from provenance import check_revocation
        check_revocation(manifest["version"])
    except ImportError:
        pass
    if manifest["version"] != version:
        raise ValueError("Manifest does not match the selected GitHub release")
    name = manifest["archive"]["name"]
    if checksums.get(name) != manifest["archive"]["sha256"]:
        raise ValueError("Archive checksum disagrees with manifest")
    download(assets[name], destination / name)
    if sha256(destination / name) != manifest["archive"]["sha256"]:
        raise ValueError("Release archive checksum mismatch")
    try:
        from provenance import verify_release_integrity
        verify_release_integrity(manifest, destination / name, expected_repo=REPOSITORY)
    except ImportError:
        pass
    extract_archive(destination / name, destination / "source")
    verify_locks(destination / "source", manifest)
    (destination / "source/release.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest, destination / "source"
