#!/usr/bin/env bash
# Provision a fresh Debian 13 container. Deliberately refuses an existing bench.
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo 'Run inside the new container as root.' >&2; exit 1; }
# shellcheck source=/dev/null
. /etc/os-release
[[ $ID == debian && $VERSION_ID == 13 ]] || { echo 'Debian 13 is required.' >&2; exit 1; }
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
. "$SOURCE_DIR/deploy/versions.env"
[[ ! -e /home/frappe/frappe-bench && ! -e /root/clothing-erp-credentials ]] || { echo 'Existing installation detected; refusing to overwrite it.' >&2; exit 1; }
exec > >(tee -a /var/log/clothing-erp-install.log) 2>&1
trap 'echo "Installation stopped at line $LINENO. Source and database are preserved." >&2' ERR
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git build-essential pkg-config \
    mariadb-server mariadb-client libmariadb-dev redis-server nginx chromium fonts-liberation fonts-noto-core \
    libffi-dev libssl-dev libjpeg62-turbo-dev zlib1g-dev libwebp-dev liblcms2-dev \
    libharfbuzz-dev libfribidi-dev libtiff-dev libopenjp2-7-dev cron xz-utils openssl
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
# uv bootstraps Python in user space; the system Python is left intact.
curl --fail --silent --show-error --location "https://astral.sh/uv/$UV_VERSION/install.sh" -o /tmp/install-uv.sh
runuser -u frappe -- env UV_INSTALL_DIR=/home/frappe/.local/bin sh /tmp/install-uv.sh
rm /tmp/install-uv.sh
NODE_ARCHIVE="node-v$NODE_VERSION-linux-x64.tar.xz"
curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/$NODE_ARCHIVE" -o "/tmp/$NODE_ARCHIVE"
curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt" -o /tmp/node-shasums
(cd /tmp && awk -v file="$NODE_ARCHIVE" '$2==file' node-shasums | sha256sum --check --strict -)
tar -xJf "/tmp/$NODE_ARCHIVE" -C /opt
ln -s "/opt/node-v$NODE_VERSION-linux-x64/bin/node" /usr/local/bin/node
ln -s "/opt/node-v$NODE_VERSION-linux-x64/bin/npm" /usr/local/bin/npm
# npm's JS launcher resolves node through PATH.
npm install --global --prefix /usr/local yarn@1.22.22
export PATH="/home/frappe/.local/bin:/home/frappe/.tooling/bin:/usr/local/bin:$PATH"
run_frappe() { runuser -u frappe -- env HOME=/home/frappe PATH="$PATH" "$@"; }
run_frappe uv python install "$PYTHON_VERSION"
run_frappe uv venv --python "$PYTHON_VERSION" /home/frappe/.tooling
run_frappe uv pip install --python /home/frappe/.tooling/bin/python "frappe-bench==$BENCH_VERSION"
# Source archives need a Git repository because bench resolves apps using Git metadata.
install -d -o frappe -g frappe /home/frappe/clothing-erp-source
cp -a "$SOURCE_DIR/." /home/frappe/clothing-erp-source/
chown -R frappe:frappe /home/frappe/clothing-erp-source
run_frappe git -C /home/frappe/clothing-erp-source init -b main
run_frappe git -C /home/frappe/clothing-erp-source add .
run_frappe git -C /home/frappe/clothing-erp-source -c user.name=Installer -c user.email=installer@example.invalid commit -m 'Install packaged Clothing ERP source'
cd /home/frappe
run_frappe bench init --python /home/frappe/.tooling/bin/python --frappe-branch "$FRAPPE_REF" --skip-redis-config-generation frappe-bench
cd /home/frappe/frappe-bench
run_frappe bench get-app --branch "$ERPNEXT_REF" https://github.com/frappe/erpnext.git
run_frappe bench get-app /home/frappe/clothing-erp-source
run_frappe bench set-config -g redis_cache redis://127.0.0.1:6379/0
run_frappe bench set-config -g redis_queue redis://127.0.0.1:6379/1
run_frappe bench set-config -g redis_socketio redis://127.0.0.1:6379/1
run_frappe bench set-config -gp socketio_port 9000
run_frappe bench set-config -g socketio_uds /run/clothing-erp/socketio.sock
run_frappe bench set-config -g chromium_path /usr/bin/chromium
run_frappe bench set-config -g default_site clothing.local
run_frappe bench set-config -gp serve_default_site True
# A temporary DB provisioner is dropped even when site creation fails.
DB_PASSWORD="$(openssl rand -hex 32)"
ADMIN_PASSWORD="$(openssl rand -hex 20)"
printf 'URL: http://<container-IP>/\nUser: Administrator\nPassword: %s\n' "$ADMIN_PASSWORD" > /root/clothing-erp-credentials
chmod 600 /root/clothing-erp-credentials
mariadb -uroot <<SQL
CREATE USER 'clothing_installer'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON *.* TO 'clothing_installer'@'localhost' WITH GRANT OPTION;
SQL
cleanup_db_user() { mariadb -uroot -e "DROP USER IF EXISTS 'clothing_installer'@'localhost';"; }
trap cleanup_db_user EXIT
# The Python entry point reads passwords from the environment, never argv.
runuser -u frappe -- env HOME=/home/frappe PATH="$PATH" \
    FRAPPE_DB_ROOT_PASSWORD="$DB_PASSWORD" FRAPPE_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    env/bin/python /home/frappe/clothing-erp-source/deploy/create_site.py
