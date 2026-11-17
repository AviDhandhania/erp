# Clothing ERP roadmap and verified state

This is the canonical roadmap. The workspace-level work.md points here.

## Requirements intake — 2026-11-16

The field-sales operating model has changed materially and is documented in full at
[`docs/field-sales-operating-model.md`](docs/field-sales-operating-model.md). No workflow
The first access-and-classification implementation slice was completed later the same day.
The remaining workflow items below are still requirements, not completion claims.

Confirmed requirements now governing the next stages:

- [x] Classify every new retailer as exactly one of: **Buy & Sell**, **Buy & Sell — Stock
  Correction**, **SIS (Shop-in-Shop)** or **EBOC (Exclusive Brand Outlet)**.
- [x] Give administrators an editable global source for those classifications and their
  behavior. Prefer native ERPNext Customer Group leaves for classification and add
  Clothing ERP settings only for cadence/escalation behavior Customer Group cannot hold.
- [x] Replace/migrate the legacy Clothing Salesperson/Sales Manager access model with
  **ASM** and **RSM**. Only ASM, RSM and authorized administrators may access the Clothing
  ERP sales area; common salespeople must have no access.
- [x] Scope ASM and RSM retailer/application/order visibility to allotted native Territory
  User Permissions, including permitted descendant Territories.
- [x] Model the RSM-to-ASM supervisory relationship explicitly; an RSM normally handles
  3–4 ASMs and 200–250 shops.
- [x] For SIS, automatically assign quarterly stock-review obligations, require separate
  monthly general visits and support seasonal order-taking.
- [x] For Buy & Sell, require a monthly sample/order visit and a collection workflow based
  on ERPNext outstanding data in the stated 90–120 days from Delivery Date.
- [x] Route ASM-created retailer applications to that ASM's RSM. Support request-for-more-
  information, RSM completion of further details, RSM decision and initial limit setting.
- [x] Require an RSM visit to every in-scope shop within 80 days, notify the RSM as the
  deadline approaches, allow five grace days and notify administrators after day 85.
- [x] Capture RSM dealer review, financial situation, customer footfall and credit/exposure
  review on every RSM visit; route the RSM report to an administrator for review.
- [x] Route ASM visit reports to the supervising RSM and ASM-created Sales Orders to RSM
  approval without bypassing native ERPNext Workflow or Sales Order validation.
- [ ] Enforce the approved shop-stock exposure rule against stock already held plus new
  incoming stock. Keep this distinct from native receivables credit until ownership,
  valuation and document flow are confirmed.
- [x] Require administrator approval before a proposed credit/exposure-limit change is
  applied, with immutable before/after/proposer/approver/reason audit data.
- [ ] Preserve all application, visit, order, limit and escalation state transitions with
  server-side role/Territory checks, concurrency protection and audit history.

Known information still missing and explicitly deferred: Stock Correction and EBOC
cadences, store-stock ownership, stock valuation, calendar semantics, seasonal calendar,
RSM advance-warning timing, visit evidence, 90/120-day escalation behavior, capacity
hard limits, overrides, notification channels and legacy-data migration details.

## Warehouse and quality intake — 2026-11-16

The target warehouse, returns/refurbishment and seven-stage supplier quality model is
documented in full at
[`docs/warehouse-quality-operating-model.md`](docs/warehouse-quality-operating-model.md).
No workflow code was changed during this intake because billing, return accounting,
quality disposition and production-cycle details are still expected.

Confirmed requirements now governing the next warehouse/quality stages:

- [ ] Replace/migrate the legacy Warehouse Operator/Manager split with manager-only
  Clothing ERP warehouse access. Scope each manager using native Warehouse User
  Permissions; administrators retain oversight.
- [ ] Complete normal fulfilment from approved order through scan/pick, packing, the
  permitted billing-preparation step and recorded handoff to delivery using native Sales
  Order, Pick List, Delivery Note and Sales Invoice controllers.
- [x] Generate a delivery follow-up obligation for the responsible ASM, who contacts the
  retailer and records confirmation or issues.
- [x] Implement return intake by scanning the exact Item/Size/serial/batch against an
  authorized original transaction and prevent duplicate or excess returns.
