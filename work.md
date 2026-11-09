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
- [x] Role-scoped launcher: operational sales/warehouse roles and their managers see
  Clothing ERP but not the full ERPNext app tile; system and Clothing Business
  administrators retain it.
- [x] Operational sales roles create drafts only through the Clothing ERP service and
  have no native Sales Order form/API permission; administrators review native orders.
- [x] Regression unit tests and real database permission tests.
- [x] Desktop launcher verified in Chromium against the real local site.
- [x] Direct local development server at `http://localhost:8000`, without nginx.
- [x] Local web workers reload app-owned Python changes automatically during development.
- [x] Stable deployment release pins; native services and nginx for an IP-based LXC.
- [x] Proxmox installer with preflight checks, new CT only, generated passwords, health check.
- [x] Portable single-file installer and tests for packaging and host command flow.
- [x] Frappe Insights analytics integration (v3.15.1) on the local site and as a
  required, exact-version component of every new release/LXC; operational users cannot
  see or call it, while administrators retain access.
- [ ] Test a full installation/reboot/restore on an actual Proxmox host.
- [ ] Revisit nginx/port 80 only when deployment testing is explicitly requested.

The local bench and new LXC deployments both use the tested pair ERPNext v16.54.0 and
Frappe v16.55.2. The upstream repositories remain unmodified; the local ERPNext checkout
was moved from an incompatible develop snapshot to the exact release tag.
The local setup wizard was completed with the fictional TEST Clothing ERP Demo company.
The production installer leaves the wizard available for the operator's real configuration.
The previous Stage 2 checklist overstated completion: barcode scanning, follow-ups,
packing queues and commercial workflows remain unimplemented. No mock data stands
in for them now.

## Apparel features still to build

1. Complete Sales Order submission: credit checks, stock/reservation policy, workflow
   approval, cancellation and lifecycle status. The matrix-to-native-draft adapter,
   server-authoritative pricing and duplicate-request protection are complete.
2. Complete exact pinned-release database coverage for Sales Order submission.
3. Warehouse operations: assigned picking, barcode verification, shortages, packing,
   dispatch and standard Delivery Notes.
4. Retailer-direct requests: authenticated intake and approval before Sales Orders.
5. Realtime workflow notifications, reconciliation and operational reports.
6. Full permission audit and cross-user integration/concurrency coverage.
7. Release CI, reproducible release manifests and supported-host installation trials.
8. Backup restore drills, upgrades and rollback tooling.

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
- [x] Add app-owned Item metadata fields for style code, collection, fabric, fit and
  season, with permission-aware catalogue filters, style-code search and fictional seed data.
- [x] Add an assigned-retailer context using native ERPNext item/Sales Order pricing for
  customer Price Lists, Pricing Rules, currency and UOM conversion.
- [x] Persist selected quantities through the separately tested Stage 5 native draft-order flow.

The displayed stock is informational on-hand quantity, not a reservation or promise.
The server never accepts catalogue rates or discounts. Draft creation rechecks the
customer and Items, then delegates commercial defaults and calculations to the native
Sales Order controller. Stock remains unreserved until a later native submission flow.

## Stage 5 — salesperson ordering

- [x] Convert catalogue matrix quantities into a standard draft Sales Order.
- [x] Send only customer, variant Item codes, quantities, delivery date and a request token;
  never trust browser prices, discounts, stock, commission or permission claims.
- [x] Revalidate the assigned enabled Customer and permission-visible, enabled Size-only
  Item variants on the server.
- [x] Delegate customer/company defaults, Price Lists, Pricing Rules, currency, taxes,
  maximum-discount validation and Sales Team commission calculations to ERPNext's native
  Sales Order controller.
- [x] Use a unique request token with ownership/customer checks so retries return the same
  draft instead of creating duplicate orders.
- [x] Provide a fictional retailer in the idempotent developer seed data so a manager or
  Administrator can exercise the catalogue order controls immediately.
- [x] Unit and static UI coverage for authorization, quantity validation, permission-aware
  Item selection, payload construction, duplicate retry and catalogue wiring.
- [x] Run local native draft creation and duplicate-request replay against the real database;
  repair a missing ERPNext-owned Contact field through ERPNext's supported installer.
- [x] Run native draft creation, salesperson UI routing and Administrator form loading on
  the exact pinned release pair; `SAL-ORD-2026-00008` was created from the catalogue and
  opened successfully in the native Administrator form without client errors.
- [x] Add an app-owned Clothing Orders directory and detail view with retailer/territory
  authorization, search, lifecycle filters and bounded pagination; operational workspace
  links no longer send sales users into the native ERPNext Sales Order interface.
- [x] Add manager-only, row-locked draft submission from Clothing Orders through the native
  Sales Order controller. Active ERPNext Workflows are detected and never bypassed; credit,
  authorization, commission, reservation and linked-document behavior remain ERPNext-owned.
- [x] Add an administrator-only native draft editing route plus manager-authorized,
  row-locked cancellation from Clothing Orders. ERPNext remains responsible for linked
  delivery checks, reservation cleanup and cancellation status; active Workflows are never
  bypassed.
- [ ] Add native submission coverage for credit limits, stock reservation, workflow and
  approval rules, Sales Person commission, concurrent stock changes and duplicate requests.
