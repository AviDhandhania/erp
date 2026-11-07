# Clothing ERP

Clothing ERP is a separate Frappe application alongside **ERPNext** and **Framework**.
It has its own source, version history and GitHub releases. Upstream ERPNext/Frappe
repositories remain unchanged. Everyone uses one IP, login and native app launcher.

## Install

Run on a Proxmox VE amd64 host as root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/bootstrap.sh)
```

The installer downloads the **latest published stable release**, checks its archive
and manifest, and creates a new unprivileged Debian 13 LXC with the complete stack.
It prints `http://<container-IP>/` and how to retrieve the generated Administrator
password. Finish the standard ERPNext company setup after signing in.

Defaults: 4 CPU cores, 8 GiB RAM, 40 GiB disk, DHCP, `vmbr0`, `local-lvm` root storage
and `local` template storage. Override only what differs on your host:

```bash
STORAGE=local-zfs BRIDGE=vmbr1 CTID=210 bash <(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/proxmox/bootstrap.sh)
```

To choose an older published release, set `CLOTHING_ERP_VERSION=v0.3.0`.
For a static address set `CT_IP=192.168.1.50/24 GATEWAY=192.168.1.1`.
Existing guests are never overwritten; failed new guests remain available for diagnosis.
The host needs internet access, working DNS, sufficient resources, and a firewall
policy that permits access to the container's HTTP port.

## Update

Inside the installed LXC, as root:

```bash
clothing-erp update
```

That single command updates Clothing ERP **and the exact compatible ERPNext,
Frappe, Python, Node and Bench versions declared by that release**. It builds a
separate bench first, takes a recovery backup, migrates, switches the active bench,
and checks readiness before opening access again. It never pulls arbitrary core
branches into production.

Useful commands:

```bash
clothing-erp status
clothing-erp check
clothing-erp update --version v0.3.1
clothing-erp update --app-only
clothing-erp backup
clothing-erp recover --yes
clothing-erp rollback --yes
```

`--app-only` requires unchanged upstream/runtime pins. `recover` resumes an
interrupted operation from its recorded phase. `rollback` restores the previous
**code, database and attachments**, not just an old Git checkout. It saves a fresh
backup of current data first; restoring an older recovery point still makes the
older data the live data. Copy backups off the CT for disaster recovery.

From the Proxmox host, updates are equally simple:

```bash
pct exec <CTID> -- clothing-erp update
```

Containers made by the earlier installer can adopt the manager once:

```bash
# Inside that existing production LXC as root
bash <(curl -fsSL https://raw.githubusercontent.com/AviDhandhania/erp/main/deploy/upgrade-bootstrap.sh)
```

This manager is for the dedicated production LXC. It does not convert or downgrade
an arbitrary developer bench.

## Publish your next release

1. Develop Clothing ERP in this repository and push to `main`.
2. In GitHub, open **Actions → Publish release → Run workflow**.
3. Enter a version such as `v0.3.1` and run it.

The workflow updates the app version and tag, runs unit/security/recovery tests,
creates a fresh database-backed Frappe/ERPNext installation, builds all assets,
then publishes checksummed source, an exact-version manifest, provenance attestation,
and a portable Proxmox installer. If verification fails, no stable release is
published. Retry the failed run without rewriting its tag.

Leave the optional ERPNext and Frappe fields blank for a clothing-only release.
When you want core updates, enter their stable v16 tags in that same form: the
workflow tests the new combination before publishing. Customers still run the
same update command. Debian/Proxmox OS administration remains separate from the
application release lifecycle.

Use this workflow rather than publishing empty releases manually: a release is
installable only when its verified assets exist. Details: [release guide](docs/releasing.md).

## What is implemented

The native launcher, three clothing workspaces, five clothing roles, read-only
operational APIs, assignment restrictions, installer, release pipeline, and update/
recovery tooling. Catalogue, retailer approval, garment ordering and warehouse
workflows remain on the [roadmap](work.md).

The five clothing roles use native User Permissions for assigned Customers and
Warehouses; pick lists additionally require an open ToDo assignment. All access is
subject to native ERPNext permissions. No mock sales or simulated ERP server is used.

## Development and operations

- [Architecture and separation](docs/architecture.md)
- [Release workflow and upstream upgrades](docs/releasing.md)
- [Backups, recovery, layout and service commands](docs/operations.md)
- [Deployment pins](deploy/versions.env)

The existing `/home/avi/GitHub/erp` development workspace still uses
`./scripts/start_all.sh`; `sudo ./scripts/setup-local-http.sh` enables no-port local
access. It contains the fictional **TEST Clothing ERP Demo** company. Its pre-existing
ERPNext develop checkout is not a release target and has not been downgraded.

**Validation limits:** automated app/database/recovery tests run locally and in CI.
Host-command tests simulate Proxmox. A complete install/update/reboot/restore on an
actual Proxmox host remains a required deployment trial; it has not been claimed
as completed. Initial HTTP access is intended for a LAN; configure HTTPS for a
public hostname.

MIT license for this application. ERPNext and Frappe retain their upstream licenses.
