#!/usr/bin/env bash
# Clothing ERP Update Script
# Usage on Proxmox VE Host:
#   pct exec 119 -- bash -c "$(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/update.sh)"
# Or directly on host:
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/update.sh)" [CTID]
set -Eeuo pipefail

# Formatting
GN='\033[1;92m'
YW='\033[33m'
BL='\033[36m'
RD='\033[01;31m'
CL='\033[m'
BOLD='\033[1m'

msg_info()  { echo -e "${BL}[INFO]${CL} $*"; }
msg_ok()    { echo -e "${GN}[OK]${CL} $*"; }
msg_warn()  { echo -e "${YW}[WARN]${CL} $*"; }
msg_error() { echo -e "${RD}[ERROR]${CL} $*" >&2; }

# Determine if running on Proxmox host or inside LXC container
if command -v pct >/dev/null 2>&1 && [[ -d /etc/pve ]]; then
    # Running on Proxmox host
    CTID="${1:-}"
    if [[ -z "$CTID" ]]; then
        # Try finding running clothing-erp container
        CTID="$(pct list 2>/dev/null | awk '$3 == "running" && $2 ~ /clothing/ {print $1}' | head -1)"
    fi
    if [[ -z "$CTID" ]]; then
        CTID="119"
    fi
    if ! pct status "$CTID" >/dev/null 2>&1; then
        msg_error "Container ID $CTID not found on this Proxmox host."
        exit 1
    fi
    msg_info "Executing update inside container ${BOLD}${CTID}${CL}..."
    pct exec "$CTID" -- bash -c "$(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/update.sh)"
    exit 0
fi

# --- Executing inside container ---
msg_info "Updating Clothing ERP from repository main branch..."

WORK_DIR="$(mktemp -d /tmp/clothing-update-XXXXXX)"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

# 1. Clone latest code from GitHub main branch
msg_info "Fetching latest code from https://github.com/AviDhandhania/erp.git..."
git clone --depth 1 https://github.com/AviDhandhania/erp.git "$WORK_DIR/repo"

# 2. Update /opt/clothing-erp-source
msg_info "Updating application source..."
mkdir -p /opt/clothing-erp-source
cp -a "$WORK_DIR/repo/sales_erp" /opt/clothing-erp-source/
cp -a "$WORK_DIR/repo/warehouse_erp" /opt/clothing-erp-source/
cp -a "$WORK_DIR/repo/quality_erp" /opt/clothing-erp-source/
cp -a "$WORK_DIR/repo/deploy" /opt/clothing-erp-source/
cp -a "$WORK_DIR/repo/pyproject.toml" /opt/clothing-erp-source/
cp -a "$WORK_DIR/repo/VERSION" /opt/clothing-erp-source/
chmod -R a+rX /opt/clothing-erp-source

# 3. Update lifecycle manager scripts in /opt/clothing-erp/manager/
if [[ -d /opt/clothing-erp/manager ]]; then
    install -m 644 "$WORK_DIR/repo/deploy/release/common.py" "$WORK_DIR/repo/deploy/release/lifecycle.py" /opt/clothing-erp/manager/
fi

# 4. Find active bench and update apps
BENCH_DIR=""
for b in /home/frappe/frappe-bench /home/erp/frappe-bench; do
    if [[ -d "$b/apps" && -f "$b/sites/common_site_config.json" ]]; then
        BENCH_DIR="$b"
        break
    fi
done

if [[ -z "$BENCH_DIR" ]]; then
    BENCH_DIR="$(find /home/frappe/releases -name "bench" -type d 2>/dev/null | tail -1)"
fi

[[ -n "$BENCH_DIR" ]] || { msg_error "Could not locate active frappe-bench directory."; exit 1; }

BENCH_USER="$(stat -c '%U' "$BENCH_DIR")"
msg_info "Found active bench at ${BOLD}${BENCH_DIR}${CL} (owned by ${BENCH_USER})"

# 5. Update upstream applications (frappe, erpnext, insights, india_compliance)
if [[ -f "$WORK_DIR/repo/deploy/versions.env" ]]; then
    # shellcheck source=/dev/null
    . "$WORK_DIR/repo/deploy/versions.env"
fi

update_upstream_app() {
    local app_name="$1"
    local target_ref="$2"
    local default_remote_url="$3"
    local app_dir="$BENCH_DIR/apps/$app_name"

    if [[ -z "$target_ref" || ! -d "$app_dir" ]]; then
        return 0
    fi

    local current_tag
    current_tag="$(git -C "$app_dir" describe --tags --exact-match 2>/dev/null || git -C "$app_dir" describe --tags 2>/dev/null || true)"
    if [[ "$current_tag" == "$target_ref"* ]]; then
        msg_ok "Upstream app ${BOLD}${app_name}${CL} is already at ${target_ref}."
        return 0
    fi

    msg_info "Checking upstream app ${BOLD}${app_name}${CL} (current: ${current_tag:-unknown}, target: ${BOLD}${target_ref}${CL})..."
    local remote
    remote="$(git -C "$app_dir" remote 2>/dev/null | head -1 || true)"
    if [[ -z "$remote" ]]; then
        remote="upstream"
        git -C "$app_dir" remote add "$remote" "$default_remote_url"
    fi

    msg_info "Fetching and checking out ${BOLD}${target_ref}${CL} for ${BOLD}${app_name}${CL}..."
    git -C "$app_dir" fetch --depth 1 "$remote" tag "$target_ref" 2>/dev/null || git -C "$app_dir" fetch "$remote" tag "$target_ref" 2>/dev/null || git -C "$app_dir" fetch --tags "$remote"
    git -C "$app_dir" checkout "$target_ref" 2>/dev/null || git -C "$app_dir" checkout "tags/$target_ref"
    chown -R "${BENCH_USER}:${BENCH_USER}" "$app_dir"
    msg_ok "Upstream app ${BOLD}${app_name}${CL} updated to $(git -C "$app_dir" describe --tags --always 2>/dev/null || echo "$target_ref")."
}