- [ ] Cover delivery/cancellation lifecycle and status reconciliation before closing Stage 5.

The local site had logged ERPNext's Contact-field migration without retaining ERPNext's
own `is_billing_contact` Custom Field. Migration now detects the missing ERPNext-owned
columns and reruns ERPNext's supported field installer instead of copying field definitions
or patching core. A real draft for two units produced `SAL-ORD-2026-00001` at INR 998, and
the same request token returned that order without duplication. Pinned-release submission
coverage remains open.

## Stage 4 — retailer management

- [x] Permission-aware assigned-retailer directory API with search and bounded pagination.
- [x] Retailer detail API with contact fields and authorized recent Sales Order history.
- [x] Simplified Retailer Application DocType and submission form.
- [x] Salesperson-only applications force the logged-in salesperson and server-owned
  Customer Group/Territory defaults; those master fields are hidden from intake users.
- [x] Duplicate detection across normalized shop name, phone, email and GSTIN.
- [x] Manager-only approval/rejection with immutable review results.
- [x] Approval creates native Customer, Contact and billing/shipping Address records.
- [x] Approval assigns the Customer through a native User Permission for the salesperson.
- [x] Retailer Visit records with outcomes, notes and required future follow-up dates.
- [x] Manager-only Retailer Visit Report with date, retailer, salesperson and outcome
  filters, outcome chart and operational summary counts; it is absent from salesperson
  navigation and rejects direct salesperson execution.
- [x] Manager-only Retailer Assignments page owned entirely by Clothing ERP; native Customer
  forms/lists contain no custom reassignment controls.
- [x] Responsive Retailer Assignments list layout with contained columns, functional 20/50
  row limits and pagination directly below the results instead of pinned to the viewport.
- [x] Territory-scoped Clothing Sales Managers can manage only Customers covered by their
  native Territory User Permissions; system/business administrators retain global scope.
- [x] Atomic single and bounded bulk reassignment services with sorted row locking,
  full-selection preflight and all-or-nothing request behavior.
- [x] Immutable Retailer Assignment History recording previous/new salesperson, reason,
  actor and timestamp for every actual assignment change.
- [x] Database integration coverage for application, approval, native records, assignment
  visibility, reassignment cache changes, immutable history and visit creation.

Stage 4 is complete. Retailer applications, visits and assignment history are app-owned
workflow/audit records; the live retailer assignment remains a native User Permission and
approved commercial masters remain native ERPNext documents. No ERPNext source was modified.

All business rules and permission enforcement belong in this custom app. Use
standard ERPNext accounting, stock and commercial documents. Never add duplicate
ledgers or implement business behavior by modifying upstream core.

Verification: 96 app tests passed through the real site runner and 34 installer/package
tests passed. Chromium checks verified that salesperson intake hides server-owned master
fields, draft creation stays on the Clothing ERP catalogue, and Administrator can open the
resulting native Sales Order. Desktop/mobile Chromium checks passed with all three icons,
the Clothing ERP workspace, the role-scoped Retailer Assignments page and the new Clothing
Orders directory/detail dialog without horizontal overflow. Current local testing is
intentionally direct on port 8000; nginx is deferred from this phase.

## ERPNext settings compatibility contract

- [x] Native ERPNext documents and their controllers remain authoritative for Customers,
  Contacts, Addresses, Items, prices, stock transactions and commercial documents.
- [x] Catalogue pricing honors the configured enabled Selling Price List, currency,
  Item Price validity, selling/UOM scope and excludes party-specific rows when no
  retailer context exists.
- [x] Catalogue stock aggregation respects Warehouse User Permissions without exposing
  warehouse-level quantities.
- [x] Retailer approval revalidates the assigned enabled Clothing Salesperson and uses
  native Customer, Contact, Address and User Permission documents.
- [x] Retailer reassignment replaces native User Permissions atomically, records immutable
  app-owned history, invalidates affected user permission caches and enforces manager
  Territory scope before reading or changing an assignment.
- [x] Gallery upload restrictions, privacy, storage and deletion use native File lifecycle
  checks; the app only removes confirmed unreferenced local uploads.
- [x] Current custom APIs retain native role and User Permission enforcement.
- [x] Stage 5 draft creation uses ERPNext's Sales Order validation and pricing-rule engine;
  native customer defaults, taxes, maximum discounts and Sales Team commission calculations
  remain authoritative, with no client-provided commercial values accepted.
- [ ] Stage 5 submission must validate credit limits, workflow/approval behavior,
  stock/reservation policy and concurrent changes on the exact pinned release pair.
- [ ] Stage 6 fulfilment must use native Pick List, Delivery Note, serial/batch and stock
  validation settings rather than changing inventory from custom status fields.

Only settings relevant to an operation are applied. A setting is either delegated to
the native ERPNext controller or explicitly handled and tested in this app; it must
never be silently reimplemented with conflicting semantics.


## Release lifecycle pipeline

- [x] Separate upstream repositories and immutable, exact-commit release manifests.
- [x] GitHub Publish release form with optional independent Frappe, ERPNext and Insights
  pin updates.
- [x] Compatibility gate: app/security tests plus a fresh native database-backed install/build.
- [x] Insights is mandatory in new manifests, dependency locking, fresh-install CI,
  installation and update health checks; a release cannot silently omit analytics.
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
