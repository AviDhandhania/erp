#!/usr/bin/env bash
# One-time adoption for containers installed before the lifecycle command existed.
set -Eeuo pipefail
[[ $EUID -eq 0 && -d /home/frappe/frappe-bench ]] || { echo 'Run inside an existing Clothing ERP production LXC as root.' >&2; exit 1; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
[[ -n ${CLOTHING_ERP_GITHUB_TOKEN:-} ]] || {
    echo 'Set CLOTHING_ERP_GITHUB_TOKEN to a read-only fine-grained GitHub token for the private repository.' >&2
    exit 1
}
git -c credential.helper='!f() { test "$1" = get && printf "username=x-access-token\npassword=%s\n" "$CLOTHING_ERP_GITHUB_TOKEN"; }; f' \
    clone --depth 1 https://github.com/AviDhandhania/erp.git "$WORK/bootstrap"
python3 "$WORK/bootstrap/deploy/release/download.py" "$WORK/release"
bash "$WORK/release/source/deploy/install-manager.sh"
clothing-erp update
