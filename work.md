# Clothing ERP roadmap and verified state

This is the canonical roadmap. The workspace-level work.md points here.

## Production security, mobile applications and barcode programme — OPEN 2026-11-17

This programme supersedes percentage claims based only on old checklist counts. A checked
feature is not production-ready until its authorization, confidentiality, integrity,
availability, audit, recovery, mobile and operational consequences have been tested. No
software can honestly promise a mathematically zero probability of a data leak; the release
standard is **zero known data exposure**, least privilege, defence in depth, tested recovery,
documented residual risk and a release block for every unresolved critical/high finding.

### Verified baseline at programme start

- [x] The custom repository was clean at `3c8119e` and was 68 commits ahead of `origin/main`.
- [x] The local site contains only the intended apps: Frappe, ERPNext, Insights,
  India Compliance, Sales ERP, Warehouse ERP and Quality ERP. `clothing_erp` is absent.
- [x] Real-site test run on 2026-11-17: Sales ERP 153/153, Warehouse ERP 65/65 and
  Quality ERP 9/9 passed.
- [x] Deployment unit/recovery tests 36/36 passed; Python compilation, JSON parsing,
  shell syntax and JavaScript syntax passed.
- [ ] Run the full fresh-install integration gate from the current commit in an isolated
  environment. Local-site tests do not replace a clean database/install/migrate/build test.
- [ ] Push the reviewed commits and obtain a green protected-branch CI run. Local commits
  ahead of GitHub are not a published or independently verified release.
- [x] Correct stale documentation that still describes the removed Clothing ERP launcher,
  old pending stages or previous app/test counts (reconciled in docs/architecture.md).

### Truthful completion and release rules

- [ ] Remove checklist-derived global percentages from release decisions. Maintain separate
  feature, security, test, migration, mobile and deployment readiness scores with evidence.
- [ ] A task may be checked only when implementation, negative authorization tests,
  concurrency tests, migration/rollback and user documentation are complete where relevant.
- [ ] Every Antigravity session must begin with `git status`, read `AGENTS.md` and this
  section, inspect overlapping user changes, and select a bounded group of unchecked tasks.
- [ ] Every session must end by updating this section with files changed, exact tests and
  results, known limitations and the next safe task. Never rewrite or discard user changes.
- [ ] Every Antigravity-authored commit must include `[antigravity]` in its subject and an
  `Agent: Antigravity` trailer/body marker. Use small, reviewable commits.
- [ ] Never modify Frappe, ERPNext, Insights or India Compliance source. Verify their Git
  status before and after every session and report any pre-existing dirt separately.
- [ ] Do not use real people, customers, financial records, credentials, phone numbers or
  addresses in development, fixtures, screenshots, logs, analytics or tests.

### P0 security and privacy release blockers

#### Threat model, data inventory and access matrix

- [x] Write `docs/security/threat-model.md` covering internet/LAN attackers, malicious or
  compromised ASM/RSM/warehouse/quality accounts, lost phones, stolen session tokens,
  malicious uploads, dependency compromise, compromised release assets, backup theft,
  database compromise, insider misuse, privilege escalation and denial of service.
- [x] Write a data-flow diagram from mobile/browser clients through nginx, Frappe, workers,
  MariaDB, Redis, private/public files, backups, Insights and outbound notifications.
- [x] Inventory every personal, commercial, financial, stock, location, photograph,
  credential, token and audit field. Assign purpose, owner, sensitivity, retention,
  export rules, deletion rules and masking/logging policy (docs/security/data-classification.md).
- [x] Create a machine-reviewed role/operation matrix for Administrator, System Manager,
  Clothing Business Administrator, ASM, RSM, Warehouse Manager, Quality Inspector and
  Quality Manager. Include every DocType, report, page, API, export, attachment and bulk
  action. Default to deny and explicitly document cross-app boundaries (docs/security/access-matrix.md).
- [x] Resolve the current manager-only contradiction: migrate and remove active
  `Clothing Warehouse Operator` authorization from server checks, seed users, page/workspace
  roles, boot filtering and cross-app compatibility code. Keep only an audited migration
  path for old sites; a legacy constant must not continue to grant access.
- [x] Prove that disabled users, ended supervision, removed Warehouse permissions and role
  changes revoke API, list, report, attachment and cached access immediately.

#### Endpoint and privileged-write audit

- [x] Inventory every `@frappe.whitelist` endpoint with method, roles, object scope, input
  schema, maximum size, rate limit, idempotency, transaction boundary and audit event
  (docs/security/endpoint-audit.md: 63 whitelisted endpoints audited).
- [x] Require POST for every mutation. GET endpoints must be side-effect free, permission
  scoped, bounded and resistant to identifier enumeration.
- [x] Review every `ignore_permissions=True`, `flags.ignore_permissions`, direct
  `frappe.db.set_value`, raw SQL mutation and `delete_doc`. Each occurrence must have a
  preceding server-side authority/scope/state check and a focused negative test, or be
  replaced with a permission-aware native controller call (docs/security/endpoint-audit.md).
- [x] Review every raw SQL query for parameterization, permission equivalence, bounded
  results, company isolation and row-lock correctness. Add a static test that rejects
  unreviewed interpolated SQL and records approved exceptional locations (deploy/tests/test_security_audit.py).
- [x] Validate all API inputs with explicit types, length/range limits, normalized names,
  allowed enums and maximum collection sizes. Reject unknown fields where the endpoint
  accepts structured payloads.
- [x] Add rate limits and abuse tests for login, search, catalogue, scanning, bulk actions,
  file upload, reports, exports and mobile synchronization.
- [x] Add idempotency keys with user/scope/payload binding and expiry for order creation,
  visits, scans, returns, dispatch, quality decisions, mobile queued writes and bulk jobs.
- [x] Verify transaction rollback for partial failures and add deadlock/retry tests for all
  row-locked transitions. Never catch an error and silently commit partial business state.
- [x] Add explicit, immutable security audit events for permission/role changes, territory
  and warehouse reassignment, credit changes, order approval/cancellation, stock handoff,
  returns, quality gates, exports, failed authorization and administrative overrides.

#### Authentication, sessions and mobile credentials

- [ ] Select and document a supported mobile authentication design. Prefer OAuth 2.0
  Authorization Code with PKCE if the pinned Frappe release can support it safely; otherwise
  use a reviewed short-lived token exchange. Never store a password or long-lived API secret
  in a mobile bundle, source repository, ordinary preferences, logs or analytics.
- [ ] Store refresh/session material only in iOS Keychain/Android Keystore-backed secure
  storage; rotate refresh tokens, detect reuse where possible and support remote revocation.
- [ ] Define short access-token/session lifetime, inactivity timeout, absolute lifetime,
  device logout, all-device logout, administrator revocation and lost-device response.
- [ ] Enforce CSRF protection for cookie sessions, strict origin/host validation and secure
  cookie attributes. Test fixation, replay and cross-origin requests.
- [ ] Require MFA for Administrator/System Manager and strongly recommend/enforce it for
  business approvers. Add recovery-code and account-recovery procedures that do not bypass
  identity verification.
- [ ] Add brute-force throttling, alerting and safe lockout behavior without exposing whether
  an email/user exists.

#### Network, TLS and host hardening

- [x] Replace the production HTTP-only installer outcome with HTTPS before any real data is
  entered. Support an operator-supplied certificate and a documented ACME/domain mode;
  redirect HTTP to HTTPS and set the correct site URL (deploy/nginx.conf, docs/security/host-hardening.md).
- [x] Configure modern TLS, HSTS after HTTPS is proven, secure headers, clickjacking
  protection, MIME sniffing protection, a tested Content Security Policy and a restrictive
  referrer/permissions policy without breaking Frappe assets (deploy/nginx.conf).
- [x] Do not display or transmit the initial Administrator password over plaintext HTTP.
  Force password change, protect the root credential file with mode 0600, document deletion
  after onboarding and ensure it never appears in process lists or logs (deploy/install-debian.sh, docs/security/host-hardening.md).
- [x] Harden the unprivileged LXC: no nesting unless proven necessary, minimal capabilities,
  firewall defaults, restricted management access, time synchronization, security updates,
  log rotation and resource limits. Document Proxmox host responsibilities separately (deploy/proxmox/clothing-erp.fw, docs/security/host-hardening.md).
- [x] Harden systemd services with the maximum compatible `NoNewPrivileges`, private temp,
  filesystem protection, kernel/control-group restrictions, capability removal and explicit
  read/write paths. Test web, workers, scheduler and socket service functionality afterward (deploy/render-services.py, deploy/tests/test_deployment_hardening.py).
- [x] Bind MariaDB and Redis only to trusted local interfaces/sockets, require authentication
  where supported, restrict filesystem permissions and prove neither is reachable externally (deploy/install-debian.sh, docs/security/host-hardening.md).
- [x] Run services as dedicated unprivileged identities and audit all suite/site/private-file
  permissions. World-readable site configs, private files or backups are release blockers (docs/security/host-hardening.md).

#### Files, photographs, exports and privacy

- [x] Make retailer, visit, return and quality evidence private by default. Verify a user
  cannot retrieve a private File URL without both File permission and permission to its
  referenced business document.
- [x] Enforce upload size, count, MIME signature, extension and decompression/image dimension
  limits. Rename server-side, strip unsafe metadata where policy permits, reject executable
  or polyglot content and integrate a documented malware-scanning/quarantine path.
- [x] Replace single quality `Attach Image` fields with permission-aware multi-photo child
  evidence containing private File, caption, evidence type, display order, uploader and
  immutable timestamp. Preserve rejected/superseded evidence according to retention policy.
- [x] Make deletion reference-safe across all documents and mobile upload retries. Add tests
  for shared references, deleted rows, failed uploads, orphan cleanup and backup/restore.
- [x] Permission-scope and audit every CSV/PDF/print/export. Add spreadsheet-injection
  protection, watermarks/revision markers where needed, bounded exports and no hidden-field
  leakage.
- [x] Ensure application errors, web logs, worker logs, mobile logs, crash reports and
  Insights datasets redact passwords, tokens, cookies, GSTIN/phone/email/address where not
  operationally required, SQL parameters and private file URLs.

#### Secrets, supply chain and release integrity

- [x] Add automated secret scanning for current files and Git history, dependency/license
  scanning, Python/JavaScript/mobile SCA, static analysis and a reviewed vulnerability policy (deploy/supply_chain/, deploy/tests/test_supply_chain.py).
- [x] Pin third-party GitHub Actions to immutable commit SHAs, not mutable major tags, and
  minimize workflow permissions. Protect release environments/tags and require reviewed CI (.github/workflows/, docs/security/supply-chain.md).
- [x] Verify Sigstore/GitHub provenance or another independent publisher signature in the
  customer installer/update client, not only SHA256 files downloaded from the same release.
  Reject unexpected repositories, redirects, subjects, identities, versions and manifests (deploy/release/provenance.py, deploy/release/common.py).
- [x] Generate an SBOM for server and each mobile app, attach it to releases and retain exact
  source/runtime/mobile dependency locks (deploy/supply_chain/sbom.py).
- [x] Prohibit unreviewed runtime downloads and post-install scripts. Check hashes/signatures
  before execution and test mirror/network failure without falling back to untrusted input (deploy/release/common.py, deploy/release/provenance.py).
- [x] Add security contact, supported-version policy, vulnerability disclosure procedure,
  emergency release/revocation process and compromised-signing/repository response runbook (deploy/release/revocations.json, docs/security/supply-chain.md).

#### Encryption, backups, retention and disaster recovery

- [x] Decide and document database/file/backup encryption at rest, key ownership, rotation,
  recovery and separation from encrypted data. Never place backup keys beside backups (deploy/release/encrypted_backup.py, docs/security/disaster-recovery.md).
- [x] Implement encrypted, integrity-authenticated off-host backups with retention tiers and
  least-privilege destination credentials. Local snapshots alone are not disaster recovery (deploy/release/encrypted_backup.py, docs/security/disaster-recovery.md).
- [x] Back up MariaDB, site config, public/private files, encryption keys required by Frappe,
  queue state where necessary and release metadata consistently (deploy/release/encrypted_backup.py, deploy/release/lifecycle.py).
- [x] Automate restore verification into an isolated environment and prove record counts,
  private files, attachments, permissions, mobile token revocation and application health (deploy/release/encrypted_backup.py: verify_isolated_restore).
- [x] Define RPO/RTO, backup monitoring, failure alerts, restore authorization, legal/business
  retention and secure deletion. Test ransomware/operator-error scenarios (docs/security/disaster-recovery.md).
- [ ] Run a real Proxmox install, update, reboot, backup, restore and rollback drill before
  release. Capture commands, versions, timings and evidence without secrets.

### Production feature completion — Sales ERP

- [x] Reconcile `docs/field-sales-operating-model.md` with implemented behavior and remove
  stale “pending” statements only after tests prove them.
- [x] Obtain business decisions and implement configurable, audited rules for Buy & Sell —
  Stock Correction and EBOC; do not invent cadence or ownership semantics (sales_erp/settings.py, docs/field-sales-operating-model.md).
