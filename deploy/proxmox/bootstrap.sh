#!/usr/bin/env bash
# The bootstrap code is small; all deployed application code comes from a verified stable release.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run on a Proxmox host as root.' >&2; exit 1; }
command -v pct >/dev/null || { echo 'Proxmox VE is required.' >&2; exit 1; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
if ! command -v git >/dev/null; then apt-get update; apt-get install -y git; fi
git clone --depth 1 https://github.com/AviDhandhania/erp.git "$WORK/bootstrap"
ARGS=()
if [[ -n ${CLOTHING_ERP_VERSION:-} ]]; then ARGS+=(--version "$CLOTHING_ERP_VERSION"); fi
python3 "$WORK/bootstrap/deploy/release/download.py" "$WORK/release" "${ARGS[@]}"
bash "$WORK/release/source/deploy/proxmox/install.sh"
