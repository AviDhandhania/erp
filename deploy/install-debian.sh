#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo 'Run inside the new container as root.' >&2; exit 1; }
# shellcheck source=/dev/null
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Debian 13 is required.' >&2; exit 1; }
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ! -e /home/frappe/frappe-bench && ! -e /root/clothing-erp-credentials ]] || { echo 'An installation exists. Use clothing-erp update.' >&2; exit 1; }
[[ -f $SOURCE/release.json ]] || { echo 'Use the published release installer, not a main-branch source snapshot.' >&2; exit 1; }
VERSION="$(python3 - "$SOURCE" <<'PY'
import json,sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1])/'deploy/release'))
from common import validate_manifest
print(validate_manifest(json.load(open(Path(sys.argv[1])/'release.json')))['version'])
PY
)"
exec > >(tee -a /var/log/clothing-erp-install.log) 2>&1
trap 'echo "Install stopped at line $LINENO. The new CT and logs were preserved." >&2' ERR
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git build-essential pkg-config \
    mariadb-server mariadb-client libmariadb-dev redis-server nginx chromium fonts-liberation fonts-noto-core \
    libffi-dev libssl-dev libjpeg62-turbo-dev zlib1g-dev libwebp-dev liblcms2-dev \
    libharfbuzz-dev libfribidi-dev libtiff-dev libopenjp2-7-dev cron xz-utils openssl file
cat > /etc/mysql/mariadb.conf.d/60-clothing-erp.cnf <<'CNF'
[mysqld]
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
bind-address=127.0.0.1
innodb-snapshot-isolation=OFF
[client]
default-character-set=utf8mb4
CNF
systemctl enable --now mariadb redis-server cron
systemctl restart mariadb
id frappe >/dev/null 2>&1 || useradd --create-home --shell /bin/bash frappe
install -d -o frappe -g frappe -m 755 /home/frappe/releases
install -d -o root -g root -m 751 /home/frappe/shared
# Verified source must be readable to the unprivileged build user.
chmod o+rx /opt/clothing-erp-source
runuser -u frappe -- bash "$SOURCE/deploy/stage-release.sh" "$SOURCE" "/home/frappe/releases/$VERSION"
ln -s "/home/frappe/releases/$VERSION/bench" /home/frappe/frappe-bench
cd /home/frappe/frappe-bench
export PATH="/home/frappe/frappe-bench/.platform/tools/bin:/home/frappe/frappe-bench/.platform/node/bin:/home/frappe/frappe-bench/.platform/bin:/usr/local/bin:/usr/bin:/bin"
run_frappe() { runuser -u frappe -- env PATH="$PATH" "$@"; }
run_frappe bench set-config -g redis_cache redis://127.0.0.1:6379/0
run_frappe bench set-config -g redis_queue redis://127.0.0.1:6379/1
run_frappe bench set-config -g redis_socketio redis://127.0.0.1:6379/1
run_frappe bench set-config -gp socketio_port 9000
run_frappe bench set-config -g socketio_uds /run/clothing-erp/socketio.sock
run_frappe bench set-config -g chromium_path /usr/bin/chromium
run_frappe bench set-config -g default_site clothing.local
DB_PASSWORD="$(openssl rand -hex 32)"
ADMIN_PASSWORD="$(openssl rand -hex 20)"
SITE_ADDRESS="$(hostname -I | awk '{print $1}')"
printf 'URL: http://%s/\nUser: Administrator\nPassword: %s\n' "$SITE_ADDRESS" "$ADMIN_PASSWORD" > /root/clothing-erp-credentials
mariadb -uroot <<SQL
CREATE USER 'clothing_installer'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON *.* TO 'clothing_installer'@'localhost' WITH GRANT OPTION;
SQL
cleanup() { mariadb -uroot -e "DROP USER IF EXISTS 'clothing_installer'@'localhost';"; }
trap cleanup EXIT
runuser -u frappe -- env PATH="$PATH" FRAPPE_DB_ROOT_PASSWORD="$DB_PASSWORD" FRAPPE_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    env/bin/python "$SOURCE/deploy/create_site.py"
cleanup
trap - EXIT
run_frappe bench --site clothing.local install-app erpnext
run_frappe bench --site clothing.local install-app clothing_erp
run_frappe bench --site clothing.local set-config host_name "http://$SITE_ADDRESS"
run_frappe bench --site clothing.local execute clothing_erp.install.configure_launcher
run_frappe bench --site clothing.local enable-scheduler
mv sites/clothing.local /home/frappe/shared/clothing.local
runuser -u frappe -- ln -s /home/frappe/shared/clothing.local sites/clothing.local
# Stable active symlink is the only path in nginx/systemd; each release owns its own code/env/assets.
cp "$SOURCE/deploy/nginx.conf" /etc/nginx/sites-available/clothing-erp
ln -s /etc/nginx/sites-available/clothing-erp /etc/nginx/sites-enabled/clothing-erp
rm -f /etc/nginx/sites-enabled/default
chmod o+x /home/frappe
python3 "$SOURCE/deploy/render-services.py" /etc/systemd/system
bash "$SOURCE/deploy/install-manager.sh"
systemctl daemon-reload
systemctl enable --now clothing-erp-{web,socketio,worker,schedule}.service
nginx -t
systemctl enable nginx
systemctl restart nginx
for ((attempt=0; attempt<60; attempt++)); do
    if systemctl is-active --quiet clothing-erp-{web,socketio,worker,schedule}.service \
        && curl -fsS http://127.0.0.1/api/method/ping | grep -q pong \
        && curl -fsS http://127.0.0.1/assets/clothing_erp/images/clothing_erp_logo.svg >/dev/null \
        && curl -fsS 'http://127.0.0.1/socket.io/?EIO=4&transport=polling' | grep -q sid; then
        echo 'Ready. Updates: clothing-erp update. Password: /root/clothing-erp-credentials'
        exit 0
    fi
    sleep 2
done
echo 'Health check failed. Inspect journalctl -u clothing-erp-web -u nginx.' >&2
exit 1