- [x] Keep returned goods in a native quarantine Warehouse/location; require a quality
  report and passing result before movement to refining/refurbishment.
- [x] Track refurbishment work and move completed goods back to saleable stock only through
  submitted native ERPNext return/Stock Entry documents.
- [ ] Add an app-owned production quality cycle linked to native Supplier, Purchase Order,
  Items/styles and applicable Purchase Receipt/Quality Inspection records.
- [ ] Enforce the ordered quality stages: First Submission (fit sample), Second Submission
  (refit sample), Size Set Submission, Production Go Ahead, Inline Visits, Mid-line Visits
  and Final Inspection.
- [ ] Require a versioned report with appropriate native File photos for every quality
  check; preserve rejected/superseded evidence and correction history.
- [ ] At Production Go Ahead, present the combined prerequisite reports/photos to an
  administrator and block workflow advancement until the recorded approval.
- [ ] At Final Inspection, present the complete seven-stage report history/photos and both
  gate decisions to an administrator for final approval/rejection.
- [ ] Add bounded, permission-safe warehouse batch processing and the recommended scanning,
  exception, printing, package, return/refurbishment and quality-review conveniences from
  the operating-model document; bulk operations must expose every failure.
- [x] Preserve all fulfilment, handoff, follow-up, return, quality, refurbishment and gate
  transitions with server-side permissions, row locking, idempotency and audit history.

Known information still missing and explicitly deferred: billing submission authority,
delivery/carrier details, ASM follow-up timing, customer-return financial treatment,
failed-quality dispositions, post-refurbishment reinspection, refurbishment costing,
production-cycle granularity, stage checklists/sampling/photos, Inline/Mid-line visit count,
quality roles, gate correction/override policy, approval effects, notifications/SLAs and
legacy warehouse-operator migration.

## Repository audit — 2026-11-16

- The application-code baseline was clean at `60f9beb`. The local feature history remains
  ahead of `origin/main`; no history was rewritten and the reviewed Antigravity commits remain
  separately attributable in Git.
- The ERPNext checkout is clean. The India Compliance checkout is clean at its pinned
  release. No upstream source was changed during requirements capture.
- The Frappe checkout still has pre-existing local changes in `package.json` and
  `yarn.lock`; they were not created or modified by this work and must not be committed
  into Clothing ERP.
- The live local site was migrated on 2026-11-16 with Frappe, ERPNext, Clothing ERP,
  Insights and India Compliance installed. All 157 app/site tests pass after the
  Sales Territory Assignment (Territory -> ASM -> RSM) model, custom page restoration,
  complete removal of legacy Clothing Salesperson and Clothing Sales Manager roles,
  role-scoped link queries for ASM/RSM, in-page modal assignment inspection,
  Retailer Assignment History update with territory and ASM/RSM tracking, and
  Retailer Application automatic ASM and RSM population on territory selection.

## RSM-to-ASM supervision model — implemented 2026-11-16

- [x] Converted the app-owned `ASM Supervision` record into the authoritative **Sales
  Territory Assignment**: one leaf Territory → one ASM → one supervising RSM, with effective
  dates, status (`Active`, `Superseded`, `Cancelled`), notes and immutable audit tracking.
- [x] Supported multiple ASMs per supervising RSM; strictly enforced that an ASM has at most
  one active supervising RSM across overlapping effective date ranges.
- [x] Enforced enabled System User status and canonical Clothing ERP roles: ASM must have
  `Clothing Area Sales Manager` and RSM must have `Clothing Regional Sales Manager`.
  Directly rejected self-supervision.
- [x] The assignment now creates the required native Territory User Permissions for its ASM
  and RSM automatically. App assignments are authoritative; native permissions are synchronized
  mirrors for ERPNext compatibility and only app-created mirrors are removed on end/reassignment.
- [x] Enforced one active ASM per Territory and one active Territory per ASM while allowing an
  RSM to supervise multiple ASMs/Territories.
- [x] Restricted creation, update, and cancellation of supervision to authorized administrators
  (`System Manager`, `Administrator`, `Clothing Business Administrator`). Ordinary ASM and
  RSM users are denied modification server-side and kept out of framework user management.
