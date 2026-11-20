#!/usr/bin/env bash
# Run on the Proxmox host. Installs only into a NEW unprivileged Debian 13 CT.
set -Eeuo pipefail
umask 022
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-}")/../.." 2>/dev/null && pwd || echo "")"
[[ -f $SOURCE_DIR/release.json ]] || { echo 'Use the published release bootstrap (a verified release.json is required).' >&2; exit 1; }
CTID="${CTID:-}"
STORAGE="${STORAGE:-}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-}"
BRIDGE="${BRIDGE:-}"
CT_IP="${CT_IP:-dhcp}"
GATEWAY="${GATEWAY:-}"
MEMORY="${MEMORY:-8192}"
CORES="${CORES:-4}"
DISK_GB="${DISK_GB:-40}"
CT_HOSTNAME="${CT_HOSTNAME:-clothing-erp}"

fail() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run this on the Proxmox host as root.'
for tool in pct pveam pvesh pvesm tar ip python3; do command -v "$tool" >/dev/null || fail "Missing Proxmox tool: $tool"; done
python3 - "$SOURCE_DIR" <<'PYTHON'
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'deploy/release'))
from common import validate_manifest
validate_manifest(json.load(open(Path(sys.argv[1])/'release.json')))
PYTHON
[[ $(uname -m) == x86_64 ]] || fail 'This installer currently supports x86_64 Proxmox hosts.'
for value in "$MEMORY" "$CORES" "$DISK_GB"; do [[ $value =~ ^[1-9][0-9]*$ ]] || fail 'Memory, cores and disk must be positive integers.'; done
(( MEMORY >= 4096 && DISK_GB >= 30 )) || fail 'At least 4096 MiB RAM and 30 GiB disk are required.'

if [[ -z $BRIDGE ]]; then
    DEF_IF="$(ip route show default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}' | head -1)"
    if [[ -n "$DEF_IF" ]] && ip link show "$DEF_IF" type bridge >/dev/null 2>&1; then
        BRIDGE="$DEF_IF"
    elif ip link show vmbr0 >/dev/null 2>&1; then
        BRIDGE="vmbr0"
    else
        BRIDGE="$(ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | grep -v '^fwbr' | head -1)"
        [[ -n "$BRIDGE" ]] || BRIDGE="vmbr0"
    fi
fi

if [[ -z $STORAGE ]]; then
    REQ_KIB="$((DISK_GB * 1024 * 1024))"
    STORAGE="$(pvesm status -content rootdir 2>/dev/null | awk -v req="$REQ_KIB" '
        NR>1 && $3=="active" && $6>=req {
            prio = ($2 ~ /zfspool|lvmthin|btrfs/) ? 1 : 2;
            print prio, $6, $1
        }' | sort -k1,1n -k2,2nr | head -1 | awk '{print $3}')"
    if [[ -z $STORAGE ]]; then
        for candidate in local-lvm local-zfs local; do
            if pvesm status -storage "$candidate" -content rootdir 2>/dev/null | awk -v req="$REQ_KIB" 'NR>1 && $3=="active" && $6>=req {ok=1} END {exit !ok}'; then
                STORAGE="$candidate"
                break
            fi
        done
    fi
fi

if [[ -z $TEMPLATE_STORAGE ]]; then
    if pvesm status -storage local -content vztmpl 2>/dev/null | awk 'NR>1 && $3=="active" {ok=1} END {exit !ok}'; then
        TEMPLATE_STORAGE="local"
    else
        TEMPLATE_STORAGE="$(pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 && $3=="active" {print $1, $6}' | sort -k2 -nr | head -1 | awk '{print $1}')"
    fi
    [[ -n $TEMPLATE_STORAGE ]] || TEMPLATE_STORAGE="local"
fi

