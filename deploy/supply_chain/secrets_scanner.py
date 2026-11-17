"""Secret scanner for repository files and git history."""

import os
import re
import subprocess
from pathlib import Path

# Patterns indicating potential secrets
SECRET_PATTERNS = [
    ("Private Key", re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")),
    ("GitHub Token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}")),
    ("GitHub Fine-Grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{82}")),
    ("AWS Access Key ID", re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}")),
    ("Generic High-Entropy Secret", re.compile(r"(?i)(?:api[_-]?key|secret[_-]?key|bearer|token)\s*[:=]\s*['\"]([A-Za-z0-9_-]{32,})['\"]")),
    ("Hardcoded Password", re.compile(r"(?i)(?:password|passwd|db_password)\s*[:=]\s*['\"]([^'\"]{8,})['\"]")),
]

# Patterns or paths known to be safe fixtures
SAFE_ALLOWLIST = [
    re.compile(r"test-only-ephemeral-password"),
    re.compile(r"test-only-admin"),
    re.compile(r"test-only-password"),
    re.compile(r"MARIADB_ROOT_PASSWORD"),
    re.compile(r"example\.invalid"),
    re.compile(r"test-only"),
    re.compile(r"dummy-secret"),
    re.compile(r"REPLACE_WITH_"),
    re.compile(r"openssl rand"),
    re.compile(r"\$\(.*?\b(?:openssl|rand|random|secrets)\b.*?\)"),
    re.compile(r'["\']\$(?:[A-Z0-9_]+)["\']'),
    re.compile(r"\$\{.*?\}"),
]

IGNORED_PATHS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "env",
    ".runtime",
    "dist",
    "target",
}


def is_allowlisted(line: str) -> bool:
    for pattern in SAFE_ALLOWLIST:
        if pattern.search(line):
            return True
    return False


def scan_text(text: str, source_label: str = "") -> list[dict]:
    findings = []
    lines = text.splitlines()
    for line_num, line in enumerate(lines, 1):
        if is_allowlisted(line):
            continue
        for name, pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                # Mask secret in report
                matched_str = match.group(0)
                masked = matched_str[:4] + "*" * (len(matched_str) - 8) + matched_str[-4:] if len(matched_str) > 8 else "***"
                findings.append({
                    "rule": name,
                    "source": source_label,
                    "line": line_num,
                    "snippet": line[:120].strip(),
                    "masked": masked,
                })
    return findings


def scan_files(root_dir: str | Path) -> list[dict]:
    root = Path(root_dir).resolve()
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_PATHS]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path.suffix in (".pyc", ".gz", ".tar", ".png", ".jpg", ".webp", ".so", ".db", ".rdb", ".fw"):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = file_path.relative_to(root)
                file_findings = scan_text(content, source_label=str(rel_path))
                findings.extend(file_findings)
            except Exception:
                pass
    return findings


def scan_git_history(repo_dir: str | Path, max_commits: int = 50) -> list[dict]:
    findings = []
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "log", f"-{max_commits}", "-p", "--full-history"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_commit = ""
        current_file = ""
        for line in proc.stdout.splitlines():
            if line.startswith("commit "):
                current_commit = line.split()[1][:10]
            elif line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("+") and not line.startswith("+++"):
                added_line = line[1:]
                if is_allowlisted(added_line):
                    continue
                for name, pattern in SECRET_PATTERNS:
                    match = pattern.search(added_line)
                    if match:
                        matched_str = match.group(0)
                        masked = matched_str[:4] + "***" + matched_str[-4:] if len(matched_str) > 8 else "***"
                        findings.append({
                            "rule": name,
                            "source": f"git:{current_commit}:{current_file}",
                            "line": 0,
                            "snippet": added_line[:120].strip(),
                            "masked": masked,
                        })
    except Exception as e:
        # Non-fatal if git is unavailable in a detached test harness
        findings.append({"rule": "Git Scan Note", "source": "git", "line": 0, "snippet": str(e), "masked": ""})
    return findings
