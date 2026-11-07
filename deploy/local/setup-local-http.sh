#!/usr/bin/env bash
# Run once with sudo: install a real port-80 proxy and start the local stack at boot.
set -Eeuo pipefail
ROOT="${CLOTHING_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
[[ $EUID -eq 0 && -n ${SUDO_USER:-} && $SUDO_USER != root ]] || { echo 'Run: sudo ./scripts/setup-local-http.sh' >&2; exit 1; }
[[ $ROOT != *' '* && $ROOT != *$'\n'* ]] || { echo 'Workspace paths containing whitespace are unsupported.' >&2; exit 1; }
if ss -ltn '( sport = :80 )' | tail -n +2 | grep -q .; then
    if ! systemctl is-active --quiet clothing-erp-http; then
        echo 'Port 80 is already in use. No existing web server was changed.' >&2
        exit 1
    fi
fi
if ! command -v nginx >/dev/null; then
    if command -v pacman >/dev/null; then pacman -S --needed --noconfirm nginx
    elif command -v apt-get >/dev/null; then apt-get update; apt-get install -y nginx
    else echo 'Install nginx for this distribution first.' >&2; exit 1; fi
    # Only stop the default server installed by this invocation.
    systemctl stop nginx 2>/dev/null || true
fi
install -d -m 755 /etc/clothing-erp
cat > /etc/clothing-erp/nginx.conf <<'NGINX'
pid /run/clothing-erp-http.pid;
error_log /var/log/clothing-erp-http-error.log;
events { worker_connections 1024; }
http {
    access_log /var/log/clothing-erp-http-access.log;
    map $http_upgrade $connection_upgrade { default upgrade; '' close; }
    server {
        listen 80 default_server;
        listen [::]:80 default_server;
        server_name _;
        client_max_body_size 50m;
        location /socket.io {
            proxy_pass http://127.0.0.1:9000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_set_header Origin $scheme://$http_host;
            proxy_set_header X-Frappe-Site-Name clothing.local;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Frappe-Site-Name clothing.local;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 120s;
        }
    }
}
NGINX
cat > /etc/systemd/system/clothing-erp-local.service <<UNIT
[Unit]
Description=Local Clothing ERP development stack
After=network.target
[Service]
User=$SUDO_USER
WorkingDirectory=$ROOT
ExecStart=$ROOT/scripts/start_all.sh
Restart=on-failure
RestartSec=5
KillMode=control-group
[Install]
WantedBy=multi-user.target
UNIT
NGINX_BIN="$(command -v nginx)"
cat > /etc/systemd/system/clothing-erp-http.service <<UNIT
[Unit]
Description=Clothing ERP HTTP entry point
Requires=clothing-erp-local.service
After=clothing-erp-local.service
[Service]
Type=simple
ExecStart=$NGINX_BIN -c /etc/clothing-erp/nginx.conf -g 'daemon off;'
ExecReload=$NGINX_BIN -c /etc/clothing-erp/nginx.conf -s reload
Restart=on-failure
[Install]
WantedBy=multi-user.target
UNIT
nginx -t -c /etc/clothing-erp/nginx.conf
systemctl daemon-reload
systemctl enable --now clothing-erp-local clothing-erp-http
curl --retry 15 --retry-connrefused --retry-delay 2 -fsS http://127.0.0.1/api/method/ping
printf '\nOpen http://localhost/ or http://<this-computer-IP>/\n'