- [x] Built atomic administrative reassignment service `assign_asm_supervision` with database
  row-locking (`FOR UPDATE`) on active supervision rows to eliminate race conditions.
  Existing active assignments are superseded with date cutoffs, fully preserving history.
- [x] Added `end_asm_supervision` service to safely cancel/end active supervision with recorded
  reasons without deleting audit records.
- [x] Implemented document permission hook (`asm_supervision_has_permission`) and list query
  conditions (`asm_supervision_conditions`):
  - RSM users can only view assignment records where they are the supervisor.
  - ASM users can only view their own supervision record.
  - System/business administrators retain global visibility.
- [x] Enforced supervision checks in Retailer Application review endpoints:
  - `approve` and `reject` verify that an RSM reviewer actually supervises the ASM who
    submitted the application and has access to the application Territory.
  - Applications from unassigned ASMs are visibly blocked from RSM review with clear guidance
    that an administrator must assign supervision.
  - Administrators retain global oversight and can approve/reject directly.
- [x] Retired per-retailer salesperson reassignment. The old route redirects to Sales Territory
  Assignments and every old mutation endpoint rejects calls server-side; historical records are
  retained as an archive.
- [x] Provided a clean native DocType UI and custom Desk page in Clothing ERP as
  **Sales Territory Assignments** under **Sales Operations** with server-side Link query filtering
  (`sales_role_user_query`) scoping ASM selections to `Clothing Area Sales Manager` and RSM
  selections to `Clothing Regional Sales Manager` across all dialogs and DocType forms.
- [x] Streamlined the Sales Territory Assignments page with in-page modal assignment inspection
  and actions, eliminating duplicate Desk tabs between the custom Page and native Form view.
- [x] Migration backfills a legacy record only when ASM/RSM permissions identify exactly one
  unambiguous leaf Territory; ambiguous legacy records are cancelled with an administrative
  migration note rather than guessing. Double migration is idempotent.
- [x] Development seed now creates two Territories, two ASMs, one RSM, business-admin and
  warehouse-manager test accounts, authoritative assignments and eight retailers spanning all
  four retailer types. Every run rotates and prints random test passwords.
- [x] Unit and database integration tests: 18 unit tests in `test_supervision.py`, 19
  workflow tests in `test_retailer_workflow.py` and `test_roles.py`, plus real-database
  integration tests in `test_site.py` (total 157 passing tests).
- [x] Updated **Retailer Assignment History** to reflect the new territory model:
  added `territory`, `previous_asm`, `new_asm`, `previous_rsm`, `new_rsm`, `reason`, `changed_by`,
  and `changed_on`. Automatically records immutable history events on `assign_asm_supervision` and
  `end_asm_supervision`. Added document permission hooks and query conditions for ASM and RSM scoping,
  and re-added the DocType link under Sales Operations workspace.
- [x] Added automatic ASM and RSM population in **Retailer Application**:
  selecting or inputting a `territory` immediately auto-fills the active `salesperson` (ASM) and `rsm`
  both client-side via `get_territory_assignment` and server-side in `validate()`. Made `territory`
  visible and required for all sales roles, and set `salesperson` and `rsm` as auto-populated read-only fields.

### Status of supervision and field sales stages

- **Implemented and tested behavior:**
  - Classify retailers into four canonical native Customer Groups.
  - Role migration to ASM/RSM with authoritative Territory assignments and synchronized native
    Territory User Permissions.
  - Retailer visibility and draft Sales Orders scoped to Territory.
  - App-owned, audited Territory → ASM → RSM model with effective dates, row-locking concurrency,
    unique active ASM per Territory, unique active Territory/supervisor per ASM, multi-ASM RSMs,
    automatic native permission synchronization, administrator-only mutations, query/document
    permission scoping and Retailer Application review gating.
- **Partially implemented behavior:**
  - Retailer intake: ASM draft application and RSM/admin approval/rejection are implemented;
    routing to a dedicated RSM inbox queue and request-for-more-information/resubmission states
    remain to be built in subsequent stages.
