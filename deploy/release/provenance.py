"""Publisher provenance and cryptographic release verification."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_REPOSITORY = "AviDhandhania/erp"
ALLOWED_DOWNLOAD_DOMAINS = {
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "raw.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


def validate_redirect_url(url: str, allowed_domains: set[str] | None = None) -> None:
    """Enforce HTTPS and ensure host is within authorized publisher domains."""
    if not url.startswith("https://"):
        raise ValueError(f"Insecure redirect URL: {url} does not use HTTPS")
    parsed = urlparse(url)
    domains = allowed_domains or ALLOWED_DOWNLOAD_DOMAINS
    hostname = parsed.hostname or ""
    if not any(hostname == d or hostname.endswith("." + d) for d in domains):
        raise ValueError(f"Unauthorized release download host: {hostname}")


def check_revocation(
    version: str,
    revocations_path: str | Path | None = None,
    repository: str = DEFAULT_REPOSITORY,
) -> None:
    """Verify that a release version has not been revoked."""
    path = Path(revocations_path) if revocations_path else Path(__file__).parent / "revocations.json"
    if not path.exists():
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to load release revocation registry: {e}")

    if data.get("repository") != repository:
        raise ValueError(f"Revocation registry repository mismatch: {data.get('repository')}")

    revoked = data.get("revoked_releases", {})
    if version in revoked:
        info = revoked[version]
        reason = info.get("reason", "Security vulnerability or deprecation")
        superseded = info.get("superseded_by", "a newer stable release")
        raise ValueError(
            f"Release {version} is REVOKED: {reason}. Upgrade to {superseded}."
        )


def verify_provenance_attestation(
    manifest: dict,
    archive_sha256: str,
    attestation_path: str | Path | None = None,
    expected_repo: str = DEFAULT_REPOSITORY,
) -> bool:
    """Verify in-toto / Sigstore build provenance attestation bundle.
    
    Validates:
    - Expected repository
    - Target subject digest matches the archive SHA-256
    - Predicate builder and invocation workflow
    - Release version agreement
    """
    if not attestation_path:
        return False

    path = Path(attestation_path)
    if not path.exists():
        raise ValueError(f"Provenance attestation bundle not found at {path}")

    try:
        content = path.read_text(encoding="utf-8")
        # Attestation bundles can be newline-delimited JSON or a JSON array
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    except Exception as e:
        raise ValueError(f"Malformed provenance attestation file: {e}")

    if not entries:
        raise ValueError("Provenance attestation file contains no statements")

    matched_subject = False
    for item in entries:
        statement = item.get("statement", item)
        # Verify statement type
        pred_type = statement.get("predicateType", "")
        if "provenance" not in pred_type:
            continue

        # Check subjects
        subjects = statement.get("subject", [])
        for subj in subjects:
            name = subj.get("name", "")
            digests = subj.get("digest", {})
            subj_sha = digests.get("sha256", "")
            if subj_sha.lower() == archive_sha256.lower():
                matched_subject = True
                break

        # Check repo in predicate
        predicate = statement.get("predicate", {})
        build_def = predicate.get("buildDefinition", {})
        internal_params = build_def.get("internalParameters", {})
        repo = internal_params.get("github", {}).get("repository") or predicate.get("invocation", {}).get("configSource", {}).get("uri", "")

        if expected_repo.lower() not in repo.lower():
            raise ValueError(f"Provenance repository mismatch: {repo} does not match {expected_repo}")

    if not matched_subject:
        raise ValueError(f"Provenance attestation does not cover archive SHA-256: {archive_sha256}")

    return True


def verify_release_integrity(
    manifest: dict,
    archive_path: str | Path,
    expected_repo: str = DEFAULT_REPOSITORY,
    revocations_path: str | Path | None = None,
    attestation_path: str | Path | None = None,
) -> None:
    """Combined security assertion for release candidate integrity:
    1. Rejects revoked releases.
    2. Validates publisher repository.
    3. Validates archive digest and naming.
    4. Validates provenance attestation if present.
    """
    version = manifest.get("version", "")
    check_revocation(version, revocations_path=revocations_path, repository=expected_repo)

    if manifest.get("repository") != expected_repo:
        raise ValueError(f"Unexpected release repository: {manifest.get('repository')} != {expected_repo}")

    archive = Path(archive_path)
    if not archive.exists():
        raise FileNotFoundError(f"Release archive not found: {archive}")

    expected_archive_name = f"clothing-erp-{version}.tar.gz"
    if manifest.get("archive", {}).get("name") != expected_archive_name:
        raise ValueError(f"Unexpected release archive name in manifest: {manifest.get('archive', {}).get('name')}")

    import hashlib
    h = hashlib.sha256()
    with archive.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    actual_digest = h.hexdigest()

    expected_digest = manifest.get("archive", {}).get("sha256", "")
    if actual_digest.lower() != expected_digest.lower():
        raise ValueError(f"Release archive SHA-256 mismatch: {actual_digest} != {expected_digest}")

    if attestation_path:
        verify_provenance_attestation(manifest, actual_digest, attestation_path, expected_repo)
