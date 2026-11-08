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
**code, database, attachments and pending jobs**, not just an old Git checkout. It saves a fresh
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
then publishes checksummed source, an exact-version manifest, tested dependency locks, provenance attestation,
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
operational APIs, assignment restrictions, responsive native Item/Variant clothing
catalogue, retailer application/approval/visit workflow, installer, release pipeline,
and update/recovery tooling. Customer-aware pricing, garment ordering and warehouse workflows remain on the
[roadmap](work.md).

The five clothing roles use native User Permissions for assigned Customers and
Warehouses; pick lists additionally require an open ToDo assignment. All access is
subject to native ERPNext permissions. No mock sales or simulated ERP server is used.

## Development and operations

- [Architecture and separation](docs/architecture.md)
- [ERPNext settings compatibility](docs/erpnext-settings-compatibility.md)
- [Release workflow and upstream upgrades](docs/releasing.md)
- [Backups, recovery, layout and service commands](docs/operations.md)
- [Deployment pins](deploy/versions.env)

The existing `/home/avi/GitHub/erp` development workspace uses
`./scripts/start_all.sh`. Open **http://localhost:8000** for current local testing.
This development path serves Frappe directly and does not use nginx, port 80 or a
system service. It contains the fictional **TEST Clothing ERP Demo** company. Its
pre-existing ERPNext develop checkout is not a release target and has not been
downgraded.

Populate the local catalogue with fictional ERPNext templates, variants, prices,
submitted stock and a test retailer by running this idempotent development-only command:

```bash
cd /home/avi/GitHub/erp/frappe-bench
../bench --site clothing.local execute clothing_erp.seed.seed_catalogue
```

It refuses non-developer sites and only uses clearly labelled `TEST` catalogue data.

To add a product gallery without changing ERPNext core, open the colour-specific Item
template in ERPNext, find **Clothing Product Gallery** beside the primary image, and add
ordered image rows with optional captions. Save the Item. The catalogue shows a
**View photos** action and opens the images in a responsive previous/next viewer.
Uploaded gallery files are stored in the standard site `public/files` or
`private/files` directory and are included in site backups. Removing a gallery row
deletes its local upload only when no Item or other gallery still references it; a
daily conservative sweep handles abandoned uploads. Packaged `/assets/clothing_erp/`
demo images remain release-managed and are never removed by this cleanup.

The catalogue's retailer selector only lists Customers permitted by native User
Permissions. Selecting one recalculates the displayed quantity-one rates through
ERPNext's item-pricing engine, including that Customer's Price List, Pricing Rules,
currency exchange and UOM behavior. Select quantities and use **Create draft order** to
create a standard ERPNext draft Sales Order. The browser does not supply its displayed
rates: the server rechecks access and Items, and ERPNext recalculates commercial values.
Submission, credit checks, reservation, approval and cancellation remain native ERPNext
operations and are not automated by this catalogue stage.

The pre-existing local mixed-version developer bench cannot complete native Sales Order
party loading; the endpoint reports that incompatibility instead of patching ERPNext core.
The release compatibility job must pass the full draft/submission integration on the exact
pinned Frappe/ERPNext pair before Stage 5 is considered complete.

### Retailer workflow

1. A salesperson opens **Salesperson Portal → Register Retailer**, completes the
   Retailer Application and saves it. The salesperson is set from the logged-in user.
2. Duplicate shop names, phone numbers, email addresses and GSTINs are rejected before
   submission, including common phone-prefix and letter-case differences.
3. A Clothing Manager, Clothing Business Administrator or System Manager opens
   **Retailer Applications**, then uses **Review → Approve** or **Review → Reject**.
4. Approval creates the standard ERPNext Customer, Contact and Address records and a
   native User Permission assigning that Customer to the salesperson. Rejection requires
   a reason. A reviewed application cannot be edited or reviewed again.
5. The salesperson records meetings from **Retailer Visits**. Choosing
   **Follow-up Required** requires a non-past follow-up date.

Salespeople only see their own applications and visits and can only select assigned
Customers. Managers can review all application and visit records. The workflow does
not duplicate ERPNext customer, address or contact masters.

**Validation limits:** automated app/database/recovery tests run locally and in CI.
Host-command tests simulate Proxmox. A complete install/update/reboot/restore on an
actual Proxmox host remains a required deployment trial; it has not been claimed
as completed. Initial HTTP access is intended for a LAN; configure HTTPS for a
public hostname.

MIT license for this application. ERPNext and Frappe retain their upstream licenses.