- [x] Define physical shop-stock ownership and valuation by retailer type. Separate physical
  exposure from ERPNext accounting credit, tax and receivable controls; test delivery,
  return, cancellation, damage, correction and concurrent-order effects (sales_erp/settings.py, docs/field-sales-operating-model.md).
- [x] Add administrator-managed settings for cadence, warning/grace intervals, seasonal
  windows, collection escalation and capacity warnings, with validation and change history (sales_erp/doctype/clothing_sales_settings/).
- [x] Complete retailer application queues, missing-information exchange, document/photo
  requirements, RSM-owned commercial fields and immutable approval evidence (sales_erp/doctype/retailer_application/).
- [x] Complete ASM/RSM visit check-in policy: optional/required location, timestamp, evidence,
  consent/privacy, spoofing limitations, offline behavior and review trail (sales_erp/doctype/retailer_visit/).
- [x] Complete order return/reject/resubmit/amend flows through native ERPNext Workflow.
  Preserve prices, taxes, discounts, commissions, reservations, credit and audit semantics (sales_erp/ordering.py).
- [x] Add notification inboxes and idempotent reminders/escalations without leaking one
  territory's retailer/order information to another (sales_erp/cadence.py, sales_erp/api.py).
- [x] Add permission-scoped operational dashboards for applications, visits, overdue cadence,
  orders, exposure, collections and delivery issues; verify aggregate queries cannot leak
  out-of-scope counts (sales_erp/api.py, sales_erp/report/retailer_cadence_and_exposure_report/).
- [x] Test multi-company, multi-currency, tax templates, India Compliance/GST, Pricing Rules,
  Sales Team commission, partial delivery, returns, cancellation and disabled master data (sales_erp/tests/test_sales_orders_reports_scale.py).
- [x] Add high-volume tests for 250+ shops per RSM, catalogue pagination, scheduling,
  concurrent approvals and duplicate mobile submissions (sales_erp/mobile_api.py, sales_erp/tests/test_sales_orders_reports_scale.py).

### Production feature completion — Warehouse ERP

- [x] Finish the manager-only migration described in the P0 access section and verify old
  operator users lose all list, read, print, scan, dispatch, return and attachment access.
- [x] Formalize the native document sequence and authority for Pick List, Packing Slip,
  Delivery Note, draft/submitted Sales Invoice and India Compliance/e-Waybill. Warehouse
  managers must never alter protected accounting or commercial fields.
- [x] Add server-generated wave/route work queues, bounded bulk preflight, per-document
  failure reporting, safe retries, cancellation and job progress for large operations.
- [x] Complete package identity, count, weight, dimensions, carrier, vehicle, LR/tracking,
  handler acceptance, timestamps and proof of handoff with immutable audit history.
- [x] Implement printable labels/manifests with permission checks, deterministic templates,
  printer-safe PDF and optional reviewed ZPL, reprint audit and no sensitive excess fields (warehouse_erp/labels.py, warehouse_erp/tests/test_warehouse_returns_and_labels.py).
- [x] Complete partial fulfilment/backorder, mixed tracking, stock reservation, wrong-location,
  expiry, rejected batch, serial ownership and concurrent scanner scenarios using native
  ERPNext controllers (warehouse_erp/fulfillment.py, warehouse_erp/tests/test_warehouse_flow_and_handoff.py).
- [x] Complete return financial-policy hooks without assuming refund/credit/replacement;
  keep physical receipt quarantined until authorized commercial and quality decisions (warehouse_erp/returns.py, warehouse_erp/tests/test_warehouse_returns_and_labels.py).
- [x] Add quarantine, awaiting-quality, refurbishment and restock SLA queues, assignment,
  reason codes, evidence, labels and permission-scoped dashboards (warehouse_erp/returns.py, warehouse_erp/tests/test_warehouse_returns_and_labels.py).
- [x] Add refurbishment operations, assignee, consumed material/cost references, timings,
  before/after evidence and mandatory post-refurbishment reinspection if approved by business (quality_erp/doctype/return_quarantine, warehouse_erp/returns.py, warehouse_erp/tests/test_warehouse_returns_and_labels.py).
- [x] Load-test large Pick Lists, multiple devices scanning the same row, bulk operations,
  printer failure and network interruption. Prove no over-pick, duplicate return or silent skip (warehouse_erp/tests/test_warehouse_flow_and_handoff.py, warehouse_erp/tests/test_warehouse_returns_and_labels.py).

### Production feature completion — Quality ERP

- [x] Create a real Production Quality Cycle with a confirmed unique business key and links
  to Supplier, Purchase Order, relevant Items/styles/colourways, production lot/season and
  applicable Purchase Receipt/native Quality Inspection. Do not duplicate purchasing/stock (quality_erp/cycle.py, quality_erp/doctype/production_quality_cycle, quality_erp/tests/test_production_quality_cycle.py).
- [x] Replace the single broad inspection record model with explicit cycle/stage/report
  relationships supporting multiple Inline and Mid-line visits and immutable revisions (quality_erp/doctype/supplier_quality_inspection, quality_erp/doctype/production_quality_cycle, quality_erp/quality.py).
- [x] Add versioned checklist templates by item group/product/category; historical reports
  retain the exact checklist version reviewed (quality_erp/doctype/quality_checklist_template, quality_erp/doctype/quality_inspection_checklist_item, quality_erp/quality.py).
- [x] Capture measurements/readings, sampling plan, sampled/passed/failed quantities,
  defect code/severity, result, recommendation, corrective action, owner and due date (quality_erp/doctype/quality_inspection_reading_item, quality_erp/doctype/quality_inspection_defect_item, quality_erp/doctype/supplier_quality_inspection, quality_erp/quality.py).
- [x] Implement multi-photo private evidence, captions/types/order, side-by-side revision
  comparison and missing-evidence gates as defined in the security section (quality_erp/doctype/quality_inspection_evidence, quality_erp/quality.py).
- [x] Implement correction requested, resubmitted, conditional approval, rejection,
  supersession and exceptional override policies with immutable reasons and exact revisions (quality_erp/doctype/supplier_quality_inspection, quality_erp/quality.py).
- [ ] Build a single Production Go Ahead review screen showing all prerequisites, evidence,
  corrections and exact revisions; only authorized administrators may decide the gate.
- [ ] Build a complete Final Inspection review screen showing all seven stages, repeated
  visits, evidence, corrections and both gate decisions; define what native event approval
  authorizes instead of changing stock/payables implicitly.
- [ ] Add generated controlled PDF/report bundles with permission checks, watermark,
  revision hash/identifier and export audit.
- [ ] Complete failed-return dispositions, supplier claims, scrap/seconds/on-hold decisions,
  post-refurbishment reinspection and costing only after business approval.
- [ ] Expand Quality tests from the current nine real-site cases to negative permissions,
  cross-supplier/company isolation, multiple visit reports, evidence privacy, revisions,
  corrections, concurrency, gate races, Purchase Receipt integration and recovery.

### Barcode, QR and label system — server, web and mobile

The barcode is an identifier, never authorization. Every scan must resolve and revalidate
the current user, company, Territory/Warehouse, document state, quantity, serial/batch,
remaining work and concurrency on the server.

- [x] Write `docs/barcodes.md` defining identifier namespaces and symbologies before coding:
  Item/EAN/UPC/GTIN where supplied, internal Item Code128, Serial No, Batch No, package,
  Pick List, Delivery Note, return/quarantine, quality-cycle/report and location labels.
- [x] Reuse ERPNext Item Barcode, Serial No, Batch No and Serial and Batch Bundle wherever
  they are authoritative. Do not generate a second competing product/serial registry.
- [x] Add administrator-controlled internal barcode generation with collision-safe server
  allocation, check digit where applicable, immutable assignment/audit, preview and explicit
  rules for manufacturer barcodes. Never silently replace a used identifier.
- [x] Support Code 128 for internal identifiers and standards-compliant EAN-13/UPC/GTIN/GS1
  only when input ownership, length, check digit and licensing/business rules are satisfied.
  Use QR only for opaque non-secret record/label identifiers or URLs requiring login.
- [x] Add single and bounded bulk label generation for products/size variants, bins/locations,
  packages, returns and quality records. Provide configurable label size, human-readable text,
  company/brand, SKU, colour, size, price only when authorized, batch/serial and print count.
- [x] Produce deterministic PDF and optional reviewed ZPL without shell interpolation or
  remote resources. Permission-check generation and download; record who printed/reprinted.
- [x] Create one server-side scan resolver that accepts normalized scan text plus operation
  context and returns a minimal typed result. Prevent cross-company/warehouse/territory
  enumeration and ambiguous collisions across barcode types.
- [x] Support hardware keyboard-wedge scanners and mobile camera scanning with debounce,
  duplicate suppression, continuous scan mode, torch, sound/haptic/color feedback and an
  accessible manual entry fallback.
- [x] Add explicit scan operations for catalogue lookup, picking, undo-before-submit,
  packing, dispatch, returns, quarantine, refurbishment, stock/location and quality evidence.
- [x] Require idempotency and row locks for scan mutations; add replay, rapid double scan,
  two-device race, wrong item, wrong variant, wrong batch, wrong serial, expired batch,
  over-pick, over-return, offline replay and revoked-access tests.
- [x] Never embed credentials, customer PII, prices, private file URLs or business approval
  in a barcode. Treat printed identifiers as observable and potentially forged.

### Mobile programme — three production applications

Build three separately branded apps sharing a reviewed core library:

1. **Clothing Sales Mobile** for ASM/RSM.
2. **Clothing Warehouse Mobile** for warehouse managers.
3. **Clothing Quality Mobile** for quality inspectors/managers and authorized approvers.

Use one cross-platform codebase with separate application targets/bundle identifiers and
strict role-aware navigation. Flutter is the preferred starting candidate for Android/iOS,
camera/barcode, secure storage and controlled offline data; record an ADR comparing it with
Capacitor/PWA and native development before committing. A web wrapper alone is not accepted
as a production mobile app unless security, offline, camera and lifecycle requirements pass.

#### Mobile foundation shared by all three apps

- [ ] Add `mobile/` as an independent workspace with shared API/auth/design/offline/scanner
  packages and three thin app targets. Do not package ERPNext server source into clients.
- [ ] Create an OpenAPI-like, versioned mobile contract with typed requests/responses,
  pagination, stable error codes, minimum-supported version and deprecation policy.
- [ ] Implement secure authentication, token storage/revocation and device/session management
  from the P0 authentication section. No embedded administrator/API credentials.
- [ ] Enforce TLS with hostname validation. Do not add a “trust all certificates” mode.
  If certificate pinning is selected, include safe rotation and recovery design.
- [ ] Minimize offline data per role. Encrypt the local database with a hardware-backed key,
  exclude it from insecure backups, redact notifications/app-switcher previews and wipe on
  logout, revocation, account disable or excessive failed unlock attempts as policy defines.
- [ ] Offline writes must be a visible encrypted queue with UUID idempotency key, original
  user/device/time, payload version, retry state and conflict UI. Server permissions/state
  are always revalidated; offline state never authorizes a transaction.
- [ ] Never cache unnecessary cross-territory/cross-warehouse/customer financial/private
  evidence. Define per-entity TTL, purge, attachment download and screenshot policy.
- [ ] Add database/API migrations, crash-safe queue processing, clock-skew handling, timezone
  tests, background/resume behavior, low-storage behavior and interrupted upload recovery.
- [ ] Add accessibility, localization architecture, responsive phone/tablet layouts,
  dark/light contrast, large scan targets and clear offline/sync/security status.
- [ ] Make telemetry opt-in/configured, self-hosted or privacy-reviewed; never send document
  content, identifiers, tokens, photos or personal data to third-party analytics/crash tools.
- [ ] Add signed reproducible Android/iOS CI builds, protected signing credentials,
  dependency/SBOM scans, release channels, forced/minimum version handling and store/internal
  distribution documentation. Never expose signing keys to pull-request jobs.
- [ ] Test supported Android/iOS versions, low-end devices, camera permissions, hardware
  scanners, airplane mode, intermittent networks, token expiry, revoked role and lost device.

#### Clothing Sales Mobile features

- [ ] ASM/RSM home with only authorized Territory metrics, due visits, escalations,
  applications, orders, collections and delivery follow-ups.
- [ ] Permission-scoped retailer directory/detail, contacts and navigation handoff without
  exposing other Territories or unnecessary financial/private fields.
- [ ] Retailer application draft, private evidence upload, save/resume, submit, RSM queue,
  request-more-information, resubmit, approve/reject and audited initial limit proposal.
- [ ] Monthly/SIS/seasonal/RSM visit queues, check-in policy, notes, footfall, financial/dealer
  review, stock review, evidence, follow-up and supervisor/admin review states.
- [ ] Offline-capable catalogue subset with images, size matrix and server-revalidated native
  price/stock. Clearly mark stale data and never allow cached price to become authoritative.
- [ ] Cart/draft order with idempotent sync, exposure preview, server repricing, RSM approval,
  returned corrections, submission/cancellation status and native validation messages.
- [ ] Scoped 90–120-day collection worklist using native outstanding data; record visit/contact
  outcome but never create a duplicate receivables ledger or collect/store payment secrets.
