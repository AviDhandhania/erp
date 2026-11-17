"""Dependency and SCA scanner for Python, JavaScript and mobile dependencies."""

import json
import re
from pathlib import Path

# Known vulnerability advisory patterns or deprecated packages
KNOWN_VULNERABLE_PACKAGES = {
    # Examples of high-risk deprecated packages
    "pycrypto": "Deprecated and unmaintained. Replaced by cryptography / pycryptodome.",
    "urllib3": {
        "range": "<1.26.18",
        "description": "CVE-2023-45803: Request body leak on redirect",
    },
    "requests": {
        "range": "<2.31.0",
        "description": "CVE-2023-32681: Unintended leak of Proxy-Authorization header",
    },
    "cryptography": {
        "range": "<41.0.6",
        "description": "CVE-2023-49083: Memory corruption in PKCS7 decoding",
    },
    "jinja2": {
        "range": "<3.1.3",
        "description": "CVE-2024-22195: XSS vulnerability on compiler",
    },
    "aiohttp": {
        "range": "<3.9.0",
        "description": "CVE-2023-49081: HTTP request smuggling",
    },
    "werkzeug": {
        "range": "<3.0.3",
        "description": "CVE-2024-34069: Remote code execution in interactive debugger",
    },
}


def parse_semver(ver_str: str) -> tuple[int, ...]:
    clean = re.sub(r"[^0-9.]", "", ver_str.split("+")[0].split("-")[0])
    parts = clean.split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def is_version_vulnerable(version_str: str, rule: str) -> bool:
    try:
        ver = parse_semver(version_str)
        if rule.startswith("<"):
            target = parse_semver(rule[1:].strip())
            return ver < target
        elif rule.startswith("<="):
            target = parse_semver(rule[2:].strip())
            return ver <= target
        elif rule.startswith("=="):
            target = parse_semver(rule[2:].strip())
            return ver == target
    except Exception:
        pass
    return False


def scan_python_lockfile(lockfile_path: str | Path) -> list[dict]:
    findings = []
    path = Path(lockfile_path)
    if not path.exists():
        return findings

    lines = path.read_text().splitlines()
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Check for unpinned/range dependencies
        if any(op in line for op in (">=", "<=", "~=", ">", "<", "*")) and "==" not in line and "@" not in line:
            findings.append({
                "severity": "HIGH",
                "type": "UNPINNED_DEPENDENCY",
                "package": line,
                "file": str(path),
                "line": line_num,
                "message": f"Dependency line is not an exact pin: {line}",
            })
            continue

        if "==" in line:
            pkg, ver = line.split("==", 1)
            pkg = pkg.strip().lower()
            ver = ver.strip()

            if pkg in KNOWN_VULNERABLE_PACKAGES:
                adv = KNOWN_VULNERABLE_PACKAGES[pkg]
                if isinstance(adv, str):
                    findings.append({
                        "severity": "CRITICAL",
                        "type": "KNOWN_VULNERABILITY",
                        "package": pkg,
                        "version": ver,
                        "file": str(path),
                        "line": line_num,
                        "message": adv,
                    })
                elif isinstance(adv, dict):
                    if is_version_vulnerable(ver, adv["range"]):
                        findings.append({
                            "severity": "HIGH",
                            "type": "KNOWN_VULNERABILITY",
                            "package": pkg,
                            "version": ver,
                            "file": str(path),
                            "line": line_num,
                            "message": f"{adv['description']} (Affects {adv['range']})",
                        })

    return findings


def scan_node_dependencies(package_json_path: str | Path) -> list[dict]:
    findings = []
    path = Path(package_json_path)
    if not path.exists():
        return findings

    try:
        data = json.loads(path.read_text())
        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        for pkg, ver in all_deps.items():
            # Check for unsafe range prefixes
            if any(ver.startswith(prefix) for prefix in ("^", "~", ">", "*")):
                findings.append({
                    "severity": "MEDIUM",
                    "type": "FLOATING_NODE_DEPENDENCY",
                    "package": pkg,
                    "version": ver,
                    "file": str(path),
                    "message": f"Node dependency {pkg} has floating version range {ver}",
                })
    except Exception as e:
        findings.append({
            "severity": "LOW",
            "type": "PARSE_ERROR",
            "package": str(path),
            "version": "",
            "file": str(path),
            "message": str(e),
        })
    return findings


def scan_mobile_dependencies(mobile_dir: str | Path) -> list[dict]:
    """Scan mobile app build configurations (Gradle, Podfile, pubspec)."""
    findings = []
    root = Path(mobile_dir)
    if not root.exists():
        return findings

    for build_file in root.rglob("build.gradle"):
        content = build_file.read_text(errors="ignore")
        if "http://" in content and "maven" in content:
            findings.append({
                "severity": "HIGH",
                "type": "INSECURE_REPOSITORY_URL",
                "package": "gradle",
                "file": str(build_file),
                "message": "Gradle build file references insecure plaintext http:// repository",
            })

    for podfile in root.rglob("Podfile"):
        content = podfile.read_text(errors="ignore")
        if "http://" in content:
            findings.append({
                "severity": "HIGH",
                "type": "INSECURE_POD_SOURCE",
                "package": "cocoapods",
                "file": str(podfile),
                "message": "Podfile references insecure plaintext http:// source",
            })

    return findings