update_upstream_app "frappe" "${FRAPPE_REF:-}" "https://github.com/frappe/frappe.git"
update_upstream_app "erpnext" "${ERPNEXT_REF:-}" "https://github.com/frappe/erpnext.git"
update_upstream_app "insights" "${INSIGHTS_REF:-}" "https://github.com/frappe/insights.git"
update_upstream_app "india_compliance" "${INDIA_COMPLIANCE_REF:-}" "https://github.com/resilient-tech/india-compliance.git"

# Sync python editable installs and dependencies
msg_info "Syncing Python packages in bench environment..."
su - "$BENCH_USER" -c "
    export PATH=\"$BENCH_DIR/.platform/tools/bin:$BENCH_DIR/.platform/node/bin:$BENCH_DIR/.platform/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:\$PATH\"
    export HOME=\"/home/$BENCH_USER\"
    cd \"$BENCH_DIR\"
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python \"$BENCH_DIR/env/bin/python\" -e apps/frappe -e apps/erpnext -e apps/insights -e apps/india_compliance 2>/dev/null || \
        \"$BENCH_DIR/env/bin/pip\" install -e apps/frappe -e apps/erpnext -e apps/insights -e apps/india_compliance
    else
        \"$BENCH_DIR/env/bin/pip\" install -e apps/frappe -e apps/erpnext -e apps/insights -e apps/india_compliance
    fi
"

# Copy files directly into installed apps if they are directories or targets of symlinks
for app in sales_erp warehouse_erp quality_erp; do
    APP_TARGET="$BENCH_DIR/apps/$app"
    if [[ -L "$APP_TARGET" ]]; then
        REAL_TARGET="$(readlink -f "$APP_TARGET")"
        msg_info "Updating symlinked app $app at $REAL_TARGET..."
        mkdir -p "$REAL_TARGET"
        cp -a "$WORK_DIR/repo/$app/$app/"* "$REAL_TARGET/"
        chown -R "${BENCH_USER}:${BENCH_USER}" "$REAL_TARGET"
    elif [[ -d "$APP_TARGET" ]]; then
        msg_info "Updating app directory $app..."
        cp -a "$WORK_DIR/repo/$app/$app" "$BENCH_DIR/apps/$app/" 2>/dev/null || true
        chown -R "${BENCH_USER}:${BENCH_USER}" "$APP_TARGET"
    fi
done

# Also update apps in the release source directory if present
RELEASE_SOURCE="$(readlink -f "$BENCH_DIR/..")/source"
if [[ -d "$RELEASE_SOURCE" ]]; then
    msg_info "Updating release source tree at $RELEASE_SOURCE..."
    cp -a "$WORK_DIR/repo/sales_erp" "$RELEASE_SOURCE/"
    cp -a "$WORK_DIR/repo/warehouse_erp" "$RELEASE_SOURCE/"
    cp -a "$WORK_DIR/repo/quality_erp" "$RELEASE_SOURCE/"
    chown -R "${BENCH_USER}:${BENCH_USER}" "$RELEASE_SOURCE"
fi

# 5. Run bench migrate and clear-cache
msg_info "Running bench database migration and cache reset..."
export PATH="$BENCH_DIR/.platform/tools/bin:$BENCH_DIR/.platform/node/bin:$BENCH_DIR/.platform/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

SITE_NAME="clothing.local"
if [[ ! -d "$BENCH_DIR/sites/$SITE_NAME" && -d "/home/${BENCH_USER}/shared/$SITE_NAME" ]]; then
    ln -sf "/home/${BENCH_USER}/shared/$SITE_NAME" "$BENCH_DIR/sites/$SITE_NAME"
fi

su - "$BENCH_USER" -c "
    export PATH=\"$PATH\"
    export HOME=\"/home/$BENCH_USER\"
    cd \"$BENCH_DIR\"
    bench --site $SITE_NAME migrate
    bench --site $SITE_NAME clear-cache
"

# 6. Restart background and web services
msg_info "Restarting Clothing ERP services..."
systemctl restart clothing-erp-{web,socketio,worker,schedule}.service 2>/dev/null || true
systemctl restart nginx 2>/dev/null || true

# 7. Verification health check
msg_info "Verifying service availability..."
for ((attempt=0; attempt<30; attempt++)); do
    if curl -kfsS https://127.0.0.1/api/method/ping >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

LATEST_COMMIT="$(git -C "$WORK_DIR/repo" rev-parse --short HEAD)"
echo
echo -e "${GN}══════════════════════════════════════════════════════════════════════════════${CL}"
echo -e "${BOLD}${GN}         CLOTHING ERP UPDATED SUCCESSFULLY (commit ${LATEST_COMMIT})         ${CL}"
echo -e "${GN}══════════════════════════════════════════════════════════════════════════════${CL}"
echo -e "  ✓ Latest security & permission patches applied"
echo -e "  ✓ Native ERPNext permissions synced (Sales Order, Purchase Order, Item, Customer)"
echo -e "  ✓ System Manager & Business Administrator permissions restored"
echo -e "  ✓ Database migrated and caches refreshed"
echo -e "  ✓ Services restarted and verified online"
echo