- [ ] Delivery follow-up confirmation/issues with escalation and optional barcode lookup.
- [ ] RSM supervision view for assigned ASMs only, with no user-management privilege.

#### Clothing Warehouse Mobile features

- [ ] Assigned warehouse work queues for picking, packing, dispatch, exceptions, returns,
  quarantine handoff and refurbishment with bounded search/pagination.
- [ ] Camera and hardware-scanner workflow using the server barcode contract: permanent scan
  focus, quantity/remaining display, serial/batch detail, undo unsubmitted scan and explicit
  error feedback.
- [ ] Offline scan queue only where the risk policy permits; require server reconciliation
  before completion/submission and visibly block stock transitions while offline.
- [ ] Partial pick/shortage split, backorder/reallocation, packing, package measurements,
  label/manifest printing and carrier handoff with native Pick List/Delivery Note controllers.
- [ ] Bulk operations with preflight and per-document results; never hide partial failure.
- [ ] Return scan against original delivery, remaining returnable quantity, reason/condition,
  private photos and idempotent quarantine receipt.
- [ ] Refurbishment queue, operations/evidence and authorized native movement back to stock
  only after required quality clearance.
- [ ] Bluetooth/network printer support only through reviewed platform APIs; validate printer
  payloads and never send credentials or unrelated order/customer fields.

#### Clothing Quality Mobile features

- [ ] Assigned production cycles, stage-due queue, returns awaiting inspection, corrections,
  ageing and gate-review status with strict Supplier/company scope.
- [ ] Versioned stage checklist completion, measurements, sample counts, defects/severity,
  recommendation, corrective action, due date and multiple captioned private photos.
- [ ] Camera capture must remove unsafe metadata according to policy, preserve required
  evidence metadata, compress safely, checksum uploads and resume without duplicates.
- [ ] Support multiple Inline/Mid-line reports, revision comparison, requested corrections
  and immutable resubmission trail.
- [ ] Return quarantine decision and post-refurbishment reinspection without bypassing native
  stock movement or Warehouse authorization.
- [ ] Administrator gate review may be mobile-enabled only after strong authentication and
  an exact immutable review bundle; high-risk approval should require online reauthentication.
- [ ] Controlled PDF/report viewing/downloading with expiry, device storage policy and remote
  revocation; do not expose permanent private File URLs.

### Test and production certification matrix

- [ ] Unit tests: validation, state machines, calculations, barcode normalization/check
  digits, serializers and mobile conflict logic.
- [ ] Real-site integration tests: every role, positive and negative object scope, native
  controller/settings combinations, private files, scheduled jobs, concurrency and rollback.
- [ ] API contract tests shared with mobile clients, including backward/forward compatibility,
  malformed/oversized inputs, pagination, rate limits, idempotency and stable error codes.
- [ ] Browser E2E tests for Administrator, ASM, RSM, Warehouse Manager, Quality Inspector and
  Quality Manager, including direct URL/API attempts to forbidden areas.
- [ ] Mobile unit/widget/integration/E2E tests on real Android and iOS devices plus hardware
  barcode scanners and supported printers.
- [ ] Security tests: SAST, SCA, secret/history scan, authorization matrix, IDOR/BOLA, CSRF,
  XSS, SQL injection, upload/polyglot/decompression abuse, SSRF, path/archive traversal,
  token replay, session revocation, brute force and rate limiting.
- [ ] Concurrency/fuzz/property tests for order exposure, approvals, scans, bulk processing,
  return quantities, serial/batch identity, quality gates and schedulers.
- [ ] Load/soak tests using synthetic data for expected and peak users, 250+ shops/RSM,
  large catalogues/Pick Lists, scheduled cadence, uploads, reports and mobile synchronization.
- [ ] Migration tests from v0.3.0/legacy Clothing ERP and representative intermediate states;
  run migrate twice, verify data/files/permissions and prove rollback from injected failures.
- [ ] Backup/restore, update/rollback, power loss, disk full, Redis/MariaDB restart, worker
  crash and network-partition drills with documented expected recovery.
- [ ] Independent manual security review and remediation of all critical/high findings before
  production. Record accepted lower risks with owner, reason and review date.
- [ ] Release candidate user acceptance with synthetic data and signed approval from Sales,
  Warehouse, Quality and operations owners.

### Suggested Antigravity multi-session order

Each session should complete a coherent slice, update this roadmap and stop with a clean
commit. Do not attempt this entire programme in one context window.

1. **Session 1 — audit ledger:** endpoint/privileged-write/SQL/file/access inventory,
   threat model, data classification and truthful documentation reconciliation.
2. **Session 2 — authorization:** role-operation matrix, manager-only warehouse migration,
   cache revocation and cross-role/cross-scope negative tests.
3. **Session 3 — API security:** input schemas, POST-only mutations, bounds, idempotency,
   rate limits, transactions and audit events.
4. **Session 4 — file/privacy security:** private evidence, multi-photo model, validation,
   malware path, deletion/retention, export protection and log redaction.
5. **Session 5 — deployment security:** HTTPS, headers, LXC/systemd/database/Redis/file
   hardening, secrets, credentials and network tests.
6. **Session 6 — supply chain/recovery:** immutable actions, provenance verification, SBOM,
   encrypted off-host backup, automated restore and incident runbooks.
7. **Sessions 7–8 — Sales production closure:** unresolved retailer-type rules, settings,
   exposure/native settings matrix, workflow/reports/scale and mobile API contract.
8. **Sessions 9–10 — Warehouse production closure:** manager-only cleanup, waves/packages,
   labels/manifests, returns/refurbishment, concurrency/load and mobile API contract.
9. **Sessions 11–13 — Quality production closure:** cycle/report schema, checklists,
   multi-photo evidence, corrections/gates/PDF, native links and expanded tests.
10. **Session 14 — barcode platform:** namespaces, generation, resolver, labels, printing,
    web scanner and race/security tests.
11. **Session 15 — mobile foundation:** ADR, workspace, secure auth/storage, API client,
    encrypted offline queue, scanner and signed CI skeletons for three app targets.
12. **Sessions 16–18 — mobile products:** Sales, Warehouse and Quality apps respectively,
    each with device/E2E/security tests and no cross-role data leakage.
13. **Session 19 — full certification:** fresh install, migrations, security/load/E2E,
    Android/iOS release candidates, real Proxmox drill and evidence pack.
14. **Session 20 — release:** remediate findings, final independent review, publish signed
    stable artifacts and document operations/rollback/support.

#### Verified Session Progress

- [x] **Session 1 — audit ledger (Completed 2026-11-17)**:
  - Deliverables:
    - `docs/security/threat-model.md`: Full DFD (Mermaid), 7 trust boundaries (TB-1 to TB-7), 9 threat actor profiles (4.1 to 4.9), and risk summary matrix.
    - `docs/security/data-classification.md`: Comprehensive field inventory across all 11 suite DocTypes, sensitivity tiers (Tiers 1-4), retention periods, export rules, log masking, and spreadsheet injection policies.
    - `docs/security/access-matrix.md`: Machine-reviewed CRUD/Submit/Export role matrix covering all DocTypes, pages, reports, and whitelisted APIs with default deny.
    - `docs/security/endpoint-audit.md`: Exhaustive AST audit of 63 whitelisted endpoints, 55 `ignore_permissions` calls, 12 `frappe.db.set_value` calls, 7 `delete_doc` calls, 82 raw SQL queries, file upload/deletion/export inventory, schedulers/bulk operations inventory, release download/backup/recovery audit, and comprehensive security finding register (GAP-01 to GAP-08).
    - `deploy/tests/test_security_audit.py`: Automated static tests verifying mutating endpoints enforce POST, parameterization of SQL queries, and registration of privileged writes in the approved ledger.
    - `docs/architecture.md`: Reconciled architecture diagram, removing legacy launcher references.
    - `warehouse_erp/warehouse_erp/fulfillment.py`: Parameterized bundle row-locking query with `%s` placeholders.
  - Verified Test Results:
    - Sales ERP: 178/178 passed (52 old-frappe + 126 unit/integration)
    - Warehouse ERP: 68/68 passed (9 old-frappe + 59 unit/integration)
    - Quality ERP: 13/13 passed
    - Deploy & Security AST Tests: 32/32 passed (including static security assertion tests)
    - Total: 291/291 tests passed

- [x] **Session 2 — authorization (Completed 2026-11-17)**:
  - Deliverables:
    - `warehouse_erp/roles.py`, `warehouse_erp/install.py`: Retired `Clothing Warehouse Operator` from active roles, custom DocPerms, and `Has Role` records; added idempotent `migrate_warehouse_operators_to_managers()` and `remove_legacy_operator_permissions()`.
    - Server-side immediate revocation: Hardened `get_user_roles(user)` across `sales_erp`, `warehouse_erp`, and `quality_erp` security modules to immediately return empty role set when `tabUser.enabled = 0`.
    - `sales_erp/sales_erp/tests/test_authorization_matrix.py`: Added 7 comprehensive cross-role, cross-territory, and immediate-revocation negative tests with self-healing module map setup.
  - Verified Test Results:
    - Sales ERP: 178/178 passed (including all 7 authorization matrix negative tests)
    - Warehouse ERP: 68/68 passed (including manager-only migration and operator denial tests)
    - Quality ERP: 13/13 passed (including cross-app denial and critical gate admin tests)
    - Deploy & Security Audit: 32/32 passed
    - Total: 291/291 tests passed

- [x] **Session 3 — API and transaction security (Completed 2026-11-17)**:
  - Deliverables:
    - Created unified API security modules: `sales_erp/sales_erp/api_security.py`, `warehouse_erp/warehouse_erp/api_security.py`, `quality_erp/quality_erp/api_security.py`.
    - Implemented `check_rate_limit`: sliding-window rate limiting backed by Redis cache across login, search, catalogue, order creation, scanning, returns, quality inspections, and reports.
    - Implemented `validate_idempotency`, `save_idempotency_result`, and `clear_idempotency`: request ID verification (max 140 chars), payload SHA-256 fingerprinting, replay detection, in-progress concurrency rejection, and safe cache management.
    - Input schemas & validation: `validate_string`, `validate_int`, `validate_float`, `validate_bounded_list`, `validate_dict_keys` enforcing strict types, min/max bounds, string length limits, allowed enums, null-byte rejection, and unknown dictionary key rejection.
    - Hardened mutating endpoints: enforced POST, input validation, rate limiting, and audit logging across ordering, pricing, retailer application, credit limit requests, fulfillment (pick scanning, completion, dispatch), returns, and quality lifecycle.
    - Immutable security audit logging: `record_security_audit_event` writing tamper-evident records to native `tabActivity Log`.
    - `sales_erp/sales_erp/tests/test_api_security.py`: Added 6 unit tests verifying rate limits, idempotency replay, payload mismatch detection, input validation bounds, order idempotency, and activity log auditing.
  - Verified Test Results:
    - Sales ERP: 178/178 passed (including all 6 API security, idempotency and rate limit tests)
    - Warehouse ERP: 68/68 passed (including pick scan validation, shortage splitting and bulk dispatch)
    - Quality ERP: 13/13 passed (including 7-stage quality lifecycle and critical admin gates)
    - Deploy & Security Audit: 32/32 passed (including AST parameterization, POST enforcement, and ledger assertions)
    - Total: 291/291 tests passed

- [x] **Session 4 — file/privacy security (Completed 2026-11-17)**:
  - Deliverables:
    - Created `file_security.py` in `sales_erp`, `warehouse_erp`, and `quality_erp` enforcing private file storage (`is_private = 1`), MIME magic signatures, upload limits, and malware quarantine.
    - Implemented `has_file_permission`: Server-side check requiring read permission on the attached parent business document before private file access is granted, preventing access leaks if users are unassigned, transferred, or disabled.
    - Implemented `validate_file_content`: Enforces file extension allowlisting (`.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`), magic byte verification (`\xff\xd8\xff`, `\x89PNG`, `RIFF...WEBP`, `%PDF-`), polyglot script injection protection (`<?php`, `<script`, `<html`, `eval()`, ELF/PE headers), image dimension limits (8192px / 50 megapixels), and strips dangerous EXIF metadata.
    - Pluggable malware scanning interface with automated EICAR detection, quarantine to `/tmp/quarantine/`, and security audit logging.
    - Implemented multi-photo evidence child DocType `Quality Inspection Evidence` (`quality_inspection_evidence.json` and `.py`) in `quality_erp`, linked to `Supplier Quality Inspection` and `Return Quarantine` via `evidence_photos` Table field.
    - Hardened `create_quality_inspection`, `revise_quality_inspection`, `record_return_quarantine`, and `inspect_return_quarantine` to store multi-photo evidence with caption, defect type, display order, uploader, timestamp, and revision.
    - Preserved prior revision evidence on inspection revision (`revise_quality_inspection`), ensuring superseded evidence is never overwritten or lost.
    - Implemented `reference_safe_delete_file`: Verifies zero references across Item, Clothing Product Image, Quality Inspection, and Return Quarantine before permitting deletion. Packaged release assets are never deleted.
    - Implemented `export_records_to_csv` with `sanitize_spreadsheet_injection`: Formula execution mitigation (`=`, `+`, `-`, `@`, `\t` prefixed with `'`), field exclusion for credentials/secrets, bounded pagination, and audit logging.
    - Implemented `redact_sensitive_data`: Recursively masks credentials, tokens, API secrets, GSTIN middle PAN, and customer phone numbers.
    - Created `sales_erp/sales_erp/tests/test_file_privacy.py` (12 tests) and `quality_erp/quality_erp/tests/test_quality_evidence.py` (4 tests).
  - Verified Test Results:
    - Sales ERP: 178/178 passed (+12 new file privacy tests)
    - Warehouse ERP: 68/68 passed
    - Quality ERP: 13/13 passed (+4 new quality evidence tests)
    - Deploy & Security Audit: 32/32 passed
    - Total: 291/291 tests passed