- **Unimplemented requirements:**
  - Stage 2: Route ASM retailer applications to their supervising RSM.
  - Stage 3: Request-for-more-information and resubmission states.
  - Stage 4: RSM completion of retailer commercial details and proposed credit limit.
  - Stage 5: Admin approval before credit-limit changes are applied.
  - Stage 6: ASM/RSM visit types, review chains and audit history.
  - Stage 7: SIS quarterly stock-review scheduling.
  - Stage 8: Monthly visit obligations.
  - Stage 9: RSM 80-day visit deadline, warnings and day-85 admin escalation.
  - Stage 10: Order approval through native ERPNext Workflow.
- **Unresolved business questions:**
  - Planning capacity guidance: 3–4 ASMs and 200–250 shops per RSM are currently unconstrained;
    whether hard limits or soft warnings are desired remains an open business decision.
  - Shop-stock exposure vs. accounting credit limit valuation and reconciliation.
  - Advance warning lead time before the 80-day RSM shop visit deadline.

## Field-sales access foundation — implemented 2026-11-16

- [x] Added canonical `Clothing Area Sales Manager` and `Clothing Regional Sales Manager`
  roles and replaced the legacy role literals on workspaces, pages, reports and DocTypes.
- [x] Added idempotent migration of legacy User roles and Role Profiles. Legacy supervision
  records are converted only when their native permissions identify one unambiguous leaf
  Territory; ambiguous records are cancelled for administrator review.
- [x] Changed retailer and Sales Order authorization from per-Customer visibility to
  server-enforced Territory visibility. ASM application/visit records remain owner-scoped;
  RSM review visibility is Territory-scoped.
- [x] Retired retailer-by-retailer salesperson reassignment. The active Territory assignment
  determines the responsible ASM and the RSM's supervisory scope.
- [x] Ordinary ERPNext `Sales User` accounts receive no Clothing ERP sales access; ASM/RSM
  users remain inside Clothing ERP and cannot browse framework User records.
- [x] Created a native `Clothing ERP Retailer Types` Customer Group parent with exactly four
  canonical leaf groups. Administrators edit these through native Customer Group; cadence
  settings still require the planned app-owned settings model.
- [x] Changed Retailer Application to require a canonical Retailer Type, auto-fill and lock
  the logged-in ASM, and resolve its Territory from the authoritative active assignment.
- [x] Approval creates the native Customer with that Customer Group classification. RSM
  approve/reject actions now perform document permission checks, preventing cross-territory
  review by guessing a document name.
- [x] Renamed the visible sales workspace label to **Field Sales** while preserving its
  stable internal route for existing bookmarks and upgrades.

## Current foundation

- [x] Independent clothing_erp app, version 0.3.0; no upstream core source edits.
- [x] Real Frappe/ERPNext site and native launcher showing ERPNext, Clothing ERP, Framework.
- [x] Root redirects through login to the native launcher.
- [x] Three module-owned workspaces and five current clothing roles, including ASM/RSM.
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
The previous Stage 2 checklist overstated completion: follow-ups, packing queues and
commercial workflows remain unimplemented. No mock data stands
in for them now.

## Apparel features still to build

1. Complete Sales Order submission: credit checks, stock/reservation policy, workflow
   approval, cancellation and lifecycle status. The matrix-to-native-draft adapter,
   server-authoritative pricing and duplicate-request protection are complete.
2. Complete exact pinned-release database coverage for Sales Order submission.
3. Warehouse operations: prebuilt serial/batch-bundle scanning, shortages, packing,
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
- [x] Keep assigned-retailer pricing available to operational salespeople without granting
  native Sales Order access: the trusted catalogue adapter performs explicit Customer,
  Price List, Item and Warehouse checks before invoking the pinned ERPNext calculation.
- [x] Add administrator-only Product Pricing in Clothing ERP so one rate can be previewed
  and applied across every enabled Size variant of a colour-specific template. The service
  creates or updates standard ERPNext Item Price records and refuses overlapping active
  prices rather than introducing template prices or a duplicate price model.
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

## Stage 6 — warehouse fulfillment

- [x] Add a role-scoped Clothing ERP Fulfillment Tasks page combining native Pick Lists
  and Delivery Notes with search, lifecycle filters, bounded pagination and responsive
  item-level detail dialogs.