cleanup_db_user
trap - EXIT
run_frappe bench --site clothing.local install-app erpnext
run_frappe bench --site clothing.local install-app clothing_erp
SITE_ADDRESS="$(hostname -I | awk '{print $1}')"
run_frappe bench --site clothing.local set-config host_name "http://$SITE_ADDRESS"
run_frappe bench --site clothing.local execute clothing_erp.install.configure_launcher
run_frappe bench --site clothing.local enable-scheduler
run_frappe bench build --production
# Serve the same site for any incoming IP/Host, preserving Host for CSRF checks.
cp apps/clothing_erp/deploy/nginx.conf /etc/nginx/sites-available/clothing-erp
ln -s /etc/nginx/sites-available/clothing-erp /etc/nginx/sites-enabled/clothing-erp
rm -f /etc/nginx/sites-enabled/default
# nginx only needs traverse/read permissions for public assets, not private files.
chmod o+x /home/frappe /home/frappe/frappe-bench /home/frappe/frappe-bench/sites
find -L sites/assets -type d -exec chmod o+rx {} +
find -L sites/assets -type f -exec chmod o+r {} +
# Assets are linked to public app directories; make the packaged source readable.
chmod o+x apps apps/frappe apps/erpnext apps/clothing_erp apps/frappe/frappe apps/erpnext/erpnext apps/clothing_erp/clothing_erp
for spec in 'web:env/bin/gunicorn --chdir /home/frappe/frappe-bench/sites --bind 127.0.0.1:8000 --workers 2 --threads 4 --timeout 120 clothing_erp.wsgi:application' \
            'socketio:/usr/local/bin/node apps/frappe/socketio.js' \
            'worker:/home/frappe/.tooling/bin/bench worker --queue short,default,long' \
            'schedule:/home/frappe/.tooling/bin/bench schedule'; do
    name="${spec%%:*}"
    command="${spec#*:}"
    cat > "/etc/systemd/system/clothing-erp-$name.service" <<UNIT
[Unit]
Description=Clothing ERP $name
After=network.target mariadb.service redis-server.service
Requires=mariadb.service redis-server.service
[Service]
User=frappe
Group=frappe
WorkingDirectory=/home/frappe/frappe-bench
Environment=SITES_PATH=/home/frappe/frappe-bench/sites
Environment=FRAPPE_SITE=clothing.local
Environment=PATH=/home/frappe/.tooling/bin:/home/frappe/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/frappe/frappe-bench/$command
Restart=on-failure
RestartSec=5
UMask=0027
[Install]
WantedBy=multi-user.target
UNIT
    if [[ $name == socketio ]]; then
        sed -i 's/Group=frappe/Group=www-data/; s/UMask=0027/UMask=0007/' "/etc/systemd/system/clothing-erp-$name.service"
        sed -i '/WorkingDirectory=/a RuntimeDirectory=clothing-erp\nRuntimeDirectoryMode=0750' "/etc/systemd/system/clothing-erp-$name.service"
    fi
    # Absolute commands must not get a bench-directory prefix.
    if [[ $command == /* ]]; then sed -i "s|ExecStart=/home/frappe/frappe-bench/|ExecStart=|" "/etc/systemd/system/clothing-erp-$name.service"; fi
done
systemctl daemon-reload
systemctl enable --now clothing-erp-{web,socketio,worker,schedule}.service
nginx -t
systemctl enable nginx
systemctl restart nginx
# Daily encrypted-at-rest storage is the host administrator's choice; backups stay private.
cat > /etc/cron.d/clothing-erp-backup <<'CRON'
0 2 * * * frappe cd /home/frappe/frappe-bench && /home/frappe/.tooling/bin/bench --site clothing.local backup --with-files >> /home/frappe/frappe-bench/logs/backup.log 2>&1
CRON
for ((attempt=0; attempt<60; attempt++)); do
    if systemctl is-active --quiet clothing-erp-{web,socketio,worker,schedule}.service \
        && curl -fsS http://127.0.0.1/api/method/ping | grep -q pong \
        && curl -fsS http://127.0.0.1/assets/clothing_erp/images/clothing_erp_logo.svg >/dev/null \
        && curl -fsS "http://127.0.0.1/socket.io/?EIO=4&transport=polling" | grep -q sid; then
        echo 'Health check passed. Credentials are in /root/clothing-erp-credentials.'
        exit 0
    fi
    sleep 2
done
echo 'Health check failed. Inspect journalctl -u clothing-erp-web -u nginx.' >&2
exit 1