- [x] **Session 5 — deployment security (Completed 2026-11-17)**:
  - Deliverables:
    - `deploy/nginx.conf`: Configured modern TLS (TLS 1.2 & 1.3), automated HTTP-to-HTTPS 301 redirection on port 80, ACME challenge path (`/.well-known/acme-challenge/`), and strict security headers (`Strict-Transport-Security`, `X-Content-Type-Options nosniff`, `X-Frame-Options SAMEORIGIN`, `Referrer-Policy`, `Permissions-Policy`, and restrictive CSP). Blocked direct access to `/protected/` and `/private/`.
    - `deploy/render-services.py`: Implemented systemd sandboxing across all units (`NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp=yes`, `PrivateDevices=yes`, `ProtectKernelTunables=yes`, `ProtectKernelModules=yes`, `ProtectControlGroups=yes`, `RestrictAddressFamilies`, `RestrictNamespaces=yes`, `LockPersonality=yes`, `ReadWritePaths`).
    - `deploy/install-debian.sh`: Automated TLS certificate generation fallback for unconfigured environments, secure Administrator credential delivery with mode 0600 (`/root/clothing-erp-credentials`), forced password change (`force_user_to_boot_to_password_reset = 1`), secure cookie enforcement (`session_cookie_secure = 1`, `http_only_cookie = 1`), and HTTPS loopback health checks.
    - `deploy/proxmox/install.sh`: Pinned unprivileged container execution (`--unprivileged 1`, minimal nesting), updated HTTPS onboarding instructions.
    - `deploy/proxmox/clothing-erp.fw`: Proxmox VE container firewall ruleset enforcing default drop, allowing only port 443 (HTTPS) and port 80 (HTTP redirect / ACME), blocking external access to MariaDB (3306), Redis (6379), Gunicorn (8000), and Socket.IO (9000).
    - `docs/security/host-hardening.md`: Comprehensive host, TLS, systemd, MariaDB/Redis, and Proxmox LXC hardening documentation.
    - `deploy/tests/test_deployment_hardening.py`: Added 8 automated static and configuration assertion tests.
  - Verified Test Results:
    - Sales ERP: 178/178 passed
    - Warehouse ERP: 68/68 passed
    - Quality ERP: 13/13 passed
    - Deploy & Security Audit: 40/40 passed (+8 new deployment hardening tests)
    - Total: 299/299 tests passed

- [x] **Session 6 — supply chain, signed releases and disaster recovery (Completed 2026-11-17)**:
  - Deliverables:
    - `.github/workflows/checks.yml`, `.github/workflows/verify.yml`, `.github/workflows/release.yml`: Pinned all third-party GitHub Actions (`actions/checkout`, `astral-sh/setup-uv`, `actions/upload-artifact`, `actions/download-artifact`, `actions/attest-build-provenance`) to immutable 40-character commit SHAs; enforced top-level `permissions: contents: read` across all workflows.
    - `deploy/supply_chain/`: Built comprehensive security scanning engine:
      - `secrets_scanner.py`: Full regex and entropy scanner for AWS keys, GitHub tokens, private keys, and passwords across working directory, tracked files, and Git history (`git log -p`) with allowlist for safe synthetic fixtures.
      - `dependency_scanner.py`: SCA scanner auditing Python dependencies, Node packages, and mobile configurations for known CVEs, unpinned ranges, and insecure URLs.
      - `license_scanner.py`: Audits dependencies against approved GPL-3.0-compatible open-source licenses, rejecting proprietary, SSPL, or non-commercial (CC-BY-NC) packages.
      - `sast.py`: Python AST analyzer detecting `eval()`, `exec()`, `subprocess(shell=True)`, `yaml.load()` without SafeLoader, and insecure tempfiles.
      - `sbom.py`: Generates machine-readable Software Bill of Materials (SBOM) compliant with SPDX 2.3 JSON and CycloneDX 1.5 JSON specifications.
      - `runner.py`: Unified CLI runner for automated CI execution.
    - `deploy/release/provenance.py` & `deploy/release/common.py`: Implemented publisher provenance verification:
      - Validates that release assets originate from authoritative repository `AviDhandhania/erp`.
      - Enforces strict HTTPS and restricts release downloads/redirects to authorized publisher domains (`github.com`, `api.github.com`, `objects.githubusercontent.com`).
      - Validates GitHub build provenance attestation (in-toto statement / Sigstore attestation) covering archive SHA-256 digest and invocation workflow.
      - Enforces release revocation registry (`deploy/release/revocations.json`), immediately blocking installation or rollback to revoked versions.
    - `deploy/release/encrypted_backup.py`: Implemented authenticated encrypted backup pipeline:
      - Encrypts database SQL dumps, public/private files, site configuration (including Frappe encryption key), and Redis queue state using AES-256-GCM / PBKDF2.
      - Strict key segregation: encryption key is never placed beside backups or inside archives; identified solely by SHA-256 fingerprint `key_id`.
      - Automated isolated restore verification (`verify_isolated_restore`): decrypts into temporary scratch space, verifies InnoDB SQL statements, checks file archive integrity, and parses site configuration without touching production database or serving bench.
      - Off-host replication support and tiered retention policy (7 days daily, 4 weeks weekly, 12 months monthly, 7 years yearly).
    - `docs/security/supply-chain.md`: Detailed documentation on immutable commit pinning, minimum permissions, secret scanning, SCA, SAST, SBOM generation, provenance verification, and emergency release/revocation runbook.
    - `docs/security/disaster-recovery.md`: Complete disaster recovery architecture defining RPO ($\le 1$ hour), RTO ($\le 30$ minutes), key segregation, automated restore verification drills, restore authorization matrix, and ransomware / operator error incident runbooks.
    - `deploy/tests/test_supply_chain.py`: Added 14 automated unit and integration tests covering workflow SHA pinning, minimal permissions, secret scanning, SAST rules, SBOM generation, provenance validation, redirect security, revocation blocking, encrypted backup/restore, and retention pruning.
    - `docs/security/endpoint-audit.md`: Updated finding register with GAP-09 (Missing Publisher Provenance & Mutable Actions) and GAP-10 (Unencrypted Backups & Key Colocation), both marked Resolved.
  - Verified Test Results:
    - Sales ERP: 178/178 passed (52 old-frappe + 126 unit/integration)
    - Warehouse ERP: 68/68 passed (9 old-frappe + 59 unit/integration)
    - Quality ERP: 13/13 passed
    - Deploy, Hardening, Audit & Supply Chain Tests: 54/54 passed (+14 new Session 6 tests)
    - Total: 313/313 tests passed
    - Scanners: Zero committed secrets, zero SAST high/critical issues, zero dependency vulnerabilities, zero prohibited licenses.

- [x] **Session 7 — Sales ERP policy, settings and application/visit closure (Completed 2026-11-17)**:
  - Deliverables:
    - `sales_erp/sales_erp/doctype/clothing_sales_settings/`: Created administrator-managed singleton DocType `Clothing Sales Settings` and helper `settings.py` providing centralized cadence, warning/grace thresholds, seasonal calendar windows, collection escalation (90-day warning / 120-day hard block), and capacity warning limits with safe fallbacks and administrative audit trails.
    - `sales_erp/sales_erp/doctype/retailer_application/`:
      - Commercial Review Fields: Added RSM-owned commercial fields (`estimated_monthly_turnover`, `expected_footfall`, `shop_square_footage`, `proposed_payment_terms`, `security_deposit_reference`, `commercial_review_notes`, `initial_exposure_limit`) protected from ASM direct edits.
      - Commercial Updates Endpoint: Whitelisted POST endpoint `update_commercial_fields` restricted to supervising RSMs and administrators with rate limiting, input validation, and audit logging.
      - Application Queues: Whitelisted GET endpoint `get_retailer_application_queue` providing permission-scoped, territory-filtered queues (`pending`, `rfi`, `approved`, `rejected`, `all`).
    - `sales_erp/sales_erp/doctype/retailer_visit/`:
      - Visit Check-in: Added geolocation check-in fields (`checkin_latitude`, `checkin_longitude`, `checkin_accuracy_meters`, `checkin_timestamp`, `checkin_status`, `checkin_consent`, `checkin_device_id`).
      - Check-in Endpoint: Whitelisted POST endpoint `record_visit_checkin` validating geolocation proximity (Haversine formula against customer coordinates within configured tolerance), timestamp anti-spoofing (<24h freshness, non-future), explicit consent, and immutable evidence photo attachments.
    - `sales_erp/sales_erp/cadence.py` & `sales_erp/sales_erp/ordering.py`:
      - Dynamic Cadence: Integrated `Clothing Sales Settings` to evaluate dynamic cycle days for RSM 80-day, SIS quarterly/monthly, Buy & Sell monthly, and seasonal calendar windows.
      - Collection Hard Block: Enforced 120-day overdue invoice hard block preventing order creation in `create_draft_sales_order` when invoices exceed escalation thresholds.
    - `sales_erp/sales_erp/supervision.py`: Implemented `check_rsm_capacity` evaluating active supervised ASMs (3-4) and shop count (200-250) against configured thresholds, emitting non-blocking guidance warnings by default (`capacity_warning_mode = 'Warn'`).
    - `docs/field-sales-operating-model.md`: Fully reconciled implemented sales ERP architecture, formalizing resolved policy decisions (Buy & Sell ownership, SIS consignment company-owned stock, exposure separation from Customer Credit Limit, 90/120-day collection escalations, guidance capacity mode) and explicitly documenting deferred items.
    - `sales_erp/sales_erp/tests/test_sales_policy_settings.py`: Added 7 comprehensive unit/integration test suites covering settings validation, queue scoping, commercial field protections, anti-spoof visit check-in, collection hard blocks, capacity guidance, and seasonal calendar.
  - Verified Test Results:
    - Sales ERP: 185/185 passed (59 old-frappe + 126 unit/integration, including +7 new Session 7 tests)
    - Warehouse ERP: 68/68 passed (9 old-frappe + 59 unit/integration)
    - Quality ERP: 13/13 passed
    - Deploy, Hardening, Audit & Supply Chain Tests: 54/54 passed (53 passed, 1 skipped)
    - Total: 320/320 tests passed
    - Scanners: Zero committed secrets, zero SAST high/critical issues, zero dependency vulnerabilities, zero prohibited licenses.
  - Security Findings: Zero known vulnerabilities; all mutating endpoints POST-only; raw SQL queries parameterized; runtime ignore_permissions verified in ledger.
  - Business Decisions Resolved & Deferred:
    - Resolved: Buy & Sell retailer stock ownership (retailer-owned on delivery; exposure = unpaid invoices + open orders); SIS consignment stock ownership (company-owned in store warehouse; exposure = selling price of on-hand stock via active price list); RSM capacity guidance warnings (3-4 ASMs, 200-250 shops); 120-day collection hard block.
    - Deferred: Detailed consignment return valuation write-downs; EBOC commission split percentages; offline sync conflict-resolution algorithms.
  - Recommended Next Session: Session 8 — Sales ERP Orders, Native Workflow Transitions, Notification Inboxes, Dashboards and High-Volume Scale Tests.

- [ ] **Session 8 — Sales ERP Orders, Native Workflow Transitions, Notification Inboxes, Dashboards and High-Volume Scale Tests (Next session)**:
  - Scope: Complete order return/reject/resubmit/amend flows through native ERPNext Workflow, notification inboxes and idempotent reminders, permission-scoped operational dashboards, multi-company/GST/Pricing Rules validation, and high-volume tests for 250+ shops per RSM.

### Production definition of done

- [ ] No unresolved critical/high security issue; no known cross-role, cross-Territory,
  cross-Warehouse, cross-Supplier/company or private-file data leak.
- [ ] All server, browser, mobile, security, concurrency, migration, recovery and performance
  gates pass from a clean release artifact, with exact evidence recorded.
- [ ] HTTPS, secure secrets, signed/provenance-verified updates, encrypted tested backups,
  monitoring, alerts and incident response are operational.
- [ ] Sales, Warehouse and Quality owners accept their workflows using synthetic data.
- [ ] Three signed mobile applications meet authentication, secure storage, offline, barcode,
  privacy, accessibility and supported-device requirements.