- [x] Preserve native warehouse User Permissions, mixed-warehouse rejection and open-ToDo
  assignment rules by using permission-aware ERPNext document queries and explicit read
  checks rather than a parallel fulfillment model.
- [x] Remove direct Pick List, Delivery Note and Stock Entry links from the operational
  warehouse workspace so operators remain inside Clothing ERP.
- [x] Add row-specific SKU/item-barcode, Batch No and Serial No verification for
  authorized draft Pick Lists. Serialized items scan one at a time with duplicate
  prevention; batches must match their allocated row; every scan row-locks and rechecks
  the native task, prevents over-picking and saves through ERPNext's Pick List controller.
- [x] Add row-locked Pick List completion after every row is verified; active workflows
  are never bypassed, ERPNext's native submit controller owns all stock, serial/batch,
  reservation and reference validation, and assignments close only after submission.
- [x] Add manager-only shortage resolution for completely unpicked rows. A required
  reason is audited on the native Pick List; the row-locked operation delegates warehouse,
  batch and serial reallocation to ERPNext and verifies that scanned rows remain unchanged.
- [ ] Add incremental scanning for rows already backed by a prebuilt native Serial and
  Batch Bundle, partial-row shortage splitting, packing and native Delivery Note dispatch.

Stage 6 was designed for the previous Warehouse Operator/Manager split. The new
manager-only access model, billing preparation, delivery handoff, ASM follow-up and
return/quarantine/quality/refurbishment requirements materially expand and reopen it.
The existing row-locked native Pick List work remains a valid migration foundation, not a
complete implementation of the target warehouse workflow.

## Stage 4 — retailer management

- [x] Permission-aware assigned-retailer directory API with search and bounded pagination.
- [x] Retailer detail API with contact fields and authorized recent Sales Order history.
- [x] Simplified Retailer Application DocType and submission form.
- [x] ASM applications force the logged-in ASM and server-owned default assigned Territory;
  the ASM selects one canonical Retailer Type without needing Territory master access.
- [x] Duplicate detection across normalized shop name, phone, email and GSTIN.
- [x] RSM/admin approval/rejection with immutable review results and Territory checks.
- [x] Approval creates native Customer, Contact and billing/shipping Address records.
- [x] Approval preserves classification through the native Customer Group. Retailer
  visibility follows the active Sales Territory Assignment and its native Territory User
  Permission mirror; no per-Customer salesperson grant is created.
- [x] Retailer Visit records with outcomes, notes and required future follow-up dates.
- [x] RSM/admin Retailer Visit Report with date, retailer, ASM and outcome filters,
  outcome chart and operational summary counts; it is absent from ASM navigation and
  rejects direct ASM execution.
- [x] Replaced the former per-retailer assignment UI with administrator-owned Sales Territory
  Assignments. The old route redirects and its mutation APIs are retired server-side; the old
  immutable Retailer Assignment History remains readable as migration/archive data.
- [x] Atomic territory assignment/reassignment locks active ASM and Territory rows, preserves
  dated history, synchronizes native User Permissions and clears affected permission caches.
- [x] Database integration coverage for application, approval, native records, assignment
  visibility, reassignment cache changes, immutable history and visit creation.

The ASM/RSM access foundation, retailer classification, and explicit RSM-to-ASM supervision
model are now implemented and tested. Routing applications to dedicated supervisor queues,
scheduled obligations, multi-level review and credit/exposure approval remain open. Existing
retailer applications, visits and assignment history remain migration inputs; ASM responsibility
is derived from the active Territory assignment while native User Permissions mirror its scope. Approved commercial
masters remain native ERPNext documents. No ERPNext source was modified.

All business rules and permission enforcement belong in this custom app. Use
standard ERPNext accounting, stock and commercial documents. Never add duplicate
ledgers or implement business behavior by modifying upstream core.

Last full app verification on 2026-11-16: 153 app tests passed through the real site runner (9 integration tests + 144 unit tests). The last deployment run had 36 installer/package
tests passed. Chromium checks verified that salesperson intake hides server-owned master
fields, draft creation stays on the Clothing ERP catalogue, and Administrator can open the
resulting native Sales Order. Desktop/mobile Chromium checks passed with all three icons,
the Clothing ERP workspace, the Sales Territory Assignments list and the new Clothing
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
- [x] Retailer approval revalidates the assigned enabled ASM, canonical native Customer
  Group retailer type and assigned Territory, then uses native Customer, Contact and
  Address documents.
