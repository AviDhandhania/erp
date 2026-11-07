# Clothing ERP

An apparel distribution extension installed alongside ERPNext on a real Frappe site.
The native app launcher shows **ERPNext**, **Clothing ERP**, and **Framework**.
Open the server IP in a browser (`http://<IP>/`); nginx handles port 80, static assets,
and realtime connections. Signing in opens the native launcher. All accounting,
customers, products and stock remain standard ERPNext documents.

Implemented: app registration, three native workspaces, five clothing roles,
read-only operational dashboards, assignment restrictions and deployment tooling.
The apparel catalogue, approvals, ordering, picking/packing workflows and retailer
portal are still planned; see [work.md](work.md). No dashboard invents sample sales.

## Install on Proxmox

Run on a **Proxmox VE host as root**, using the published repository:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/bootstrap.sh)
```

This creates a **new unprivileged Debian 13 amd64 LXC**, provisions MariaDB, Redis,
Python, Node, Chromium for PDF printing, Frappe, ERPNext, Clothing ERP, nginx, background workers and daily
backups, and prints the container's URL. Defaults: 4 cores, 8 GiB RAM, 40 GiB disk,
DHCP, bridge `vmbr0`, storage `local-lvm`, template storage `local`. The host must
have those resources available, working DNS and internet access. A site using
another bridge or storage must override them; no installer can infer every host's
network policy. ARM hosts are not supported.

```bash
STORAGE=local-zfs BRIDGE=vmbr1 CTID=210 bash <(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/bootstrap.sh)
```

For a static address, also set `CT_IP=192.168.1.50/24 GATEWAY=192.168.1.1`.
Set `CLOTHING_ERP_REF` to a published release tag to install that revision.
Existing CTs/VMs are rejected. Failed installations preserve the new CT for diagnosis.
This installer does not alter the Proxmox host's network, firewall, or existing guests.

Retrieve the generated password on the host:

```bash
pct exec <CTID> -- cat /root/clothing-erp-credentials
```

Sign in as `Administrator` and complete ERPNext's standard setup wizard with your
company details. The production installer creates **no demo company or customers**.
After setup, the launcher and app workspaces are available. The password is random;
there is no shared production default. Logs: `/var/log/clothing-erp-install.log` in
that CT. Service logs: `journalctl -u clothing-erp-web -u clothing-erp-socketio`.

The scripts and package have automated command-level tests. **A complete installation
has not yet been tested on a real Proxmox host.** Validate a disposable CT before
using this for business data. The initial HTTP setup is intended for your LAN;
HTTPS for a public hostname is a separate administrator configuration.

## Portable installer

A source checkout can create an installer containing the complete custom app:

```bash
./deploy/build-installer.sh
```

Copy `dist/clothing-erp-lxc.run` to the Proxmox host and run:

```bash
bash clothing-erp-lxc.run
```

The package verifies its embedded SHA-256 checksum and requires no GitHub login.
It still downloads upstream dependencies. It excludes local databases, site configs,
virtual environments and Git history. `--extract DIRECTORY` extracts it without
installing anything.

## Runtime contract

Exact upstream release pins are in [deploy/versions.env](deploy/versions.env):
Frappe `v16.55.2`, ERPNext `v16.54.0`, Bench `5.31.1`, Python `3.14.9`, Node `24.22.2`,
and Debian 13's MariaDB/Redis packages. Python, Node, Bench and uv versions are pinned; Debian security
updates are resolved at install time. The installer never uses an ERPNext develop
branch or a `latest` container image. Runtime requirements follow the
[official Frappe installation guide](https://docs.frappe.io/framework/user/en/installation).
Proxmox creation uses the [native container toolkit](https://pve.proxmox.com/pve-docs/pct.1.html).

nginx is the only public entry point. MariaDB, Redis and gunicorn bind to loopback;
realtime runs behind nginx. No mock ERPNext process runs on port 8001. The dedicated
WSGI entry point fixes the site to `clothing.local`, so an IP or forged incoming
site-selection header cannot select another site's database.

## Existing local development workspace

From `/home/avi/GitHub/erp`:

```bash
./scripts/start_all.sh
```

This starts the real local database/cache, workers, scheduler, realtime and gunicorn.
The development address is `http://localhost:8000/`. Stop the foreground process
with Ctrl+C. To use **`http://localhost/` or the machine IP without a port**, run once:

```bash
sudo ./scripts/setup-local-http.sh
```

This installs nginx if necessary and enables the project's own systemd services.
It refuses to take over port 80 from another web server. For this workspace's test
preview, the standard setup wizard was completed with **TEST Clothing ERP Demo**;
no real company or personal data was entered. Production installations use their
own company setup. Local runtime remains the pre-existing ERPNext develop checkout;
this deployment package pins stable v16 and does not downgrade that site's database.

The canonical local scripts live in `deploy/local/`; workspace scripts delegate to
them. Set `CLOTHING_WORKSPACE` if the development workspace is located elsewhere.
The old Docker setup and simulated ERPNext server have been retired.

## Roles and assignments

Roles: Clothing Salesperson, Clothing Sales Manager, Clothing Warehouse Operator,
Clothing Warehouse Manager, Clothing Business Administrator. Administrators assign
roles in **User**. Operational roles have read access for this foundation;
workflow-specific write permissions will accompany those future workflows.

Use native **User Permission** records to assign Customers and Warehouses. Apply
those permissions to all applicable document types. Unassigned operational users
see no customers/tasks. Pick lists also require an open native ToDo assignment to
the operator. Mixed-warehouse delivery/pick documents are denied if they contain an
unassigned warehouse. Native ERPNext permissions still apply; clothing hooks only
add restrictions. Other ERPNext users retain their native access rules.

## Verification and maintenance

```bash
# From the existing development workspace
./scripts/test-dev.sh
.venv/bin/python -m unittest discover -s clothing_erp/deploy/tests -v

# In a production CT as frappe, from /home/frappe/frappe-bench
/home/frappe/.tooling/bin/bench --site clothing.local backup --with-files
```

Daily backups run at 02:00 container time. They reside under the site's private
backups directory and need an off-container copy plus the site's encryption key for
recovery. An automated upgrade/rollback system is not implemented. Do not rerun the
fresh-install script against an existing bench; it refuses to overwrite one.

All custom source is maintained in this repository. Never modify Frappe or ERPNext
core files to implement clothing features. MIT license; see [license.txt](license.txt).