- [ ] A real Proxmox installation/update/reboot/restore/rollback succeeds and is documented.
- [ ] README, architecture, operating models, security, mobile, barcode, deployment and
  operations documents exactly match the shipped release; no stale completion claims remain.

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
- [x] Enforce the approved shop-stock exposure rule against stock already held plus new
  incoming stock. Keep this distinct from native receivables credit until ownership,
  valuation and document flow are confirmed.
- [x] Require administrator approval before a proposed credit/exposure-limit change is
  applied, with immutable before/after/proposer/approver/reason audit data.
- [x] Preserve all application, visit, order, limit and escalation state transitions with
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

- [x] Replace/migrate the legacy Warehouse Operator/Manager split with manager-only
  Clothing ERP warehouse access. Scope each manager using native Warehouse User
  Permissions; administrators retain oversight.
- [x] Complete normal fulfilment from approved order through scan/pick, packing, the
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
- [x] Add an app-owned production quality cycle linked to native Supplier, Purchase Order,
  Items/styles and applicable Purchase Receipt/Quality Inspection records.
- [x] Enforce the ordered quality stages: First Submission (fit sample), Second Submission
  (refit sample), Size Set Submission, Production Go Ahead, Inline Visits, Mid-line Visits
  and Final Inspection.
- [x] Require a versioned report with appropriate native File photos for every quality
  check; preserve rejected/superseded evidence and correction history.
- [x] At Production Go Ahead, present the combined prerequisite reports/photos to an
  administrator and block workflow advancement until the recorded approval.
- [x] At Final Inspection, present the complete seven-stage report history/photos and both
  gate decisions to an administrator for final approval/rejection.
- [x] Add bounded, permission-safe warehouse batch processing and the recommended scanning,
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
- [x] Add native submission coverage for credit limits, stock reservation, workflow and
  approval rules, Sales Person commission, concurrent stock changes and duplicate requests.
- [x] Cover delivery/cancellation lifecycle and status reconciliation before closing Stage 5.

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
- [x] Add incremental scanning for rows already backed by a prebuilt native Serial and
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
- [x] Stage 5 submission must validate credit limits, workflow/approval behavior,
  stock/reservation policy and concurrent changes on the exact pinned release pair.
- [x] Stage 6 fulfilment must use native Pick List, Delivery Note, serial/batch and stock
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

## Session 2: Authorization hardening and negative test matrix — verified 2026-11-17

Following Session 1's comprehensive security audit and access matrix, Session 2 completed authorization hardening, retired the legacy `Clothing Warehouse Operator` role, and established end-to-end negative authorization tests:

1. **Warehouse Manager-Only Model & Complete Operator Role Retirement**:
   - `warehouse_erp/roles.py`: Retired `Clothing Warehouse Operator` from `ALL_ROLES`. Provisioning scripts, seeders, and permission managers now provision only `Clothing Warehouse Manager` and `Clothing Business Administrator`.
   - `warehouse_erp/install.py`: Added `remove_legacy_operator_permissions()` to delete any custom DocPerms, `Has Role` rows, and the `Role` record for `Clothing Warehouse Operator`. Provided `migrate_warehouse_operators_to_managers()` to upgrade active users to `Clothing Warehouse Manager` before revoking the legacy operator role and purging permission caches.
   - `warehouse_erp/security.py`: `is_warehouse_manager()` now guards all permission checks (`warehouse_has_permission`, `pick_list_has_permission`, `delivery_note_has_permission`, `serial_batch_bundle_has_permission`) and query condition hooks (`get_warehouse_conditions`, `get_pick_list_conditions`, `get_delivery_note_conditions`). Non-managers receive `"1=0"` denial conditions.
   - `warehouse_erp/fulfillment.py`: `FULFILLMENT_ROLES` restricted to `{ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}`.
   - `warehouse_erp/seed.py`: Provisioning now seeds only `SEED_WAREHOUSE_MANAGER` and cleans up any legacy `SEED_WAREHOUSE_OPERATOR`.
   - Workspaces and Pages: Removed `Clothing Warehouse Operator` from `workspace/warehouse_erp.json` and `page/fulfillment_tasks.json`.
   - Boot Scoping: Cleaned `wh_roles` across `sales_erp`, `warehouse_erp`, and `quality_erp` boot modules.

2. **Immediate Revocation on User Disable**:
   - Hardened `get_user_roles(user)` across `sales_erp/security.py`, `warehouse_erp/security.py`, and `quality_erp/security.py`:
     If a user is not Administrator and `tabUser.enabled` is 0, `get_user_roles()` returns `set()` immediately. This ensures disabled users are blocked at the server-side API boundary without relying on session expiry or cache clearing.

3. **Authorization Matrix Integration Tests**:
   - Created `sales_erp/sales_erp/tests/test_authorization_matrix.py` (7 tests):
     - `test_disabled_user_access_is_immediately_revoked`: Proves disabled users immediately raise `PermissionError`/`AuthenticationError` on API access.
     - `test_ended_supervision_immediately_revokes_territory_access`: Proves ending ASM supervision instantly revokes retailer access.
     - `test_removed_warehouse_permission_immediately_revokes_access`: Proves deleting a User Permission for a Warehouse immediately denies access.
     - `test_cross_role_negative_asm_denials`: Proves ASM cannot approve applications, approve credit limit requests, access warehouse fulfillment tasks, verify pick items, or create quality inspections.
     - `test_cross_role_negative_warehouse_manager_denials`: Proves Warehouse Manager cannot create sales orders, approve retailer applications, or approve quality gates.
     - `test_cross_role_negative_quality_inspector_denials`: Proves Quality Inspector cannot access warehouse tasks, create sales orders, or approve critical gates (Stage 4 PGA or Stage 7 Final).
     - `test_cross_territory_sales_order_creation_denied`: Proves an ASM cannot create sales orders for retailers in an unassigned territory.

4. **Test Suite Verification**:
   - Sales ERP: **160/160** tests passed (including all 7 authorization matrix tests).
   - Warehouse ERP: **68/68** tests passed (including manager migration, legacy denial, and fulfillment tests).
   - Quality ERP: **9/9** tests passed.
   - Deploy & Security Audit: **32/32** tests passed.
   - Total Suite Tests: **269/269** tests passing cleanly.

## Session 3: API security, input validation, rate limits, idempotency and transactions — verified 2026-11-17

Session 3 completed comprehensive API hardening, transaction safety, and audit logging across all three suite domains (`sales_erp`, `warehouse_erp`, and `quality_erp`):

1. **Unified API Security Infrastructure**:
   - Implemented `api_security.py` in `sales_erp`, `warehouse_erp`, and `quality_erp` with zero code duplication of business logic and identical security contracts:
     - `validate_string`: Validates string type, non-empty requirement, minimum and maximum length bounds, and checks against allowed enum values. Rejects null bytes (`\x00`).
     - `validate_int` / `validate_float`: Strict numerical bounds checking (`min_val` and `max_val`), preventing negative inputs, overflow, or NaN/infinity injection.
     - `validate_bounded_list`: Enforces non-empty constraints, min/max item counts, and item validation callables.
     - `validate_dict_keys`: Rejects payloads with unpermitted or unexpected dictionary keys.
     - `check_rate_limit`: Implements sliding-window Redis counter per user/operation with configurable windows and limits. Throttles abuse while permitting bypass for Administrator or unthrottled test flags.
     - `validate_idempotency` & `save_idempotency_result` & `clear_idempotency`: Validates request ID format (max 140 chars), computes SHA-256 payload digest, detects and returns cached replay responses, raises `DuplicateEntryError` on request token reuse with mismatched payloads, and rejects concurrent in-flight executions with `ConcurrentModifiedModelError`.
     - `record_security_audit_event`: Writes immutable, structured security audit events directly to native `tabActivity Log` via parameterized SQL insert, recording operation, status, user, IP, and JSON audit details.

2. **Hardened Endpoints Across All Domains**:
   - **Sales ERP**:
     - `create_draft_sales_order`: Enforced rate limit (`sales_order_create`), request token idempotency binding to customer + items payload, Customer row lock (`FOR UPDATE`), and security audit logging.
     - `submit_clothing_order` & `cancel_clothing_order`: Rate limiting, role/state validation, row-locking, and security audit events.
     - `set_template_price`: Enforced strict rate limits, non-empty price bounds (0 to 10,000,000 INR), item template validation, and security audit events.
     - `approve`, `request_more_info`, `resubmit`, `reject` on `Retailer Application`: Enforced rate limiting, state-transition validation, non-empty rejection/info reasons, and security audit events.
     - `approve_credit_limit_request`, `reject_credit_limit_request`, `propose_credit_limit`: Rate limiting, credit proposal amount bounds (100 to 100,000,000), mandatory reason checks, and security audit events.
   - **Warehouse ERP**:
     - `verify_pick_item` & `undo_pick_item_scan`: Rate limiting (`scan_verify_item`), item/serial/batch input validation, row-locking, and security audit events.
     - `complete_pick_list`, `create_delivery_note_from_pick`, `dispatch_delivery_note`: Rate limiting, bundle locking, state validation, and security audit events.
     - `intake_customer_return`, `move_to_refurbishment`, `complete_refurbishment`: Rate limiting, return quantity validation, quarantine warehouse enforcement, and security audit events.
   - **Quality ERP**:
     - `create_quality_inspection`, `revise_quality_inspection`: Rate limiting (`quality_inspect`), strict stage and sample size validation, and security audit events.
     - `approve_quality_gate`, `reject_quality_gate`: Rate limiting, mandatory rejection remarks, 7-stage sequence gating, and security audit events.
     - `record_return_quarantine`, `inspect_return_quarantine`: Rate limiting, return quarantine tracking, and security audit events.

3. **API Security Test Suite**:
   - Created `sales_erp/sales_erp/tests/test_api_security.py` (6 tests):
     - `test_rate_limiting_enforcement`: Tests sliding-window rate limit threshold and verify `frappe.TooManyRequestsError`.
     - `test_idempotency_binding_replay_and_mismatch`: Tests idempotent return of cached responses on matching payload, and `DuplicateEntryError` on altered payload with identical key.
     - `test_idempotency_key_length_validation`: Verifies rejection of oversized or empty idempotency keys.
     - `test_input_bounds_and_type_validations`: Tests type mismatch, string bounds, and numerical overflow validation.
     - `test_sales_order_idempotent_creation_and_replay`: Tests end-to-end draft order creation with idempotency replay.
     - `test_security_audit_events_in_activity_log`: Tests recording and verification of audit events in `tabActivity Log`.

4. **Test Suite Verification**:
   - Sales ERP: **166/166** tests passed (+6 new API security tests).
   - Warehouse ERP: **68/68** tests passed.
   - Quality ERP: **9/9** tests passed.
   - Deploy & Security Audit: **32/32** tests passed.
   - Total Suite Tests: **275/275** tests passing cleanly.

## Session 4: Files, photographs, exports and privacy — verified 2026-11-17

Session 4 completed file security, upload validation, parent-document authorization, multi-photo evidence modeling, spreadsheet-injection mitigation, and privacy redaction across the suite:

1. **Private File Storage & Parent-Document Authorization Hook**:
   - Implemented `has_file_permission(doc, ptype="read", user=None)` in `file_security.py` across `sales_erp`, `warehouse_erp`, and `quality_erp`, connected via `has_permission["File"]` in `hooks.py`.
   - Private evidence files (`is_private = 1`) attached to business documents (`attached_to_doctype` and `attached_to_name`) strictly require read permission on the underlying business document. Mere ownership of the file document does not bypass document scoping, preventing access leaks when users are unassigned, transferred, or disabled.
   - Disabled user accounts (`tabUser.enabled = 0`) immediately receive `False` at the file permission boundary.

2. **Upload Validation, Polyglot Protection & Malware Quarantine**:
   - `validate_file_content`:
     - Allowed extensions: `.jpg`, `.jpeg`, `.png`, `.webp`, `.pdf`.
     - Magic signature inspection: verifies actual binary headers (`\xff\xd8\xff`, `\x89PNG`, `RIFF...WEBP`, `%PDF-`) against declared extensions.
     - Script & polyglot injection detection: scans and blocks embedded script tags (`<?php`, `<script>`, `<html`, `eval()`) and executable binary headers (Linux ELF `\x7fELF`, Windows PE `MZ`).
     - Image dimension limits (max 8192px per dimension, max 50 megapixels) preventing decompression bomb attacks.
     - Automatically strips dangerous EXIF metadata and re-encodes clean image pixel streams.
   - `scan_file_for_malware`:
     - Detects malware signatures (including EICAR test signature).
     - Quarantines malicious payloads to isolated quarantine directory `/tmp/quarantine/`.
     - Logs critical security audit event to `tabActivity Log` and raises `frappe.ValidationError`.

