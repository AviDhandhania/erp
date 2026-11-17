"""Unified runner for supply chain, secret scanning, license auditing and SAST."""

import argparse
import json
import sys
from pathlib import Path

# Support running directly or as module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from supply_chain.secrets_scanner import scan_files, scan_git_history
    from supply_chain.license_scanner import scan_lockfile
    from supply_chain.dependency_scanner import scan_python_lockfile
    from supply_chain.sast import run_sast_scan
    from supply_chain.sbom import write_sboms
else:
    from .secrets_scanner import scan_files, scan_git_history
    from .license_scanner import scan_lockfile
    from .dependency_scanner import scan_python_lockfile
    from .sast import run_sast_scan
    from .sbom import write_sboms


def run_all_scans(repo_root: Path, output_dir: Path | None = None) -> dict:
    results = {
        "secrets": scan_files(repo_root),
        "git_secrets": scan_git_history(repo_root, max_commits=25),
        "sast": run_sast_scan(repo_root),
        "licenses": [],
        "dependencies": [],
    }

    lock_file = repo_root / "deploy/locks/python.txt"
    if lock_file.exists():
        results["licenses"] = scan_lockfile(lock_file)
        results["dependencies"] = scan_python_lockfile(lock_file)

    if output_dir:
        write_sboms(repo_root, output_dir)
        (output_dir / "security-scan-report.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )

    return results


def main():
    parser = argparse.ArgumentParser(description="Run Clothing ERP Security & Supply Chain Checks")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--out", default=None, help="Output directory for SBOM and scan report")
    parser.add_argument("--strict", action="store_true", help="Fail if critical findings are detected")

    args = parser.parse_args()
    repo_path = Path(args.repo).resolve()
    out_path = Path(args.out).resolve() if args.out else None

    print(f"Running Supply Chain & Security Scans on {repo_path}...")
    report = run_all_scans(repo_path, out_path)

    secret_count = len(report["secrets"])
    git_secret_count = len([f for f in report["git_secrets"] if f.get("rule") != "Git Scan Note"])
    sast_count = len([f for f in report["sast"] if f["severity"] in ("HIGH", "CRITICAL")])
    dep_count = len([f for f in report["dependencies"] if f["severity"] in ("HIGH", "CRITICAL")])
    prohibited_licenses = len([f for f in report["licenses"] if f.get("status") == "PROHIBITED"])

    print(f"Secret Scanner findings: {secret_count} (Git history: {git_secret_count})")
    print(f"SAST high/critical findings: {sast_count}")
    print(f"Dependency high/critical findings: {dep_count}")
    print(f"Prohibited licenses: {prohibited_licenses}")

    if out_path:
        print(f"SBOM and report generated in {out_path}")

    if args.strict and (secret_count > 0 or git_secret_count > 0 or sast_count > 0 or dep_count > 0 or prohibited_licenses > 0):
        print("ERROR: Strict mode failed due to security findings.", file=sys.stderr)
        sys.exit(1)

    print("All security and supply-chain checks passed.")


if __name__ == "__main__":
    main()
