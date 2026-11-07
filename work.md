# Clothing ERP roadmap and verified state

This is the canonical roadmap. The workspace-level work.md points here.

## Current foundation

- [x] Independent clothing_erp app, version 0.3.0; no upstream core source edits.
- [x] Real Frappe/ERPNext site and native launcher showing ERPNext, Clothing ERP, Framework.
- [x] Root redirects through login to the native launcher.
- [x] Three module-owned workspaces and five clothing roles.
- [x] Permission-aware native dashboard queries; empty data produces zero/empty results.
- [x] Remove preview-role authorization bypass and mock ERPNext HTTP clients.
- [x] Restrict operational Customers, Warehouses, Sales Orders, Delivery Notes and Pick Lists.
- [x] Native User Permissions for assignments; open ToDo required for operator pick lists.
- [x] Regression unit tests and real database permission tests.
- [x] Desktop launcher verified in Chromium against the real local site.
- [x] Local nginx/systemd setup script for port 80, prepared for a sudo run.
- [x] Stable deployment release pins; native services and nginx for an IP-based LXC.
- [x] Proxmox installer with preflight checks, new CT only, generated passwords, health check.
- [x] Portable single-file installer and tests for packaging and host command flow.
- [ ] Test a full installation/reboot/restore on an actual Proxmox host.
- [ ] Activate local port 80 using sudo (passwordless sudo is unavailable to this session).

The local pre-existing bench uses Frappe v16.55.2 and ERPNext develop 17.0.0-dev.
It was not downgraded. New LXC deployments pin ERPNext v16.54.0 with Frappe v16.55.2.
The local setup wizard was completed with the fictional TEST Clothing ERP Demo company.
The production installer leaves the wizard available for the operator's real configuration.
The previous Stage 2 checklist overstated completion: barcode scanning, follow-ups,
packing queues and commercial workflows remain unimplemented. No mock data stands
in for them now.

## Apparel features still to build

1. Salesperson catalogue: native Items/variants, style/collection/fabric/fit/season,
   images, size-colour matrix, stock visibility and permitted customer pricing.
2. Retailer management: registration, duplicate checks, approval, customer linkage,
   visit tracking and assignment management.
3. Salesperson ordering: matrix cart, authoritative pricing, discounts/credit checks,
   stock handling, idempotency, standard Sales Orders and lifecycle status.
4. Warehouse operations: assigned picking, barcode verification, shortages, packing,
   dispatch and standard Delivery Notes.
5. Retailer-direct requests: authenticated intake and approval before Sales Orders.
6. Realtime workflow notifications, reconciliation and operational reports.
7. Full permission audit and cross-user integration/concurrency coverage.
8. Release CI, reproducible release manifests and supported-host installation trials.
9. Backup restore drills, upgrades and rollback tooling.

All business rules and permission enforcement belong in this custom app. Use
standard ERPNext accounting, stock and commercial documents. Never add duplicate
ledgers or implement business behavior by modifying upstream core.

Verification: 22 app tests passed through the real site runner, 8 installer/package
tests passed, ShellCheck and Python static checks passed. Desktop/mobile Chromium
checks passed with all three icons, the Clothing ERP workspace and a connected
realtime socket through nginx. nginx configurations were checked on unprivileged
test ports; activating port 80 still requires the local sudo setup command.


## Release lifecycle pipeline

- [x] Separate upstream repositories and immutable, exact-commit release manifests.
- [x] GitHub Publish release form with optional independent Frappe/ERPNext pin updates.
- [x] Compatibility gate: app/security tests plus a fresh native database-backed install/build.
- [x] Publish completed draft artifacts/checksums/provenance, then expose a stable release.
- [x] Proxmox bootstrap installs a verified stable release instead of main source snapshots.
- [x] Dedicated per-release benches, Python/Node/Bench tools and assets; shared site data.
- [x] Root-owned lifecycle CLI: status/check/update/app-only/backup/recover/rollback.
- [x] Locked operations, maintenance gate, consistent DB/config/attachment recovery points.
- [x] Failed migration/frontend readiness restores previous code and data together.
- [x] Post-commit service failures preserve new job writes and retry service startup.
- [x] Manual rollback preserves a fresh backup of post-upgrade data before restoring old data.
- [x] Previous native-installer adoption without downgrading developer benches.
- [x] Release contract, archive safety, checksum, fault recovery and packaging tests.
- [x] Full GitHub compatibility workflow passed, including the exact staging builder and native SQL restore.
- [x] Published v0.3.0 and verified customer downloads of the source and portable installer.
- [ ] Real Proxmox install/update/reboot/restore trial remains outstanding.

The release updater manages the application stack's declared runtime versions.
Debian OS packages and the Proxmox host remain separate operator administration.
See docs/releasing.md and docs/operations.md for the simple maintainer/customer flows.

Additional verification: isolated native queue RDB snapshot and integrity checks passed.
Recovery points include pending jobs so abandoned migration jobs cannot run against
a restored old schema. Code, database, attachments, config and queue are recovered together.


Release completion evidence:
- Stable release: https://github.com/AviDhandhania/erp/releases/tag/v0.3.0
- Full release gate and publish: https://github.com/AviDhandhania/erp/actions/runs/42385415031
- 32 deployment/contract/recovery checks and 22 app/site checks passed.
- CI resolves runtime dependencies, then builds and tests a second fresh environment using the frozen locks.
- Published source checksums, dependency locks, portable payload and embedded checksum were verified through the customer download path.
- Isolated native MariaDB schema/data/config/attachment recovery and queue RDB integrity checks passed.
- Physical Proxmox guest creation, real systemd cutover, reboot and end-to-end guest rollback remain a deployment trial, not a completed claim.