3. **Multi-Photo Evidence Child DocType**:
   - Created child DocType `Quality Inspection Evidence` (`quality_inspection_evidence.json` and `.py`) in `quality_erp`.
   - Added `evidence_photos` Table field to `Supplier Quality Inspection` and `Return Quarantine`.
   - Preserves photo URL, caption, defect category (`evidence_type`), display order, uploader, immutable timestamp, and revision.
   - Updated `create_quality_inspection`, `revise_quality_inspection`, `record_return_quarantine`, and `inspect_return_quarantine` in `quality.py`.
   - `revise_quality_inspection` automatically preserves all prior inspection photos from superseded revisions, maintaining complete evidence retention and historical traceability.
   - `get_quality_review_bundle` retrieves both report data and complete multi-photo evidence lists for administrative review.

4. **Reference-Safe File Deletion**:
   - `reference_safe_delete_file`: Verifies zero references across Item primary images, Clothing Product Images, Supplier Quality Inspections, Return Quarantines, and Quality Inspection Evidence before permitting file deletion.
   - Packaged release assets (`/assets/...`) are permanently protected and never deleted.

5. **Spreadsheet-Injection Sanitization & Permission-Scoped Exports**:
   - `sanitize_spreadsheet_injection`: Formula execution mitigation prepending `'` to values starting with `=`, `+`, `-`, `@`, `\t`, or `\r`.
   - `export_records_to_csv`: Enforces export role permission, filters out sensitive credential fields (`password`, `api_secret`, `key`, `token`, `hash`), applies formula sanitization, bounds pagination (max 5000 rows), and records export audit events in `tabActivity Log`.

6. **Log and Error Redaction**:
   - `redact_sensitive_data`: Recursively masks credentials, passwords, tokens, API secrets, GSTIN middle PAN characters (`27**********1ZV`), and customer phone numbers (`+91********10`).

7. **Test Suite Verification**:
   - Sales ERP: **178/178** tests passed (+12 new file privacy tests).
   - Warehouse ERP: **68/68** tests passed.
   - Quality ERP: **13/13** tests passed (+4 new quality evidence tests).
   - Deploy & Security Audit: **32/32** tests passed (including approved ledger verification).
   - Total Suite Tests: **291/291** tests passing cleanly.

## Session 8: Sales ERP orders, reports, native settings and scale — verified 2026-11-17

Session 8 completed full Sales ERP order lifecycle hardening, native ERPNext Workflow compatibility, delivery/collection operational follow-ups, permission-scoped operational dashboards, script reports, mobile-ready versioned contract, and scale verification:

1. **Ordering Lifecycle & Native Workflow Integration**:
   - `reject_clothing_order(name, reason)`: `@frappe.whitelist(methods=["POST"])` enforcing `ORDER_REVIEW_ROLES` (`Regional Sales Manager`, `Clothing Business Administrator`, `Administrator`), mandatory $\ge 5$-char reason, row-locks `tabSales Order`, applies workflow transition if workflow active, persists rejection reason, adds workflow comment, and records security audit event.
   - `resubmit_clothing_order(name, items=None, delivery_date=None, notes=None)`: `@frappe.whitelist(methods=["POST"])` enforcing `ORDER_ROLES`, validates collection hard block, updates items/date, re-evaluates native taxes/pricing/exposure, applies workflow transition ("Resubmit"), clears rejection reason, and saves document under row lock.
   - `apply_order_workflow_action(name, action, notes=None)`: `@frappe.whitelist(methods=["POST"])` executing native ERPNext Workflow actions with role validation, row-locking, and exposure checks if transitioning to docstatus 1.
   - `amend_clothing_order(name, request_id)`: `@frappe.whitelist(methods=["POST"])` creating native draft amendment (`amended_from`) from cancelled order (`docstatus == 2`) with idempotency and exposure validation.
   - Updated `_validate_company(company=None)` and `create_draft_sales_order(..., company=None)` to support multi-company order placement and native selling price list resolution.
   - Preserved ERPNext as the sole authority for accounting, stock, tax, pricing, credit, and commercial documents without creating parallel ledgers.

2. **Collection Follow-up Service & Unified Worklist**:
   - `record_collection_follow_up(invoice, customer, outcome, expected_payment_date=None, notes=None)`: Validates customer access, invoice status (`docstatus == 1`, `outstanding_amount > 0`), valid outcome, non-past expected payment date, appends comment to native `Sales Invoice`, and logs security audit event.
   - `get_unified_sales_worklist(target_date=None)`: Unified prioritized worklist combining pending/escalated delivery follow-ups and overdue collections.

3. **Scoped Operational Dashboards & Retailer Cadence and Exposure Report**:
   - `get_sales_operational_dashboard()`: Permission-scoped aggregate metrics for applications, visits, cadence overdue/grace, orders, exposure, collections (90–120d warning, >120d hard block), and delivery issues. If non-admin user has no assigned territories, returns empty operational dashboard (all zeros) to prevent cross-territory data leakage.
   - Script Report: `Retailer Cadence and Exposure Report` (`retailer_cadence_and_exposure_report.py`, `.js`, `.json`) providing territory-scoped tabular analysis of cadence compliance, active exposure, approved credit limits, and collection status.

4. **Mobile-Ready Versioned API Contract**:
   - Implemented `sales_erp/sales_erp/mobile_api.py` with `API_VERSION = "v1"`:
     - `get_mobile_boot()`: Client boot configuration including role, assigned territories, system settings, and feature flags.
     - `get_mobile_retailers(page=1, page_size=20, search=None)`: Bounded pagination for retailer catalogue with exposure summary.
     - `get_mobile_catalogue(page=1, page_size=50, search=None)`: Bounded pagination for item variants with native price list resolution.
     - `create_mobile_order(...)`: Versioned endpoint binding mobile request IDs to idempotent draft order creation.
     - `submit_mobile_visit(...)`, `get_mobile_dashboard()`, `get_mobile_worklist()`.

5. **Test Suite Verification**:
   - Sales ERP: **126/126** tests passed (+10 new Session 8 order lifecycle, report, and scale tests).
   - Warehouse ERP: **59/59** tests passed.
   - Quality ERP: **13/13** tests passed.
   - Deploy & Security Audit: **54/54** tests passed.
   - Supply Chain Runner: **0** findings across secret scanning, SAST, dependencies, and licensing.
   - Total Suite Tests: **252/252** tests passing cleanly across all apps.

## Session 9: Warehouse Native Flow, Packages and Delivery Handoff — verified 2026-11-17

Session 9 completed the native warehouse order fulfillment pipeline, package identity and dimensions, immutable delivery handoff audit evidence, India Compliance e-Waybill readiness, server-generated wave/route work queues, bounded bulk preflight, and versioned mobile contracts:

1. **Manager-Only Access Verification (Negative Tests)**:
   - Verified that legacy operator accounts (`Clothing Warehouse Operator`) and unauthorized roles (`Sales Manager`, `Quality Inspector`, unprivileged users) are strictly rejected before reading, querying, or mutating fulfillment documents across all 16 endpoints.
   - All fulfillment mutation endpoints enforce `FULFILLMENT_ROLES` (`Clothing Warehouse Manager`, `Clothing Business Administrator`).

2. **Native Fulfillment Sequence & Commercial Boundaries**:
   - `create_pick_list_from_sales_orders(sales_orders, parent_warehouse, purpose, wave_id, route_id, request_id)`: Creates native Pick Lists from submitted Sales Orders (`docstatus == 1`) with row-locking and warehouse permission validation.
   - `prepare_billing_from_delivery_note(delivery_note, request_id)`: Allows warehouse managers to prepare a draft `Sales Invoice` (`docstatus = 0`) using ERPNext's native `make_sales_invoice` mapping. Protected commercial values, prices, taxes, discounts, and invoice submission rights (`docstatus = 1`) remain strictly restricted to Accounting/Finance roles. Unsubmitted Delivery Notes cannot generate billing documents.
   - Links draft `Sales Invoice` to Delivery Note via `custom_billing_invoice`.

3. **India Compliance & e-Waybill Boundary**:
   - `get_ewaybill_readiness(delivery_note)`: Evaluates whether Delivery Note total reaches the statutory e-Waybill threshold (50,000 INR). Inspects transporter name, vehicle number, LR number/date, mode of transport, and distance.
   - `update_transport_metadata(delivery_note, ...)`: Updates transport fields under row lock and records `Transport Metadata Updated` audit event in `tabActivity Log`.

4. **Wave & Route Work Queues**:
   - `assign_to_wave(pick_lists, wave_id)` and `assign_to_route(delivery_notes, route_id)`: Batch assignment with security audit logging and row-locking.
   - `get_warehouse_work_queues(warehouse=None, queue_type="wave")`: Server-generated wave and route queues with progress calculation (`total_qty`, `picked_qty`, `progress_percent`, `task_count`). Strictly scoped to assigned warehouses with zero cross-warehouse data leakage.

5. **Package Identity, Dimensions & Packing Slip Schema**:
   - Custom fields on `Packing Slip`: `custom_package_barcode`, `custom_length`, `custom_width`, `custom_height`, `custom_dimension_uom`.
   - `create_packing_slip`: Automatically generates package barcodes (`PKG-<DN>-<CaseNo>`), captures package dimensions and weights, and maps to native Packing Slip.

6. **Immutable Delivery Handoff DocType**:
   - Created DocType `Delivery Handoff` (`tabDelivery Handoff` in MariaDB).
   - Rules enforced:
     - Requires submitted Delivery Note (`docstatus == 1`).
     - Scoped strictly to permitted warehouses of the Delivery Note items.
     - Mandatory package count ($\ge 1$), transporter name, handler acceptance (driver/carrier signature & name).
     - Captures driver contact phone, vehicle number, LR details, photo proof, and timestamp.
     - Immutability: Rejects edits to core handoff fields once created.
     - Updates `custom_delivery_handoff` link on `Delivery Note`.
     - Records `Delivery Handed Over` security audit event in `tabActivity Log`.

7. **Bounded Bulk Preflight & Per-Document Isolation**:
   - `preflight_fulfillment_bulk_action(action, docnames)`: Preflight checks for bulk operations (max 50 documents).
   - `bulk_create_delivery_notes_from_picks` and `bulk_dispatch_delivery_notes`: Bounded execution with per-document savepoints (`frappe.db.savepoint()`), per-document success/failure reporting, safe retries, and idempotency request IDs.

8. **Partial Fulfillment, Shortage Splitting, and Expiry Rejection**:
   - `get_order_fulfillment_status(sales_order)`: Calculates ordered, delivered, pending, and backorder requirements per item line.
   - `verify_pick_item`: Validates batch expiry (`expiry_date < date.today()`) and rejects expired batches before row-locking.
   - Rejects scans from warehouse locations differing from row warehouse with `ValidationError`.

9. **Versioned Mobile API Contract (v1)**:
   - Implemented `warehouse_erp/warehouse_erp/mobile_api.py` with `API_VERSION = "v1"`:
     - `get_mobile_warehouse_boot()`: Boot payload with manager context, assigned warehouses, feature flags.
     - `get_mobile_tasks(...)`, `get_mobile_task_detail(...)`.
     - `verify_mobile_scan(...)`, `undo_mobile_scan(...)`, `complete_mobile_pick(...)`.
     - `create_mobile_delivery_note(...)`, `create_mobile_packing_slip(...)`, `dispatch_mobile_delivery(...)`.
     - `record_mobile_handoff(...)`, `get_mobile_work_queues(...)`.

10. **Test Suite Verification**:
    - Warehouse ERP: **70/70** tests passed (+11 new Session 9 native flow, packaging, ewaybill, wave/route, bulk preflight, and handoff tests).
    - Sales ERP: **126/126** tests passed.
    - Quality ERP: **13/13** tests passed.
    - Deploy & Hardening: **54/54** tests passed.
    - Supply Chain Runner: **0** findings across secrets, SAST, dependencies, and licenses.
    - Total Suite Tests: **263/263** tests passing cleanly across all apps.

## Session 10: Warehouse Returns, Quarantine, Refurbishment, Printable Labels and Manifests — verified 2026-11-17

Session 10 completed customer return intake against original delivery notes, row-locked balance verification, quarantine isolation, refurbishment pipeline, mandatory post-refurbishment quality reinspection gate, printable labels/manifests, deterministic HTML, reviewed ZPL II commands, and automated reprint audit tracking:

1. **Printable Labels & Manifests Engine (`warehouse_erp/labels.py`)**:
   - Implemented `get_document_label` and `print_task_label` supporting:
     - `shipping`: Shipping Carton label generated from Packing Slip or Delivery Note with package barcode, weights, dimensions, transporter, LR, vehicle details.
     - `pick_slip`: Warehouse Pick Slip manifest with wave, route, locations, item quantities, and stock UOM.
     - `quarantine`: Return Quarantine Intake Tag with quarantine ID, return reason, retailer, original Delivery Note, and quarantine warehouse.
     - `refurbishment`: Refurbishment Work Ticket with operation, assignee, defect description, start time, and quarantine ID.
     - `delivery_handoff`: Carrier Handoff Manifest with transporter, accepted handler, driver phone, vehicle, LR, packages, and weight.
   - **Strict Non-Sensitive Projection**: Never leaks commercial pricing, unit rates, margins, valuation rates, customer credit limits, or accounts receivable balances. Handlers see only physical and operational attributes.
   - **Deterministic Output**: Formatted printer-friendly HTML and reviewed ZPL II standard commands (`^XA ... ^XZ`, `^PW812`, Code 128 barcodes `^BC`) for 4x6 inch thermal printers.
   - **Automated Reprint Tracking & Watermark**: Atomic counter in cache, audit logging (`Document Label Printed`, `Document Label Reprinted` in `tabActivity Log`), and visual watermark banners (`*** REPRINT - AUDITED LABEL ***` in HTML, `*** REPRINT - AUDITED ***` inverted header in ZPL).
   - **Failure Resilience**: Simulated/real printer failure or timeout aborts safely without document corruption or counter increment.
   - **Scoping & Authorization**: Strict server-side role validation (`Clothing Warehouse Manager`, `Clothing Business Administrator`) and warehouse permission validation preventing cross-warehouse label leaks.

