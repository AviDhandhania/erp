#!/usr/bin/env bash
# Real Frappe + ERPNext + Clothing ERP. No mock services and no interactive debugger.
set -Eeuo pipefail
ROOT="${CLOTHING_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
export FRAPPE_BENCH_ROOT="$ROOT/frappe-bench"
export LD_LIBRARY_PATH="$ROOT/.services/usr/lib:${LD_LIBRARY_PATH:-}"
export PATH="$ROOT/.venv/bin:$ROOT/.services/usr/bin:$PATH"
mkdir -p "$ROOT/.services/pids"
if ! mariadb-admin --defaults-file="$ROOT/.services/my.cnf" ping --silent >/dev/null 2>&1; then
    "$ROOT/.services/usr/bin/mariadbd" --defaults-file="$ROOT/.services/my.cnf" > "$ROOT/.services/mariadb.log" 2>&1 &
    for ((i=0;i<30;i++)); do
        if mariadb-admin --defaults-file="$ROOT/.services/my.cnf" ping --silent >/dev/null 2>&1; then break; fi
        sleep 1
    done
    mariadb-admin --defaults-file="$ROOT/.services/my.cnf" ping --silent >/dev/null
fi
for spec in cache:13000 queue:11000; do
    name="${spec%:*}"; port="${spec#*:}"
    if ! valkey-cli -s "$ROOT/.services/data/redis-$name.sock" ping >/dev/null 2>&1; then
        mkdir -p "$ROOT/.services/data/redis-$name"
        valkey-server --bind 127.0.0.1 --port "$port" \
            --unixsocket "$ROOT/.services/data/redis-$name.sock" --unixsocketperm 700 \
            --dir "$ROOT/.services/data/redis-$name" \
            --pidfile "$ROOT/.services/pids/redis-$name.pid" --daemonize yes
    fi
done
export SITES_PATH="$ROOT/frappe-bench/sites"
cd "$ROOT/frappe-bench"
# Children remain in this service's process group/cgroup for clean shutdown.
node apps/frappe/socketio.js > logs/socketio.log 2>&1 &
SOCKET_PID=$!
"$ROOT/bench" worker --queue short,default,long > logs/worker.log 2>&1 &
WORKER_PID=$!
"$ROOT/bench" schedule > logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!
trap 'kill "$SOCKET_PID" "$WORKER_PID" "$SCHEDULER_PID" 2>/dev/null || true' EXIT
# Frappe's static-file wrapper is useful in local development; nginx serves assets in LXC.
. "$ROOT/.venv/bin/activate"
gunicorn --chdir "$ROOT/frappe-bench/sites" --bind 127.0.0.1:8000 --workers 2 --threads 4 --timeout 120 'clothing_erp.wsgi:create_development_application()' &
WEB_PID=$!
trap 'kill "$WEB_PID" "$SOCKET_PID" "$WORKER_PID" "$SCHEDULER_PID" 2>/dev/null || true' EXIT
trap 'exit 0' TERM INT
printf 'Native ERP is running at http://localhost:8000/\nUse sudo ./scripts/setup-local-http.sh once for http://localhost/\n'
wait -n "$WEB_PID" "$SOCKET_PID" "$WORKER_PID" "$SCHEDULER_PID"
exit 1