[[ $STORAGE =~ ^[a-zA-Z0-9_-]+$ && $TEMPLATE_STORAGE =~ ^[a-zA-Z0-9_-]+$ ]] || fail 'Invalid storage ID.'
[[ $BRIDGE =~ ^[a-zA-Z0-9_.:-]+$ ]] || fail 'Invalid bridge.'
[[ $CT_HOSTNAME =~ ^[a-z][a-z0-9-]{0,62}$ ]] || fail 'Invalid hostname.'
ip link show "$BRIDGE" >/dev/null || fail "Bridge $BRIDGE does not exist."
# Check content support and active storage before creating anything.
pvesm status --storage "$STORAGE" --content rootdir | awk 'NR>1 && $3=="active" {ok=1} END {exit !ok}' || fail "Storage $STORAGE must be active and support rootdir. Set STORAGE to a suitable storage ID."
pvesm status --storage "$TEMPLATE_STORAGE" --content vztmpl | awk 'NR>1 && $3=="active" {ok=1} END {exit !ok}' || fail "Template storage $TEMPLATE_STORAGE is unavailable."
pvesm status --storage "$STORAGE" --content rootdir | awk -v required="$((DISK_GB * 1024 * 1024))" 'NR>1 && $6>=required {ok=1} END {exit !ok}' || fail "Storage $STORAGE has less than $DISK_GB GiB available."
if [[ -z $CTID ]]; then CTID="$(pvesh get /cluster/nextid)"; fi
if [[ ! $CTID =~ ^[1-9][0-9]+$ ]] || (( CTID < 100 )); then fail 'Invalid CTID.'; fi
# nextid with vmid checks both VMs and CTs cluster-wide.
pvesh get /cluster/nextid --vmid "$CTID" >/dev/null || fail "VMID $CTID is already in use."
NET="name=eth0,bridge=$BRIDGE,ip=$CT_IP,type=veth,firewall=1"
if [[ $CT_IP != dhcp ]]; then
    [[ $CT_IP =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ && $GATEWAY =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail 'Set CT_IP to IPv4/CIDR and GATEWAY to an IPv4 gateway, or leave CT_IP=dhcp.'
    NET+=",gw=$GATEWAY"
fi
WORK="$(mktemp -d)"
CREATED=0
# shellcheck disable=SC2034 # Referenced in the EXIT trap.
trap 'rc=$?; rm -rf "$WORK"; if (( rc != 0 && CREATED )); then echo "Installation failed. CT $CTID was preserved for diagnosis; inspect /var/log/clothing-erp-install.log inside it. No existing CT was changed." >&2; fi' EXIT

TEMPLATE=""
EXISTING_TMPL="$(pveam list "$TEMPLATE_STORAGE" 2>/dev/null | awk '$1 ~ /debian-13-standard_.*_amd64\.tar\.(zst|gz|xz)/ {print $1}' | sort -V | tail -1)"
if [[ -z "$EXISTING_TMPL" ]]; then
    EXISTING_TMPL="$(pveam list "$TEMPLATE_STORAGE" 2>/dev/null | awk '$1 ~ /debian-12-standard_.*_amd64\.tar\.(zst|gz|xz)/ {print $1}' | sort -V | tail -1)"
fi
if [[ -n "$EXISTING_TMPL" ]]; then
    TEMPLATE="${EXISTING_TMPL##*/}"
else
    pveam update >/dev/null 2>&1 || true
    TEMPLATE="$(pveam available --section system 2>/dev/null | awk '$2 ~ /^debian-13-standard_.*_amd64\.tar\.(zst|gz|xz)$/ {print $2}' | sort -V | tail -1)"
    if [[ -z "$TEMPLATE" ]]; then
        TEMPLATE="$(pveam available --section system 2>/dev/null | awk '$2 ~ /^debian-12-standard_.*_amd64\.tar\.(zst|gz|xz)$/ {print $2}' | sort -V | tail -1)"
    fi
    [[ -n "$TEMPLATE" ]] || fail 'No Debian 12 or 13 amd64 standard template is available from pveam.'
    pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
fi
# Include only app source, never the development bench, services, data or credentials.
tar -C "$SOURCE_DIR" --exclude=__pycache__ --exclude='*.pyc' -czf "$WORK/app.tar.gz" sales_erp warehouse_erp quality_erp deploy pyproject.toml VERSION README.md AGENTS.md license.txt work.md release.json
mkdir -p /var/lib/lxc 2>/dev/null || true
chmod 755 /var/lib/lxc 2>/dev/null || true
pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE" \
    --hostname "$CT_HOSTNAME" --ostype debian --unprivileged 1 \
    --cores "$CORES" --memory "$MEMORY" --swap 1024 \
    --rootfs "$STORAGE:$DISK_GB" --net0 "$NET" --onboot 1 \
    --features nesting=1

# shellcheck disable=SC2034 # Referenced in the EXIT trap.
CREATED=1
pct start "$CTID"
ready=0
for ((attempt=0; attempt<60; attempt++)); do
    if pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
done
(( ready )) || fail 'Container networking/DNS did not become ready within two minutes.'
pct push "$CTID" "$WORK/app.tar.gz" /root/clothing-erp-source.tar.gz --perms 600
pct exec "$CTID" -- mkdir -p /opt/clothing-erp-source
pct exec "$CTID" -- tar -xzf /root/clothing-erp-source.tar.gz -C /opt/clothing-erp-source
pct exec "$CTID" -- bash /opt/clothing-erp-source/deploy/install-debian.sh
CT_ADDRESS="$(pct exec "$CTID" -- hostname -I | awk '{print $1}')"
printf '\nClothing ERP is ready: https://%s/\nContainer: %s\n' "$CT_ADDRESS" "$CTID"
printf 'Retrieve the generated Administrator password: pct exec %s -- cat /root/clothing-erp-credentials\n' "$CTID"
echo 'Complete the standard ERPNext setup wizard after signing in.'