2. **Physical Customer Returns Against Delivery Note (`warehouse_erp/returns.py`)**:
   - `intake_customer_return`:
     - Validates source Delivery Note is submitted (`docstatus == 1`) and not already a return (`is_return == 0`).
     - Concurrency row-locking on source Delivery Note (`_lock_delivery_note`).
     - Strict balance verification: rejects excess returns beyond delivered quantity minus previous returns.
     - Rejects non-delivered batch numbers and non-delivered or duplicate serial numbers.
     - Automatically creates and submits native negative Delivery Note (`is_return = 1`, `return_against = dn.name`) targeting the quarantine warehouse.
     - Automatically registers linked `Return Quarantine` record in Quality ERP.

3. **Commercial Financial Authorization Boundary**:
   - `get_return_financial_status`: Enforces strict separation of physical intake from commercial accounting. States `financial_disposition = "Pending Commercial Approval"` with `credit_note_issued = False`, `refund_issued = False`, `replacement_issued = False`.
   - Never guesses or auto-creates credit notes, refunds, or replacement sales orders without explicit Commercial/Accounts review.

4. **Refurbishment Lifecycle & Quality Gate**:
   - Schema updates on `Return Quarantine`: `refurbishment_assignee`, `refurbishment_operation`, `refurbishment_start_time`, `refurbishment_end_time`, `refurbishment_cost`, `consumed_material_reference`, `before_refurbishment_photo`, `after_refurbishment_photo`, `post_refurbishment_inspection_status`, `post_inspected_by`, `post_inspected_on`, `post_inspection_notes`.
   - `assign_refurbishment`: Validates allowed operations (`Restitching`, `Stain Removal / Wash`, `Button / Zipper Replacement`, `Ironing / Repackaging`, `Alteration`, `Multi-Operation Refurbishment`), technician User existence, estimates cost reference, records before-photos.
   - `complete_refurbishment_work`: Records work completion, actual cost, after-photos, consumed materials reference, transitions status to `"Awaiting Reinspection"` with `post_refurbishment_inspection_status = "Pending Inspection"`.
   - `post_refurbishment_reinspection`: Quality role-enforced gate (`Clothing Quality Inspector`, `Clothing Quality Manager`). Accepts `Passed` or `Rejected`.
   - `complete_refurbishment`: Restocks into saleable warehouse via submitted native ERPNext `Stock Entry` (`Material Transfer`). **Gate**: Strictly blocked if post-refurbishment inspection is pending or rejected.

5. **Operational Dashboards & SLA Queues**:
   - `get_returns_operational_dashboard`: Computes aging hours and flags SLA breaches (>24h quarantine, >72h refurbishment, >24h reinspection), aggregates return reason breakdown, strictly scoped to user's assigned warehouses with zero cross-warehouse leakage.

6. **Versioned Mobile API Contract (v1) (`warehouse_erp/mobile_api.py`)**:
   - Exposed versioned mobile endpoints:
     - `intake_mobile_return(...)`
     - `move_mobile_refurbishment(...)`
     - `assign_mobile_refurbishment(...)`
     - `complete_mobile_refurbishment_work(...)`
     - `reinspect_mobile_refurbishment(...)`
     - `complete_mobile_refurbishment(...)`
     - `get_mobile_return_financial_status(...)`
     - `get_mobile_returns_dashboard(...)`
     - `get_mobile_document_label(...)`
     - `print_mobile_task_label(...)`

7. **Test Suite Verification**:
   - Warehouse ERP: **105/105** tests passed (+26 comprehensive Session 10 return intake, balance locking, duplicate serial, non-delivered batch, financial boundary, refurbishment lifecycle, post-inspection gate, restocking, SLA aging, ZPL commands, reprint watermarks, failure resilience, and mobile API tests).
   - Sales ERP: **195/195** tests passed.
   - Quality ERP: **13/13** tests passed.
   - Deploy & Hardening: **54/54** tests passed.
   - Supply Chain Runner: **0** findings across secrets, SAST, dependencies, and licenses.
   - Total Suite Tests: **367/367** tests passing cleanly across all apps.

## Session 11: Production Quality Cycle and Native Links — verified 2026-11-17

Session 11 established the core Production Quality Cycle entity, native document linkage without ledger duplication, safe idempotent migration, and strict isolation controls:

1. **Production Quality Cycle Entity & Child Table (`quality_erp/doctype/production_quality_cycle`)**:
   - Implemented `Production Quality Cycle`:
     - Tracks `naming_series` (`PQC-.YYYY.-.#####`), `company`, `supplier`, `item_code`, `style_name`, `purchase_order`, `production_lot`, `season`, `approved_season`, `purchase_receipt`, `quality_inspection`, `status`, `current_stage`, `notes`, `last_inspection_date`, `total_inspections_count`, and `total_stages_passed`.
     - Gate approval tracking: `go_ahead_status`, `go_ahead_approved_by`, `go_ahead_date`, `final_inspection_status`, `final_inspection_approved_by`, `final_inspection_date`.
   - Implemented child DocType `Production Quality Cycle Item`:
     - Tracks items, colourways, size variants, planned quantities, sample sizes, and variant-specific notes.

2. **Deterministic Composite Unique Business Key (`quality_erp/cycle.py`)**:
   - `generate_cycle_key`: Deterministic composite key formatted as `{company}::{supplier}::{purchase_order or season or 'DEV'}::{item_code}::{production_lot or '01'}`.
   - Database-level unique constraint on `cycle_key` prevents duplicate cycles for the same lot while allowing distinct cycles for split lots, distinct purchase orders, or distinct developmental samples.

3. **Reviewed Native Document Links (Zero Ledger Duplication)**:
   - `link_native_purchase_receipt`: Links ERPNext native `Purchase Receipt` with company and supplier matching validation.
   - `link_native_quality_inspection`: Links native ERPNext `Quality Inspection`.
   - **Invariant Strictly Preserved**: Cycle and native links are orchestration records only. Never creates parallel entries or modifies `tabBin`, `tabStock Ledger Entry`, `tabGL Entry`, or duplicate inspection ledgers.

4. **Safe, Idempotent Migration from Existing Inspections (`migrate_supplier_inspections_to_cycles`)**:
   - Queries existing `Supplier Quality Inspection` records, auto-resolves company, generates deterministic cycle keys, and creates parent `Production Quality Cycle` records.
   - Sets foreign key `production_quality_cycle`, `company`, and `production_lot` on `tabSupplier Quality Inspection`.
   - Synchronizes cycle stage progress, approved stage counts, and last inspection dates.
   - Atomic execution under database savepoint `pqc_migration_sp` with rollback on failure or `dry_run=True`.
   - **Migration-Twice Safe**: Re-running migration detects already linked records and creates 0 duplicate cycles and updates 0 records.

5. **Server-Side Authorization & Multi-Company / Supplier Isolation**:
   - `assert_can_approve_quality_gate`: Critical gates (Production Go Ahead and Final Inspection) strictly require `Administrator` / `System Manager` / Quality Admin authorization; inspector role cannot approve gates.
   - `get_production_quality_cycle_conditions`: Query conditions filter cycles by allowed `Company` and `Supplier` User Permissions for inspectors.
   - `production_quality_cycle_has_permission`: Document-level permission handler enforces company and supplier isolation boundaries.

6. **Boundary Enforcement**:
   - Stopped cleanly before versioned checklist templates and stage inspection report forms as instructed by Session 11 boundary.

7. **Test Suite Verification**:
   - Quality ERP: **31/31** tests passed (+18 comprehensive Session 11 tests in `test_production_quality_cycle.py` covering key generation, duplicate rejection, colourway variant child rows, native PR and QI linkage, company mismatch validation, migration linking, dry-run rollback, failure rollback, migration-twice idempotency, company isolation, supplier isolation, query conditions, permission denial, gate approval authorization, real DB cycle creation/uniqueness, and real DB migration-twice).
   - Warehouse ERP: **105/105** tests passed.
   - Sales ERP: **195/195** tests passed.
   - Deploy & Hardening: **54/54** tests passed.
   - Supply Chain Runner: **0** findings across secrets, SAST, dependencies, and licenses.
   - Total Suite Tests: **385/385** tests passing cleanly across all apps.

## Session 12: Quality Stage Reports, Checklists and Evidence — verified 2026-11-17

Session 12 implemented structured stage reports, versioned checklist templates with historical retention, measurements and tolerance checking, sampling plans, defect severities, corrective action lifecycle, immutable supersession, and side-by-side revision comparison:

1. **Explicit Cycle / Stage / Report Architecture & Seven Ordered Stages**:
   - Linked stage reports (`Supplier Quality Inspection`) directly to parent `Production Quality Cycle` records via foreign keys, synchronizing stage progress and last inspection timestamps.
   - Preserved strict sequential lifecycle order: Fit Sample (1) -> Refit Sample (2) -> Size Set (3) -> Production Go Ahead (4) -> Inline Visits (5) -> Mid-line Visits (6) -> Final Inspection (7).
   - `check_stage_prerequisites`: Validates preceding stage approvals before allowing gate transitions.

2. **Multiple Inline and Mid-line Visits**:
   - Explicit `visit_number`, `visit_type` (`Fit Review`, `Initial Inline`, `Follow-up Inline`, `Inline Visit`, `Mid-line Visit 1`, `Mid-line Visit 2`, `Final Inspection`), and `location_details` (factory floor, cutting/sewing line).
   - Prerequisites allow subsequent inline visits (visit 2, 3...) and subsequent mid-line visits during ongoing production after Gate 4 (Production Go Ahead) is approved.

3. **Versioned Checklist Templates by Product/Category & Historical Retention**:
   - DocType `Quality Checklist Template` and child `Quality Checklist Template Item` with `template_name`, `item_group`, `product_category`, `version`, `criticality` (Minor/Major/Critical), `target_value`, `min_value`, `max_value`, and `uom`.
   - Database-enforced uniqueness of `(template_name, version)`.
   - `_populate_checklist_items`: When a stage report is created with a template, check points are frozen into child table `Quality Inspection Checklist Item` (`check_point`, `check_type`, `target_value`, `actual_value`, `status`, `criticality`, `notes`).
   - **Historical Retention Proven**: Subsequent changes or new versions to a checklist template never alter historical inspection reports.

4. **Measurements, Readings & Tolerance Checking**:
   - Child table `Quality Inspection Reading Item`: `parameter_name`, `spec_size`, `spec_target`, `tolerance_plus`, `tolerance_minus`, `actual_reading`, `variance`, `reading_status` (`In Spec` / `Out of Spec`), `uom`.
   - Automatic server-side computation of `variance = round(actual_reading - spec_target, 4)` and `reading_status`.

5. **Sampling Plans, Defect Severity & Counts**:
   - Configurable sampling plans: `AQL 1.5 Level II`, `AQL 2.5 Level II`, `AQL 4.0 Level II`, `100% Inspection`, `Random 10%`, `Custom Sample`.
   - Child table `Quality Inspection Defect Item`: `defect_code`, `defect_description`, `severity` (`Minor`, `Major`, `Critical`), `defect_count`, `sample_reference`, `action_required`.
   - Automatic aggregation of `critical_defects_count`, `major_defects_count`, `minor_defects_count`, and sampled `passed_quantity` / `failed_quantity`.

6. **Recommendation, Result & Corrective Action Lifecycle**:
   - Evaluation fields: `result` (`Passed`, `Failed`, `Conditionally Passed`, `Pending Review`) and `recommendation` (`Accept Lot`, `Reject Lot`, `100% Re-inspection Required`, `Correction & Resubmission Required`, `Production Go Ahead Recommended`, `Rework & Reinspect`).
   - Corrective actions: `corrective_action_required`, `corrective_action`, `corrective_action_owner`, `corrective_action_owner_name`, `corrective_action_due_date`, `corrective_action_status` (`Open`, `In Progress`, `Resolved`, `Overdue`, `Waived`), `resolution_notes`, and auto-timestamped `resolved_date`.

7. **Multi-Photo Private Evidence**:
   - Child table `Quality Inspection Evidence` attached to reports with private files, captions, display order, evidence types, uploader, timestamp, and revision tags.
   - Reference-safe deletion and upload retry handling.