- [x] Sales Territory reassignment updates only app-managed native User Permissions atomically,
  preserves effective-dated app-owned history, invalidates affected caches and makes the active
  Territory → ASM → RSM record the row-scope authority.
- [x] Gallery upload restrictions, privacy, storage and deletion use native File lifecycle
  checks; the app only removes confirmed unreferenced local uploads.
- [x] Current custom APIs retain native role and User Permission enforcement.
- [x] Stage 5 draft creation uses ERPNext's Sales Order validation and pricing-rule engine;
  native customer defaults, taxes, maximum discounts and Sales Team commission calculations
  remain authoritative, with no client-provided commercial values accepted.
- [x] Stage 6 scanning reads native Item tracking settings and delegates Batch quantity,
  expiry, Serial No warehouse and Serial/Batch Bundle validation to ERPNext. Warehouse
  roles receive only the required tracked-stock reads; bundle mutation is gated to the
  authorized, row-locked Pick List submission context and direct mutation is denied.
- [ ] Stage 5 submission must validate credit limits, workflow/approval behavior,
  stock/reservation policy and concurrent changes on the exact pinned release pair.
- [ ] Stage 6 fulfilment must use native Pick List, Delivery Note, serial/batch and stock
  validation settings rather than changing inventory from custom status fields.

Only settings relevant to an operation are applied. A setting is either delegated to
the native ERPNext controller or explicitly handled and tested in this app; it must
never be silently reimplemented with conflicting semantics.


## Release lifecycle pipeline

- [x] Separate upstream repositories and immutable, exact-commit release manifests.
- [x] GitHub Publish release form with optional independent Frappe, ERPNext, Insights
  and India Compliance pin updates.
- [x] Compatibility gate: app/security tests plus a fresh native database-backed install/build.
- [x] Insights is mandatory in new manifests, dependency locking, fresh-install CI,
  installation and update health checks; a release cannot silently omit analytics.
- [x] India Compliance v16 is a mandatory, independently pinned component: fresh
  LXCs and compatibility CI download/install it, managed sites install it before
  migration when absent, exact commits and locks are verified, updater health/status/
  app-only rules include it, and operational users do not see its administrative tile.
- [x] Preserve upstream source while avoiding the pinned Frappe/Python 3.14 translation
  pool finalizer abort: the deployment builder uses Frappe's own asset and PO-to-MO
  functions with sequential locale compilation and is exercised by the release gate.
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


Previously published v0.3.0 release evidence (before the India Compliance work):
- Stable release: https://github.com/AviDhandhania/erp/releases/tag/v0.3.0
- Full release gate and publish: https://github.com/AviDhandhania/erp/actions/runs/42385415031
- CI resolves runtime dependencies, then builds and tests a second fresh environment using the frozen locks.
- Published source checksums, dependency locks, portable payload and embedded checksum were verified through the customer download path.
- Isolated native MariaDB schema/data/config/attachment recovery and queue RDB integrity checks passed.

Current unreleased validation evidence:
- All 10 audit findings resolved, tested, and verified across all applications.
- Architectural migration complete: `clothing_erp` application fully uninstalled, decoupled, and removed.
- The product consists strictly of 3 domain apps: `sales_erp`, `warehouse_erp`, and `quality_erp`.
- Double migration runs cleanly and idempotently on local site `clothing.local`.
- Complete test suites passing across all 3 domain apps and deploy suite:
  - `sales_erp`: 135/135 tests pass (23 integration + 112 unit).
  - `warehouse_erp`: 34/34 tests pass (7 integration + 27 unit).
  - `quality_erp`: 7/7 tests pass.
  - `deploy`: 29/29 tests pass.
- All JSON files valid, all Python compiles cleanly, all JavaScript passes syntax checks.
- The next stable release must pass the fresh two-stage native compatibility gate
  before its installer is published; v0.3.0 does not retroactively contain this work.
- Physical Proxmox guest creation, real systemd cutover, reboot and end-to-end guest rollback remain a deployment trial, not a completed claim.

