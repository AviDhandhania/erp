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
- [x] Direct local development server at `http://localhost:8000`, without nginx.
- [x] Stable deployment release pins; native services and nginx for an IP-based LXC.
- [x] Proxmox installer with preflight checks, new CT only, generated passwords, health check.
- [x] Portable single-file installer and tests for packaging and host command flow.
- [ ] Test a full installation/reboot/restore on an actual Proxmox host.
- [ ] Revisit nginx/port 80 only when deployment testing is explicitly requested.

The local pre-existing bench uses Frappe v16.55.2 and ERPNext develop 17.0.0-dev.
It was not downgraded. New LXC deployments pin ERPNext v16.54.0 with Frappe v16.55.2.
The local setup wizard was completed with the fictional TEST Clothing ERP Demo company.
The production installer leaves the wizard available for the operator's real configuration.
The previous Stage 2 checklist overstated completion: barcode scanning, follow-ups,
packing queues and commercial workflows remain unimplemented. No mock data stands
in for them now.

## Apparel features still to build

1. Complete the salesperson catalogue with style/collection/fabric/fit/season custom
   fields and customer-specific pricing context. The native catalogue foundation,
   images, filters, variant matrix, generic selling prices and stock visibility are done.
2. Extend retailer management with reassignment history, visit reporting and bulk
   administration. Registration, duplicate checks, approval, customer linkage,
   salesperson assignment and visit follow-ups are complete.
3. Salesperson ordering: matrix cart, authoritative pricing, discounts/credit checks,
   stock handling, idempotency, standard Sales Orders and lifecycle status.
4. Warehouse operations: assigned picking, barcode verification, shortages, packing,
   dispatch and standard Delivery Notes.
5. Retailer-direct requests: authenticated intake and approval before Sales Orders.
6. Realtime workflow notifications, reconciliation and operational reports.
7. Full permission audit and cross-user integration/concurrency coverage.
8. Release CI, reproducible release manifests and supported-host installation trials.
9. Backup restore drills, upgrades and rollback tooling.

## Stage 3 — salesperson catalogue

- [x] Role-restricted Clothing Catalogue Desk page linked from the salesperson workspace.
- [x] Responsive product cards and horizontally safe mobile variant tables.
- [x] Native ERPNext Item templates and Item Variants; no duplicate product model.
- [x] Colour-specific product templates/SKUs with Size as the only variant dimension.
- [x] Search, leaf-category and brand filters with bounded server-side pagination.
- [x] Product images, size attributes, stock UOM and aggregate on-hand visibility;
  colour is part of the product identity/SKU rather than a variant attribute.
- [x] Active generic selling-price lookup with future, expired, batch, supplier and
  customer-specific records excluded from the generic view.
- [x] Touch-friendly quantity selection with an in-browser draft units/value summary.
- [x] Backend role enforcement and native Item permission-aware template/variant queries.
- [x] Real database integration test covering template, variant attributes, Item Price and Bin.
- [x] Idempotent developer-only fictional seed command using submitted ERPNext stock receipts.
- [x] Locally bundled, attributed web photos for all fictional seed product families.
- [x] App-owned multi-image gallery on Item templates with ordered captions and a
  responsive click-to-view catalogue viewer.
- [x] Site-owned gallery uploads with reference-safe cleanup on row removal and a
  conservative scheduled orphan sweep; packaged release images are never deleted.
- [ ] Add clothing metadata fields after confirming the exact naming and reporting needs.
- [ ] Add an assigned-retailer context and ERPNext pricing-rule/customer-specific calculation.
- [ ] Persist selected quantities only as part of the separately tested Stage 5 cart/order flow.

The displayed stock is informational on-hand quantity, not a reservation or promise.
Stage 5 must recalculate prices, permissions and stock on the server when an order is
submitted. The catalogue intentionally creates no Sales Order or stock transaction.

## Stage 4 — retailer management

- [x] Permission-aware assigned-retailer directory API with search and bounded pagination.
- [x] Retailer detail API with contact fields and authorized recent Sales Order history.
- [x] Simplified Retailer Application DocType and submission form.
- [x] Duplicate detection across normalized shop name, phone, email and GSTIN.
- [x] Manager-only approval/rejection with immutable review results.
- [x] Approval creates native Customer, Contact and billing/shipping Address records.
- [x] Approval assigns the Customer through a native User Permission for the salesperson.
- [x] Retailer Visit records with outcomes, notes and required future follow-up dates.
- [x] Database integration coverage for application, approval, native records, assignment
  visibility and visit creation.

Stage 4 is complete. Retailer applications and visits are app-owned workflow records;
approved commercial masters remain native ERPNext documents. No ERPNext source was
modified.

All business rules and permission enforcement belong in this custom app. Use
standard ERPNext accounting, stock and commercial documents. Never add duplicate
ledgers or implement business behavior by modifying upstream core.

Verification: 41 app tests passed through the real site runner, 8 installer/package
tests passed, ShellCheck and Python static checks passed. Desktop/mobile Chromium
checks passed with all three icons and the Clothing ERP workspace. Current local
testing is intentionally direct on port 8000; nginx is deferred from this phase.


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
