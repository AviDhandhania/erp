#!/usr/bin/env python3
"""Write reviewable systemd units for the stable active-bench symlink."""

from pathlib import Path
import argparse

BENCH = "/home/frappe/frappe-bench"
COMMANDS = {
    "web": f"{BENCH}/env/bin/gunicorn --chdir {BENCH}/sites --bind 127.0.0.1:8000 --workers 2 --threads 4 --timeout 120 clothing_erp.wsgi:application",
    "socketio": f"{BENCH}/.platform/node/bin/node apps/frappe/socketio.js",
    "worker": f"{BENCH}/.platform/tools/bin/bench worker --queue short,default,long",
    "schedule": f"{BENCH}/.platform/tools/bin/bench schedule",
}


def render(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, command in COMMANDS.items():
        socket = name == "socketio"
        runtime = (
            "RuntimeDirectory=clothing-erp\nRuntimeDirectoryMode=0750\n"
            if socket
            else ""
        )
        (directory / f"clothing-erp-{name}.service").write_text(f"""[Unit]
Description=Clothing ERP {name}
After=network.target mariadb.service redis-server.service
Requires=mariadb.service redis-server.service
[Service]
User=frappe
Group={"www-data" if socket else "frappe"}
WorkingDirectory={BENCH}
{runtime}Environment=SITES_PATH={BENCH}/sites
Environment=FRAPPE_SITE=clothing.local
Environment=FRAPPE_BENCH_ROOT={BENCH}
Environment=PATH={BENCH}/.platform/tools/bin:{BENCH}/.platform/node/bin:{BENCH}/.platform/bin:/usr/local/bin:/usr/bin:/bin
ExecStart={command}
Restart=on-failure
RestartSec=5
TimeoutStopSec=300
UMask={"0007" if socket else "0027"}
[Install]
WantedBy=multi-user.target
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    render(parser.parse_args().directory)