## Three-App Architecture Migration: Complete Decoupling and Removal of `clothing_erp` Application — implemented 2026-11-17

Completed architectural migration away from the installed Frappe application named `clothing_erp`:
1. The final product consists strictly of three user-facing, installed custom Frappe applications:
   - `sales_erp` (wholesale apparel sales, interactive catalogue, draft ordering, product gallery lifecycle, portal routing, territory supervision, visits, credit limit approvals, and cadence obligations)
   - `warehouse_erp` (warehouse operations, scan-based fulfillment, Pick List shortage resolution, nested warehouse permissions, and serial/batch bundle locking)
   - `quality_erp` (7-stage supplier quality lifecycle, versioned inspection reports, and return quarantine)
2. `clothing_erp` application directory is completely removed. It is no longer an installed Frappe app, launcher tile, workspace, compatibility dependency, or owner of business functionality.
3. Decoupled web server and runtime:
   - Created neutral WSGI entry point `deploy/wsgi.py` (`deploy.wsgi:application` and `deploy.wsgi:create_development_application()`) for IP-based access without virtual host header requirement.
   - Migrated portal root and redirect routing into `sales_erp` (`sales_erp/www/clothing.py` and `clothing.html`), routing `/`, `/clothing-erp`, `/sales-erp`, `/salesperson`, `/warehouse`, and `/quality` to `/login?redirect-to=%2Fdesk%2Fdesktop` (for Guests) or `/desk/desktop`.
   - Seed data unified under `sales_erp.seed.seed_all()`.
   - Updated suite packaging in `pyproject.toml` to distribution `clothing-erp-suite` (version `0.3.1`) packaging `sales_erp`, `warehouse_erp`, `quality_erp`, and `deploy`.
4. Release lifecycle, installer, and CI parity:
   - Updated `deploy/release/lifecycle.py`: removed `clothing_erp` from `MANAGED_APPS` and `REQUIRED_SITE_EXTENSIONS`, registered `DEPRECATED_SITE_APPS = ("clothing_erp",)` so existing sites upgrading safely uninstall `clothing_erp` with data preserved.
   - Updated `deploy/stage-release.sh`, `deploy/install-debian.sh`, and `deploy/ci-integration.sh` to install and test only `erpnext`, `india_compliance`, `insights`, `sales_erp`, `warehouse_erp`, and `quality_erp`.
   - Updated `deploy/release/build.py` and `deploy/release/prepare.py` to use root `VERSION` file (`0.3.1`).
5. Verification:
   - Uninstalled `clothing_erp` from `clothing.local`.
   - Successfully executed double migrations (`bench --site clothing.local migrate` twice) with 0 errors.
   - Verified `bench --site clothing.local list-apps` shows strictly: `frappe`, `erpnext`, `insights`, `india_compliance`, `sales_erp`, `warehouse_erp`, `quality_erp`.
   - Ran all 135 tests in `sales_erp` (all passed).
   - Ran all 34 tests in `warehouse_erp` (all passed).
   - Ran all 7 tests in `quality_erp` (all passed).
   - Ran all 29 tests in `deploy/tests` (all passed).

## Architecture, security, and release stabilization — implemented 2026-11-17

Following comprehensive audit findings, the architecture, security boundaries, and release pipeline across the four-app suite were stabilized and verified:

1. **Canonical App and DocType Ownership**:
   - Resolved feature and schema duplication between `clothing_erp` and `sales_erp`.
   - `sales_erp` canonically owns all Sales DocTypes: `ASM Supervision`, `Clothing Product Image`, `Retailer Application`, `Retailer Assignment History`, `Retailer Credit Limit Request`, `Retailer Visit`, and `RSM Visit Obligation`.
   - `quality_erp` canonically owns `Supplier Quality Inspection` and `Return Quarantine`.
   - `clothing_erp` serves as the suite launcher, Desk routing layer, workspace navigator, and gallery manager, with explicit compatibility forwarding for legacy module paths.
   - All document hooks, scheduler events, and permission hooks are deduplicated and registered in exactly one authoritative app.

