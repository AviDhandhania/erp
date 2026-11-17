#!/usr/bin/env bash
# The bootstrap code is small; all deployed application code comes from a verified stable release.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run on a Proxmox host as root.' >&2; exit 1; }
command -v pct >/dev/null || { echo 'Proxmox VE is required.' >&2; exit 1; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
if ! command -v git >/dev/null; then apt-get update; apt-get install -y git; fi
[[ -n ${CLOTHING_ERP_GITHUB_TOKEN:-} ]] || {
    echo 'Set CLOTHING_ERP_GITHUB_TOKEN to a read-only fine-grained GitHub token for the private repository.' >&2
    exit 1
}
# The helper reads the token from the environment. The value is never embedded in the
# repository URL, persisted Git configuration, generated files, or command arguments.
git -c credential.helper='!f() { test "$1" = get && printf "username=x-access-token\npassword=%s\n" "$CLOTHING_ERP_GITHUB_TOKEN"; }; f' \
    clone --depth 1 https://github.com/AviDhandhania/erp.git "$WORK/bootstrap"
ARGS=()
if [[ -n ${CLOTHING_ERP_VERSION:-} ]]; then ARGS+=(--version "$CLOTHING_ERP_VERSION"); fi
python3 "$WORK/bootstrap/deploy/release/download.py" "$WORK/release" "${ARGS[@]}"
bash "$WORK/release/source/deploy/proxmox/install.sh"
