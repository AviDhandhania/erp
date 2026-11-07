#!/usr/bin/env bash
# Run on the Proxmox host. Installs only into a NEW unprivileged Debian 13 CT.
set -Eeuo pipefail
umask 077
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CTID="${CTID:-}"
STORAGE="${STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
BRIDGE="${BRIDGE:-vmbr0}"
CT_IP="${CT_IP:-dhcp}"
GATEWAY="${GATEWAY:-}"
MEMORY="${MEMORY:-8192}"
CORES="${CORES:-4}"
DISK_GB="${DISK_GB:-40}"
CT_HOSTNAME="${CT_HOSTNAME:-clothing-erp}"

fail() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run this on the Proxmox host as root.'
for tool in pct pveam pvesh pvesm tar ip; do command -v "$tool" >/dev/null || fail "Missing Proxmox tool: $tool"; done
[[ $(uname -m) == x86_64 ]] || fail 'This installer currently supports x86_64 Proxmox hosts.'
for value in "$MEMORY" "$CORES" "$DISK_GB"; do [[ $value =~ ^[1-9][0-9]*$ ]] || fail 'Memory, cores and disk must be positive integers.'; done
(( MEMORY >= 4096 && DISK_GB >= 30 )) || fail 'At least 4096 MiB RAM and 30 GiB disk are required.'
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
pveam update
TEMPLATE="$(pveam available --section system | awk '$2 ~ /^debian-13-standard_.*_amd64.tar.zst$/ {print $2}' | sort -V | tail -1)"
[[ -n $TEMPLATE ]] || fail 'No Debian 13 amd64 standard template is available from pveam.'
pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
# Include only app source, never the development bench, services, data or credentials.
tar -C "$SOURCE_DIR" --exclude=__pycache__ --exclude='*.pyc' -czf "$WORK/app.tar.gz" clothing_erp deploy pyproject.toml README.md AGENTS.md license.txt work.md
pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE" \
    --hostname "$CT_HOSTNAME" --ostype debian --unprivileged 1 \
    --cores "$CORES" --memory "$MEMORY" --swap 1024 \
    --rootfs "$STORAGE:$DISK_GB" --net0 "$NET" --onboot 1

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
printf '\nClothing ERP is ready: http://%s/\nContainer: %s\n' "$CT_ADDRESS" "$CTID"
printf 'Retrieve the generated Administrator password: pct exec %s -- cat /root/clothing-erp-credentials\n' "$CTID"
echo 'Complete the standard ERPNext setup wizard after signing in.'