2. **Full CI and Production Lifecycle Parity**:
   - Updated `deploy/ci-integration.sh` and `.github/workflows/verify.yml` to install and test all 7 apps in production order: `erpnext`, `india_compliance`, `insights`, `clothing_erp`, `sales_erp`, `warehouse_erp`, and `quality_erp`.
   - Updated `deploy/stage-release.sh` and `deploy/release/lifecycle.py` (`MANAGED_APPS` and `REQUIRED_SITE_EXTENSIONS`) to guarantee that staging, update, backup, rollback, and recovery retain and manage all four apps.
   - Tested deployment update and recovery logic across 29 automated tests.

3. **Authoritative Territory → ASM → RSM Enforcement Everywhere**:
   - Replaced fragile dependencies on `assigned_documents("Territory")` and `assigned_documents("Customer")` in Sales APIs with `assigned_sales_territories()`.
   - Order listing, detail, submission, and cancellation derive scope authoritatively from active `Sales Territory Assignment` (`ASM Supervision`) records.
   - Verified that stale manual User Permissions grant zero sales access, ASMs see all retailers in their active territory, and ended/expired supervisions lose access immediately.

4. **Harden Retailer Visit Workflows**:
   - Evidence fields (`customer`, `salesperson`, `rsm`, `visit_date`, `visit_type`, `visitor_role`, `outcome`, `notes`, `follow_up_date`, `financial_assessment`, `customer_footfall`, `stock_condition`, `dealer_feedback`) are immutable once submitted.
   - ASMs are blocked server-side from altering submitted reports.
   - Modeled separate Administrator review of RSM visits (`Reviewed by Admin`), rejecting self-reviews by RSMs.
   - Periodic reviews mandate and validate required fields: `financial_assessment`, `customer_footfall`, `stock_condition`, `dealer_feedback`.
   - Row-locking (`FOR UPDATE`) on review transitions prevents race conditions.

5. **Harden Retailer Credit Limit Requests**:
   - Transition endpoints (`approve_credit_limit_request`, `reject_credit_limit_request`) enforce POST-only methods and database row-locking.
   - Mandatory non-empty rejection reasons are required server-side.
   - Dynamic currency resolution from ERPNext Company avoids hardcoded symbols.
   - Detects live customer credit limit modifications occurring while the request was pending and blocks stale approval.
   - Approved or rejected requests are immutable.

6. **Structured Cadence Obligations**:
   - Created DocType `RSM Visit Obligation` with deterministic `cycle_id` (`{customer}-{cycle_start}`).
   - Replaced fragile text matching with structured obligation records tracking status, advance warnings, grace periods, and escalation state.

7. **Manager-Only Warehouse Model**:
   - Supported nested source warehouses cleanly by recursively traversing child and descendant warehouses.
   - Row-locked Serial and Batch Bundles (`FOR UPDATE`) during Pick List completion to eliminate mutation races during native submission.
   - Enacted audited migration path (`migrate_warehouse_operators_to_managers`) for legacy operator accounts to transition safely to `Clothing Warehouse Manager`.

8. **Quality ERP Hardening**:
   - All mutation endpoints are POST-only (`@frappe.whitelist(methods=["POST"])`) with write permission validation and database row-locking.
   - Enforced strict 7-stage quality lifecycle ordering (Fit Sample → Refit Sample → Size Set → Production Go Ahead → Inline Visits → Mid-line Visits → Final Inspection). Completing later stages is blocked if prerequisite stages are unapproved.
   - Added versioning and revision tracking for inspection reports (`revision`, `supersedes`, `revise_quality_inspection`).
   - Modeled administrative review bundles (`get_quality_review_bundle`) assembling prior reports, photographs, and readiness gates for Production Go Ahead and Final Inspection.

9. **Authorization and Correctness Gaps Resolved**:
   - `get_territory_assignment` strictly enforces supervisory scope for non-administrators.
   - `find_duplicates` detects collisions across all active application states (`Pending`, `Pending Info`, `Resubmitted`, `Approved`).
   - Single maintained navigation and sidebar scoping.

10. **Reconciled Documentation**:
    - Aligned `README.md`, `work.md`, `AGENTS.md`, and `docs/architecture.md` with multi-app architecture and current verified state.
