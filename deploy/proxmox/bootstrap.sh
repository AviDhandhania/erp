#!/usr/bin/env bash
# Download one complete source revision, then run its installer.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run on a Proxmox host as root.' >&2; exit 1; }
command -v pct >/dev/null || { echo 'Proxmox VE is required.' >&2; exit 1; }
REPO="https://github.com/AviDhandhania/erp.git"
REF="${CLOTHING_ERP_REF:-main}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
if ! command -v git >/dev/null; then apt-get update; apt-get install -y git; fi
git clone --depth 1 --branch "$REF" "$REPO" "$WORK/source"
bash "$WORK/source/deploy/proxmox/install.sh"