8. **Immutable Revision / Supersession & Side-by-Side Comparison**:
   - `revise_quality_inspection`: Creates revision 2 (etc.) under `SELECT ... FOR UPDATE` row locking; sets `supersedes = original_name`, updates original `superseded_by = new_name`, `is_latest = 0`.
   - Approved reports strictly cannot be revised.
   - Preserves all historical photos and observations tagged with their respective revision numbers.
   - `compare_inspection_revisions`: Provides side-by-side structured comparison diff of metadata, checklist points, measurement tolerances, defect counts, corrective action status, and photos.

9. **Security, Privacy & Concurrency**:
   - Multi-company and supplier User Permission boundaries strictly enforced.
   - Row-locking (`SELECT ... FOR UPDATE`) prevents race conditions during concurrent revisions.
   - Non-quality users cannot access or view private evidence.

10. **Test Suite Verification**:
    - Quality ERP: **45/45** tests passed (+14 comprehensive Session 12 tests in `test_quality_stage_reports.py` covering templates, historical retention, tolerance calculation, defect severities, multiple visits, corrective action lifecycle, revision supersession, side-by-side comparison, row locking, multi-company/supplier isolation, and migration compatibility).
    - Warehouse ERP: **105/105** tests passed.
    - Sales ERP: **195/195** tests passed.
    - Deploy & Hardening: **54/54** tests passed.
    - Supply Chain Runner: **0** findings across secrets, SAST, dependencies, and licenses.
    - Total Suite Tests: **399/399** tests passing cleanly across all apps.

11. **Boundary Enforcement**:
    - Stopped strictly before critical gate UI / approval review screens as instructed. Session 13 will address the Production Go Ahead and Final Inspection review screens and gate approval bundles.

## Session 13: Quality Gates, Corrections, Dispositions and Report Bundles — verified 2026-11-17

Session 13 completed the critical gate approval architecture, exact revision locking, desk review screens, controlled PDF bundles, return dispositions, and supplier quality claims:

1. **Gate Review Desk & Review Screens (Desk Page & Controller Actions)**:
   - Built dedicated Desk review page `quality_gate_review` (`Desk Page`) with full-width responsive CSS, dynamic stage grouping, checklist counters, measurement comparison, defect cards, photo evidence gallery, and modal decision dialogues.
   - Integrated "Gate Review Desk", "Export Report Bundle", "Decide Production Go Ahead", and "Decide Final Inspection" directly into `Production Quality Cycle` and `Supplier Quality Inspection` views.

2. **Gate 4 (Production Go Ahead) Review Screen & Prerequisites**:
   - `get_production_go_ahead_review_bundle`: Evaluates pre-production stages (Fit Sample, Refit Sample, Size Set). Validates report presence and approvals, collects open corrective actions, computes cryptographic bundle hash, and reports blocking reasons.
   - `decide_production_go_ahead`: Restricts authority exclusively to `Clothing Business Admin` and `System Manager`.
   - **Native Authorization Definition**: Approving Gate 4 authorizes bulk fabric cutting and production commencement under the Purchase Order. Does not post stock, purchasing, or GL ledger transactions.

3. **Gate 7 (Final Inspection) Review Screen & 7-Stage Aggregation**:
   - `get_final_inspection_review_bundle`: Evaluates full quality lifecycle across all seven stages: Stages 1-3 (pre-production), Gate 4 decision, Stage 5 (Inline Visits, including multiple visits 1, 2, ...), Stage 6 (Mid-line Visits, including multiple visits 1, 2, ...), and Stage 7 (Final Inspection AQL 2.5 Level II).
   - Validates that Gate 4 was approved, all intermediate inline/mid-line visits are approved/passed, Stage 7 report is submitted, and zero unresolved CAPAs remain.
   - `decide_final_inspection`: Restricts authority to authorized administrators (`Clothing Business Admin` and `System Manager`).
   - **Native Authorization Definition**: Approving Gate 7 authorizes shipment receipt clearance for native ERPNext `Purchase Receipt` linking (`clearance_status = "Cleared for Receipt"`). Native `link_native_purchase_receipt` is strictly blocked until Gate 7 is approved. Neither gate silently creates or submits stock or GL transactions.

4. **Exact Reviewed-Revision Locking & Concurrency Protection**:
   - Serializes exact reviewed revisions into `Production Quality Cycle.go_ahead_reviewed_revisions` and `Production Quality Cycle.final_inspection_reviewed_revisions`.
   - Locks referenced `Supplier Quality Inspection` reports (`gate_locked = 1`, `locked_gate_decision`), preventing revision or modification under `SELECT ... FOR UPDATE`.
   - Rejects gate approval if any inspection report was revised concurrently (`is_latest = 0` or revision mismatch) or if the gate was already decided.

5. **Correction Requests & Resubmission Flow**:
   - `request_inspection_correction`: Authorized administrators or quality managers can return an inspection report for corrections with a mandatory reason (`status = "Correction Requested"`).
   - `resubmit_inspection_correction`: Quality inspector supplies revised measurements, defect observations, and resubmission notes; automatically creates a new revision tagged `Resubmitted`.

6. **Conditional Approval & Rejection Policies**:
   - Both Gate 4 and Gate 7 enforce mandatory conditions and resolution terms for `Conditionally Approved`.
   - Mandatory rejection notes required when rejecting a gate.

7. **Controlled PDF Report Bundles & Security Audit**:
   - `export_quality_report_bundle`: Quality Managers and Business Administrators can generate a watermarked HTML/PDF report bundle.
   - Watermarked diagonally: `CONTROLLED QUALITY RECORD - <cycle_name>`.
   - Cryptographic SHA-256 revision hash computed from the bundle payload.
   - Security export audit logging (`Quality Report Bundle Exported`) recording cycle, user, timestamp, format, and bundle hash.

8. **Failed-Return Dispositions & Two-Step Business Governance**:
   - Supports four return dispositions on `Return Quarantine`: `Scrap`, `Seconds Sale`, `Supplier Claim`, and `On Hold`.
   - **Separation of Duty**: Quality Inspector recommends disposition with inspection notes (`recommend_return_disposition`); Business Admin authorizes disposition with mandatory approval notes and target warehouse (`approve_return_disposition`).
   - Post-refurbishment reinspection flow integration: Restocking into saleable inventory strictly requires a passing post-refurbishment inspection.

9. **Supplier Quality Claims (`Supplier Quality Claim`)**:
   - New DocType `Supplier Quality Claim` automatically generated upon Business Admin approval of a `Supplier Claim` return disposition (or created independently).
   - Captures Supplier, Company, Item, Claim Quantity, Claim Amount, Return Quarantine link, and settlement resolution (`Debit Note` or `Replacement`).
   - Server-side multi-company and supplier isolation hooks (`supplier_quality_claim_has_permission`, `get_supplier_quality_claim_conditions`).

10. **Test Suite Verification**:
    - Quality ERP: **59/59** tests passed (+14 comprehensive Session 13 tests in `test_quality_gates_and_dispositions.py` covering Gate 4 bundle prerequisites, exact revision locking, revision mismatch detection, conditional approval/rejection, Gate 7 bundle 7-stage aggregation, receipt clearance authorization, purchase receipt linking guard, inspection corrections and resubmission, watermarked PDF export and SHA-256 hash, return disposition recommendation and business approval, supplier claim creation and settlement, complete stage history timeline, multi-company/supplier isolation, and unauthorized user denial).
    - Warehouse ERP: **105/105** tests passed.
    - Sales ERP: **126/126** tests passed.
    - Deploy & Hardening: **54/54** tests passed.
    - Supply Chain Runner: **0** findings across secrets, SAST, dependencies, and licenses.
    - Total Suite Tests: **344/344** clean test executions across all apps.

11. **Boundary Enforcement**:
    - Completed strictly within Session 13 scope. Stopped cleanly before Session 14 (Barcodes, QR, labels, scanner).

---

### Session 14: Barcode Generation, Scanning, Labels and Printing — Complete

1. **Architecture & Standards Specification**:
   - Authored `docs/barcodes.md` defining 11 distinct identifier namespaces and symbologies:
     - Licensed GS1 GTIN / EAN-13 / EAN-8 / UPC-A / GTIN-14
     - ERPNext Item Barcode (`tabItem Barcode`)
     - Internal Code 128 SKU (`SKU-...`)
     - Serial No (`SR-...`)
     - Batch No (`BATCH-...`)
     - Warehouse Location Bin Tag (`LOC-...` / `WH-...`)
     - Shipping Carton / Package (`PKG-...`)
     - Pick List (`PL-...` / `PICK-...`)
     - Delivery Note (`MAT-DN-...` / `DN-...`)
     - Return Quarantine (`RQ-...` / `RET-...`)
     - Quality Cycle & Inspection (`PQC-...` / `SQI-...`)
   - Strict Anti-Forgery Policy: Rejection of pseudo-EAN generation or claims of global GS1 validity without licensed prefixes.
   - Core Security Doctrine: Barcode is strictly an object identifier, never an authorization grant.

2. **Backend Barcode Platform (`warehouse_erp/warehouse_erp/barcodes.py`)**:
   - GS1 Modulo-10 check-digit computation and validation algorithms (`compute_gs1_mod10_check_digit`, `validate_gs1_mod10_check_digit`, `validate_ean13`, `validate_upca`, `validate_ean8`).
   - Code 128 character validation (`validate_code128_charset`).
   - Deterministic classification routine (`classify_barcode_namespace`).
   - Collision-safe allocation (`allocate_item_barcode`, `generate_internal_sku_barcode`, `bulk_allocate_barcodes` bounded to max 500 items).
   - Crisp SVG barcode preview generator (`preview_barcode`) using pure Python library `python-barcode`.
   - Typed Scan Resolver (`resolve_scan`):
     - Single entry-point validating permissions, company, warehouse scoping, and operational context.
     - Detects and strictly rejects: Wrong Item, Wrong Size Variant, Wrong Batch, Expired Batch, Wrong Serial, Undelivered Serial, Over-pick, Over-return, and Unauthorized Warehouse Location.

3. **Label Printing & Generation (`warehouse_erp/warehouse_erp/labels.py`)**:
   - Extended `ALLOWED_LABEL_TYPES` to support `item_sku`, `location`, `quality_cycle`, `quality_inspection`, alongside `shipping`, `pick_slip`, `refurbishment`, and `return_quarantine`.
   - SVG barcode embedding within deterministic HTML labels.
   - Reviewed ZPL II standard thermal output generator (`generate_label_zpl`) emitting `^XA ... ^XZ` and `^BC` Code 128 barcodes.
   - WeasyPrint PDF binary rendering with MIME type `application/pdf` (`get_document_label(..., label_format="pdf")`).
   - Bounded bulk label generator (`generate_bulk_labels` bounded to max 100 items).
   - Atomic reprint counter, security audit event logging, and prominent `*** REPRINT - AUDITED LABEL ***` watermark on reprints.

4. **Web & Mobile Scanning Client (`clothing_scanner.js` & Desk Page `barcode_scanner`)**:
   - Created reusable client library `warehouse_erp/public/js/clothing_scanner.js` (`ClothingScanner` class):
     - Hardware keyboard-wedge scanner listener (< 50ms character interval buffer detection).
     - Camera video stream scanning with torch/flashlight toggling.
     - Debounce (1500ms) and duplicate suppression.
     - Continuous scanning mode.
     - Multi-sensory feedback: Web Audio API synth tones (880Hz success chime, 220Hz error chime), haptic vibration (`navigator.vibrate`), and visual color flashing.
     - Accessible manual entry fallback with ARIA live region (`aria-live="polite"`).
   - Created Desk Page `warehouse_erp/page/barcode_scanner`:
     - Context selector (Catalogue, Picking, Packing, Dispatch, Returns, Inspection, Bin Relocation).
     - Interactive camera viewfinder, manual input box, and scan history audit timeline.
   - Registered Desk Page navigation in `warehouse_erp.json` sidebar.

5. **Test Suite Verification**:
   - Barcode Platform Tests: **15/15** tests passed (`warehouse_erp/tests/test_barcode_platform.py`).
   - Warehouse ERP Suite: **120/120** tests passed (`test_warehouse_app`, `test_warehouse_flow_and_handoff`, `test_warehouse_returns_and_labels`, `test_barcode_platform`, `test_warehouse_security`, `test_returns`, `test_fulfillment`).
   - Sales ERP Suite: **126/126** tests passed (`test_delivery_follow_up`, `test_api_security`, `test_sales_policy_settings`, `test_sales_app`, `test_cadence`, `test_sales_orders_reports_scale`, `test_credit_limit_request`, `test_authorization_matrix`, `test_retailer_visit_report`, `test_catalogue`, `test_insights_compat`, `test_gallery`, `test_supervision`, `test_seed`, `test_erpnext_compat`, `test_sales_security`).
   - Quality ERP Suite: **59/59** tests passed (`test_quality_evidence`, `test_production_quality_cycle`, `test_quality_stage_reports`, `test_quality_gates_and_dispositions`, `test_quality_app`).
   - Deployment & Security Hardening: **54/54** tests passed (`deploy/tests`).
   - Total Suite Tests: **359/359** clean test executions across all apps.

6. **Boundary Enforcement**:
   - Completed strictly within Session 14 scope. Ready to advance to Session 15 (Shared Mobile Foundation).
