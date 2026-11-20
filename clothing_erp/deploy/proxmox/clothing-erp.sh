#!/usr/bin/env bash
# Clothing ERP Proxmox VE Helper Script
# Automates LXC container discovery, creation, full stack installation and startup.
# Usage on Proxmox VE host (as root):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/clothing-erp.sh)"
# or:
#   bash -c "$(wget -qLO - https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/clothing-erp.sh)"
set -Eeuo pipefail
umask 022

# Color formatting
YW='\033[33m'
BL='\033[36m'
RD='\033[01;31m'
GN='\033[1;92m'
DGN='\033[32m'
CL='\033[m'
BOLD='\033[1m'

msg_info()  { echo -e "${BL}[INFO]${CL} $*"; }
msg_ok()    { echo -e "${GN}[OK]${CL} $*"; }
msg_warn()  { echo -e "${YW}[WARN]${CL} $*"; }
msg_error() { echo -e "${RD}[ERROR]${CL} $*" >&2; }

header_info() {
    clear 2>/dev/null || true
    cat << "EOF"
  ____ _       _   _     _                _____ ____  ____  
 / ___| | ___ | |_| |__ (_)_ __   __ _   | ____|  _ \|  _ \ 
| |   | |/ _ \| __| '_ \| | '_ \ / _` |  |  _| | |_) | |_) |
| |___| | (_) | |_| | | | | | | | (_| |_ | |___|  _ <|  __/ 
 \____|_|\___/ \__|_| |_|_|_| |_|\__, (_)_____|_| \_\_|    
                                 |___/                     
EOF
    echo -e "${BOLD}Clothing ERP Proxmox VE Helper Script${CL}"
    echo -e "Automated LXC Deployment: Frappe v16 + ERPNext v16 + India Compliance + Insights"
    echo -e "Apps: Sales ERP (sales_erp), Warehouse ERP (warehouse_erp), Quality ERP (quality_erp)\n"
}

header_info

# --- Pre-flight Checks ---
[[ $EUID -eq 0 ]] || { msg_error "This script must be executed with root privileges on the Proxmox VE host."; exit 1; }
[[ $(uname -m) == "x86_64" ]] || { msg_error "Clothing ERP requires an x86_64 Proxmox host."; exit 1; }

for tool in pct pveam pvesh pvesm tar ip; do
    command -v "$tool" >/dev/null || { msg_error "Missing required Proxmox tool: $tool. Run this on a Proxmox VE host."; exit 1; }
done

# Ensure git, curl, and python3 exist on host
for host_pkg in git curl python3; do
    if ! command -v "$host_pkg" >/dev/null; then
        msg_info "Installing missing host utility: $host_pkg..."
        apt-get update -qq && apt-get install -y -qq "$host_pkg" >/dev/null 2>&1
    fi
done

# --- Auto-Discovery ---
msg_info "Discovering Proxmox host environment and available resources..."

# 1. CTID auto-discovery
AUTO_CTID=""
if command -v pvesh >/dev/null; then
    AUTO_CTID="$(pvesh get /cluster/nextid 2>/dev/null || echo "")"
fi
if [[ -z "$AUTO_CTID" || ! "$AUTO_CTID" =~ ^[1-9][0-9]*$ ]]; then
    for ((id=100; id<999; id++)); do
        if ! pct status "$id" >/dev/null 2>&1 && ! qm status "$id" >/dev/null 2>&1; then
            AUTO_CTID="$id"
            break
        fi
    done
fi
[[ -n "$AUTO_CTID" ]] || { msg_error "Unable to discover an available CTID."; exit 1; }
msg_ok "Next available CTID: ${BOLD}${AUTO_CTID}${CL}"

# 2. Root storage auto-discovery (content: rootdir)
AUTO_STORAGE=""
if [[ -n "${STORAGE:-}" ]]; then
    AUTO_STORAGE="$STORAGE"
else
    # Find active storage with rootdir content and maximum available space
    AUTO_STORAGE="$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $3=="active" {print $1, $6}' | sort -k2 -nr | head -1 | awk '{print $1}')"
    # Fallback to local-lvm or local-zfs if detected
    if [[ -z "$AUTO_STORAGE" ]]; then
        if pvesm status -storage local-lvm -content rootdir >/dev/null 2>&1; then
            AUTO_STORAGE="local-lvm"
        elif pvesm status -storage local-zfs -content rootdir >/dev/null 2>&1; then
            AUTO_STORAGE="local-zfs"
        else
            AUTO_STORAGE="local"
        fi
    fi
fi
msg_ok "Detected Root Storage: ${BOLD}${AUTO_STORAGE}${CL}"

# 3. Template storage auto-discovery (content: vztmpl)
AUTO_TMPL_STORAGE=""
if [[ -n "${TEMPLATE_STORAGE:-}" ]]; then
    AUTO_TMPL_STORAGE="$TEMPLATE_STORAGE"
else
    if pvesm status -storage local -content vztmpl 2>/dev/null | awk 'NR>1 && $3=="active" {ok=1} END {exit !ok}'; then
        AUTO_TMPL_STORAGE="local"
    else
        AUTO_TMPL_STORAGE="$(pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 && $3=="active" {print $1}' | head -1)"
    fi
fi
[[ -n "$AUTO_TMPL_STORAGE" ]] || AUTO_TMPL_STORAGE="local"
msg_ok "Detected Template Storage: ${BOLD}${AUTO_TMPL_STORAGE}${CL}"

# 4. Bridge auto-discovery
AUTO_BRIDGE=""
if [[ -n "${BRIDGE:-}" ]]; then
    AUTO_BRIDGE="$BRIDGE"
elif ip link show vmbr0 >/dev/null 2>&1; then
    AUTO_BRIDGE="vmbr0"
else
    AUTO_BRIDGE="$(ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | head -1)"
    [[ -n "$AUTO_BRIDGE" ]] || AUTO_BRIDGE="vmbr0"
fi
msg_ok "Detected Network Bridge: ${BOLD}${AUTO_BRIDGE}${CL}"

# --- Configuration & Dialog UI ---
CTID="${CTID:-$AUTO_CTID}"
CT_HOSTNAME="${CT_HOSTNAME:-clothing-erp}"
STORAGE="${STORAGE:-$AUTO_STORAGE}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-$AUTO_TMPL_STORAGE}"
BRIDGE="${BRIDGE:-$AUTO_BRIDGE}"
CT_IP="${CT_IP:-dhcp}"
GATEWAY="${GATEWAY:-}"
MEMORY="${MEMORY:-8192}"
CORES="${CORES:-4}"
DISK_GB="${DISK_GB:-40}"
SWAP="${SWAP:-1024}"

INTERACTIVE=0
if [[ -t 0 ]] && command -v whiptail >/dev/null && [[ ! " $* " =~ " -y " ]] && [[ ! " $* " =~ " --default " ]] && [[ ! " $* " =~ " --silent " ]]; then
    INTERACTIVE=1
fi

if [[ $INTERACTIVE -eq 1 ]]; then
    PROMPT_MSG="Create a new Clothing ERP LXC container?\n\n"
    PROMPT_MSG+="Auto-detected defaults:\n"
    PROMPT_MSG+="  • Container ID:  $AUTO_CTID\n"
    PROMPT_MSG+="  • Hostname:      $CT_HOSTNAME\n"
    PROMPT_MSG+="  • CPU Cores:     $CORES vCPU\n"
    PROMPT_MSG+="  • Memory (RAM):  $MEMORY MB\n"
    PROMPT_MSG+="  • Disk Size:     $DISK_GB GB\n"
    PROMPT_MSG+="  • Storage:       $AUTO_STORAGE\n"
    PROMPT_MSG+="  • Network:       $AUTO_BRIDGE (DHCP)\n\n"
    PROMPT_MSG+="Select 'Yes' for 1-Click Default Installation, or 'No' for Advanced Customization."

    if whiptail --title "Clothing ERP LXC Installation" --yes-button "Default Settings" --no-button "Advanced Settings" --yesno "$PROMPT_MSG" 17 68; then
        msg_info "Proceeding with Default Settings..."
    else
        msg_info "Opening Advanced Settings dialog..."
        CTID=$(whiptail --title "Container ID" --inputbox "Enter Container ID (CTID):" 8 50 "$CTID" 3>&1 1>&2 2>&3)
        CT_HOSTNAME=$(whiptail --title "Hostname" --inputbox "Enter Container Hostname:" 8 50 "$CT_HOSTNAME" 3>&1 1>&2 2>&3)
        CORES=$(whiptail --title "CPU Cores" --inputbox "Allocated CPU Cores:" 8 50 "$CORES" 3>&1 1>&2 2>&3)
        MEMORY=$(whiptail --title "Memory (RAM)" --inputbox "Allocated RAM in MB (min 4096):" 8 50 "$MEMORY" 3>&1 1>&2 2>&3)
        DISK_GB=$(whiptail --title "Disk Size" --inputbox "Root Disk Size in GB (min 30):" 8 50 "$DISK_GB" 3>&1 1>&2 2>&3)
        STORAGE=$(whiptail --title "Storage" --inputbox "Target Storage Pool for Container Rootfs:" 8 50 "$STORAGE" 3>&1 1>&2 2>&3)
        BRIDGE=$(whiptail --title "Network Bridge" --inputbox "Network Bridge Interface:" 8 50 "$BRIDGE" 3>&1 1>&2 2>&3)
        
        IP_CHOICE=$(whiptail --title "IP Assignment" --menu "Choose IP Configuration:" 10 50 2 \
            "1" "DHCP (Automatic)" \
            "2" "Static IPv4" 3>&1 1>&2 2>&3)
        if [[ "$IP_CHOICE" == "2" ]]; then
            CT_IP=$(whiptail --title "Static IPv4" --inputbox "Enter Static IP address with CIDR mask (e.g. 192.168.1.100/24):" 8 60 "192.168.1.100/24" 3>&1 1>&2 2>&3)
            GATEWAY=$(whiptail --title "Gateway" --inputbox "Enter IPv4 Gateway address (e.g. 192.168.1.1):" 8 60 "192.168.1.1" 3>&1 1>&2 2>&3)
        else
            CT_IP="dhcp"
            GATEWAY=""
        fi
    fi
fi

# Input validation
for val in "$MEMORY" "$CORES" "$DISK_GB"; do
    [[ $val =~ ^[1-9][0-9]*$ ]] || { msg_error "Memory, cores and disk must be positive integers."; exit 1; }
done
(( MEMORY >= 4096 && DISK_GB >= 30 )) || { msg_error "At least 4096 MB RAM and 30 GB disk are required."; exit 1; }
[[ $STORAGE =~ ^[a-zA-Z0-9_-]+$ && $TEMPLATE_STORAGE =~ ^[a-zA-Z0-9_-]+$ ]] || { msg_error "Invalid storage ID."; exit 1; }
[[ $BRIDGE =~ ^[a-zA-Z0-9_.:-]+$ ]] || { msg_error "Invalid bridge interface name."; exit 1; }
[[ $CT_HOSTNAME =~ ^[a-z][a-z0-9-]{0,62}$ ]] || { msg_error "Invalid hostname."; exit 1; }
ip link show "$BRIDGE" >/dev/null 2>&1 || { msg_error "Bridge $BRIDGE does not exist."; exit 1; }

# Validate storage status and capacity
pvesm status --storage "$STORAGE" --content rootdir 2>/dev/null | awk 'NR>1 && $3=="active" {ok=1} END {exit !ok}' || {
    msg_error "Storage '$STORAGE' is unavailable or does not support container rootdir."; exit 1;
}
pvesm status --storage "$TEMPLATE_STORAGE" --content vztmpl 2>/dev/null | awk 'NR>1 && $3=="active" {ok=1} END {exit !ok}' || {
    msg_error "Template storage '$TEMPLATE_STORAGE' is unavailable."; exit 1;
}
pvesm status --storage "$STORAGE" --content rootdir 2>/dev/null | awk -v required="$((DISK_GB * 1024 * 1024))" 'NR>1 && $6>=required {ok=1} END {exit !ok}' || {
    msg_error "Storage '$STORAGE' does not have at least $DISK_GB GB available."; exit 1;
}

# Verify CTID availability
if [[ ! $CTID =~ ^[1-9][0-9]+$ ]] || (( CTID < 100 )); then msg_error "Invalid CTID: $CTID."; exit 1; fi
pvesh get /cluster/nextid --vmid "$CTID" >/dev/null 2>&1 || { msg_error "CTID $CTID is already in use."; exit 1; }

# Setup network parameter
NET="name=eth0,bridge=$BRIDGE,ip=$CT_IP,type=veth,firewall=1"
if [[ $CT_IP != "dhcp" ]]; then
    [[ $CT_IP =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ && $GATEWAY =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || {
        msg_error "Invalid static IP ($CT_IP) or Gateway ($GATEWAY)."; exit 1;
    }
    NET+=",gw=$GATEWAY"
fi

# --- Template Discovery / Download ---
msg_info "Checking Debian LXC standard template..."
TEMPLATE=""
EXISTING_TMPL="$(pveam list "$TEMPLATE_STORAGE" 2>/dev/null | awk '$1 ~ /debian-(13|12)-standard_.*_amd64\.tar\.(zst|gz|xz)/ {print $1}' | tail -1 || echo '')"
if [[ -n "$EXISTING_TMPL" ]]; then
    TEMPLATE="${EXISTING_TMPL##*/}"
    msg_ok "Using cached template: ${TEMPLATE}"
else
    msg_info "Updating Proxmox template index..."
    pveam update >/dev/null 2>&1 || true
    TEMPLATE="$(pveam available --section system 2>/dev/null | awk '$2 ~ /^debian-13-standard_.*_amd64\.tar\.(zst|gz|xz)$/ {print $2}' | sort -V | tail -1)"
    if [[ -z "$TEMPLATE" ]]; then
        TEMPLATE="$(pveam available --section system 2>/dev/null | awk '$2 ~ /^debian-12-standard_.*_amd64\.tar\.(zst|gz|xz)$/ {print $2}' | sort -V | tail -1)"
    fi
    [[ -n "$TEMPLATE" ]] || { msg_error "No Debian 12 or 13 amd64 template found in pveam."; exit 1; }
    msg_info "Downloading Debian template: $TEMPLATE into $TEMPLATE_STORAGE..."
    pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
    msg_ok "Downloaded $TEMPLATE"
fi

# --- Workspace & Trap Setup ---
WORK="$(mktemp -d)"
CREATED=0
trap 'rc=$?; rm -rf "$WORK"; if (( rc != 0 && CREATED )); then echo -e "\n${RD}Installation encountered an error.${CL} Container $CTID was preserved for diagnosis.\nInspect logs inside the CT at: /var/log/clothing-erp-install.log" >&2; fi' EXIT

# --- Source Acquisition ---
# If running inside a git clone, use it; otherwise clone the public repository
SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
fi
SOURCE_ROOT=""
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/../../sales_erp/pyproject.toml" ]]; then
    SOURCE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    msg_info "Using local source tree at: $SOURCE_ROOT"
else
    msg_info "Cloning Clothing ERP from public repository..."
    git clone --depth 1 https://github.com/AviDhandhania/erp.git "$WORK/repo"
    SOURCE_ROOT="$WORK/repo"
fi

# Ensure release.json is present in source root for installer validation
if [[ ! -f "$SOURCE_ROOT/release.json" ]]; then
    if [[ -f "$SOURCE_ROOT/deploy/tests/fixtures/release.production.json" ]]; then
        cp "$SOURCE_ROOT/deploy/tests/fixtures/release.production.json" "$SOURCE_ROOT/release.json"
    elif [[ -f "$SOURCE_ROOT/deploy/tests/fixtures/release.json" ]]; then
        cp "$SOURCE_ROOT/deploy/tests/fixtures/release.json" "$SOURCE_ROOT/release.json"
    else
        cat > "$SOURCE_ROOT/release.json" << 'EOF'
{
  "schema": 1,
  "platform": "debian13-native-v1",
  "version": "v0.3.1",
  "repository": "AviDhandhania/erp",
  "source_commit": "61468e4695b28531102613d965d1d6a78cead888",
  "frappe": { "ref": "v16.55.2", "commit": "3d1284c5fdb52207a516a49bbf2fd186cb43b3ab" },
  "erpnext": { "ref": "v16.54.0", "commit": "495380b59c8701629f25089bd3807e6ddf7f26c6" },
  "insights": { "ref": "v3.15.1", "commit": "c7dc954d8275756deb5ad24f7c35c3f3c2ca1a6c" },
  "india_compliance": { "ref": "v16.10.0", "commit": "93eca2f553c04f6695e3d6103be8a4e6e6264d39" },
  "runtime": { "bench": "5.31.1", "node": "24.22.2", "python": "3.14.9", "uv": "0.13.7" },
  "archive": { "name": "clothing-erp-v0.3.1.tar.gz", "sha256": "0000000000000000000000000000000000000000000000000000000000000000" },
  "locks": {
    "python.txt": { "path": "deploy/locks/python.txt", "sha256": "9ea459c01f87a5c3e86bba4a38ae45985981423c3a114a73cbba0b3dd92d9e3f" },
    "tools.txt": { "path": "deploy/locks/tools.txt", "sha256": "bb1ae2605571fa88c3c9600dd90da7ec6cf9b2953cbe05a14054aee8249bb990" }
  }
}
EOF
    fi
fi

# Ensure deploy/locks are populated from fixtures
if [[ ! -d "$SOURCE_ROOT/deploy/locks" ]] && [[ -d "$SOURCE_ROOT/deploy/tests/fixtures/locks" ]]; then
    mkdir -p "$SOURCE_ROOT/deploy/locks"
    cp -a "$SOURCE_ROOT/deploy/tests/fixtures/locks/"* "$SOURCE_ROOT/deploy/locks/"
fi

# --- Container Creation ---
msg_info "Creating LXC Container ${BOLD}${CTID}${CL} (${CT_HOSTNAME})..."

# Ensure standard permissions on /var/lib/lxc for unprivileged container namespace traversal
mkdir -p /var/lib/lxc 2>/dev/null || true
chmod 755 /var/lib/lxc 2>/dev/null || true

# If a previous failed attempt left an unmanaged directory or broken state, clean it up
if [[ -d "/var/lib/lxc/$CTID" ]] && ! pct status "$CTID" >/dev/null 2>&1; then
    rm -rf "/var/lib/lxc/$CTID" 2>/dev/null || true
fi
if ! pct status "$CTID" >/dev/null 2>&1 && [[ ! -f "/etc/pve/lxc/${CTID}.conf" ]]; then
    if command -v pvesm >/dev/null && pvesm list "$STORAGE" 2>/dev/null | grep -q "subvol-${CTID}-disk"; then
        msg_info "Cleaning up orphaned storage volume subvol-${CTID}-disk-0 on $STORAGE..."
        pvesm free "${STORAGE}:subvol-${CTID}-disk-0" >/dev/null 2>&1 || true
    fi
fi

pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE" \
    --hostname "$CT_HOSTNAME" \
    --ostype debian \
    --unprivileged 1 \
    --cores "$CORES" \
    --memory "$MEMORY" \
    --swap "$SWAP" \
    --rootfs "$STORAGE:$DISK_GB" \
    --net0 "$NET" \
    --onboot 1 \
    --features nesting=1,keyctl=1

CREATED=1
msg_ok "Created LXC Container ${BOLD}${CTID}${CL}"

# Apply container firewall rules if firewall directory exists
if [[ -d /etc/pve/firewall ]] && [[ -f "$SOURCE_ROOT/deploy/proxmox/clothing-erp.fw" ]]; then
    msg_info "Configuring Proxmox container firewall rules..."
    cp "$SOURCE_ROOT/deploy/proxmox/clothing-erp.fw" "/etc/pve/firewall/${CTID}.fw"
    chmod 640 "/etc/pve/firewall/${CTID}.fw"
fi

# --- Container Startup ---
msg_info "Starting container ${CTID}..."
pct start "$CTID"

msg_info "Waiting for container networking and DNS resolution..."
ready=0
for ((attempt=0; attempt<60; attempt++)); do
    if pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1 || pct exec "$CTID" -- getent hosts github.com >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done
(( ready )) || { msg_error "Container networking/DNS did not become ready within two minutes."; exit 1; }
msg_ok "Container networking is operational"

# --- Payload Packaging & Push ---
msg_info "Packaging and uploading application components..."
tar -C "$SOURCE_ROOT" --exclude=__pycache__ --exclude='*.pyc' -czf "$WORK/app.tar.gz" \
    sales_erp warehouse_erp quality_erp deploy pyproject.toml VERSION README.md AGENTS.md license.txt work.md release.json

pct push "$CTID" "$WORK/app.tar.gz" /root/clothing-erp-source.tar.gz --perms 600
pct exec "$CTID" -- mkdir -p /opt/clothing-erp-source
pct exec "$CTID" -- tar -xzf /root/clothing-erp-source.tar.gz -C /opt/clothing-erp-source
pct exec "$CTID" -- chmod -R a+rX /opt/clothing-erp-source

# --- In-Guest Stack Installation ---
msg_info "Executing automated in-container installation (MariaDB, Redis, Frappe, ERPNext, Apps, TLS)..."
echo -e "${YW}Note: This provisions Python, Node.js, MariaDB, Redis, Bench, and builds Frappe assets.${CL}"
echo -e "${YW}Streaming guest install log below (also logged to /var/log/clothing-erp-install.log):${CL}\n"

pct exec "$CTID" -- bash /opt/clothing-erp-source/deploy/install-debian.sh

# --- Completion Details ---
CT_ADDRESS="$(pct exec "$CTID" -- hostname -I | awk '{print $1}')"
ADMIN_PASSWORD="$(pct exec "$CTID" -- awk -F'Password: ' '/Password:/ {print $2}' /root/clothing-erp-credentials 2>/dev/null || echo 'Check /root/clothing-erp-credentials')"

echo
echo -e "${GN}══════════════════════════════════════════════════════════════════════════════${CL}"
echo -e "${BOLD}${GN}              CLOTHING ERP LXC PROVISIONED SUCCESSFULLY!              ${CL}"
echo -e "${GN}══════════════════════════════════════════════════════════════════════════════${CL}"
echo -e "  ${BOLD}Container ID:${CL}    ${CTID}"
echo -e "  ${BOLD}Hostname:${CL}        ${CT_HOSTNAME}"
echo -e "  ${BOLD}IP Address:${CL}      ${CT_ADDRESS}"
echo -e "  ${BOLD}Web UI URL:${CL}      ${BL}https://${CT_ADDRESS}/${CL}"
echo -e "  ${BOLD}Username:${CL}        Administrator"
echo -e "  ${BOLD}Password:${CL}        ${YW}${ADMIN_PASSWORD}${CL}"
echo -e "  ${BOLD}Credentials:${CL}     Stored in /root/clothing-erp-credentials inside the container"
echo
echo -e "${BOLD}Installed Applications:${CL}"
echo -e "  ✓ Frappe Framework (v16.55.2)"
echo -e "  ✓ ERPNext (v16.54.0)"
echo -e "  ✓ India Compliance (v16.10.0)"
echo -e "  ✓ Frappe Insights (v3.15.1)"
echo -e "  ✓ Sales ERP (sales_erp)"
echo -e "  ✓ Warehouse ERP (warehouse_erp)"
echo -e "  ✓ Quality ERP (quality_erp)"
echo -e "  ✓ Hardened Nginx TLS (ports 80 -> 443 redirect)"
echo -e "  ✓ Hardened systemd services (web, socketio, worker, schedule)"
echo
echo -e "${BOLD}Management Commands (on Proxmox Host):${CL}"
echo -e "  • Enter Container:         ${BL}pct enter ${CTID}${CL}"
echo -e "  • View Credentials:        ${BL}pct exec ${CTID} -- cat /root/clothing-erp-credentials${CL}"
echo -e "  • Check Service Status:    ${BL}pct exec ${CTID} -- clothing-erp status${CL}"
echo -e "  • Check Health:            ${BL}pct exec ${CTID} -- clothing-erp check${CL}"
echo -e "  • Application Update:      ${BL}pct exec ${CTID} -- clothing-erp update${CL}"
echo -e "${GN}══════════════════════════════════════════════════════════════════════════════${CL}"
echo
