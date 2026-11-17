# Antigravity production session prompt pack

Use this prompt pack to keep Antigravity focused without loading the entire implementation
programme into one context window.

## How to use this file

For every new Antigravity session:

1. Start a new Antigravity conversation/context.
2. Copy the **Base prompt**.
3. Copy only the relevant numbered **Session chunk**.
4. Let Antigravity finish, test, document and commit that bounded session.
5. Start another fresh context for the next session.
6. If the session was not completed, use the **Continuation prompt** instead of advancing.

The authoritative detailed checklist remains the section named **Production security,
mobile applications and barcode programme** at the top of [`../work.md`](../work.md).

---

## Base prompt — paste before every session

```text
You are Antigravity, continuing development of the Clothing ERP Suite.

Repository:
/home/avi/GitHub/erp/clothing_erp

Remote:
https://github.com/AviDhandhania/erp.git

This is one bounded session in a multi-session production programme. Do not start work
from another session after completing this one.

Canonical instructions

Before taking action, read completely:

1. `AGENTS.md`
2. The top section of `work.md` named:
   `Production security, mobile applications and barcode programme — OPEN 2026-11-17`
3. The specific subsection relevant to this session
4. The relevant operating-model document:
   - Sales: `docs/field-sales-operating-model.md`
   - Warehouse/Quality: `docs/warehouse-quality-operating-model.md`
5. `docs/architecture.md`
6. Every source file you intend to change

The current uncommitted `work.md` production programme was intentionally added by Codex.
Preserve it. Do not overwrite, revert or discard it. Include it in the first coherent
audit/roadmap commit if it is still uncommitted.

Start-of-session checks

Run:

- `git status --short --branch`
- `git log -10 --oneline`
- Inspect all existing changes before editing.
- Check Git status of the separate Frappe, ERPNext, Insights and India Compliance repositories.
- Identify the most recently completed Antigravity session from `work.md` and Git history.
- If the previous session is incomplete, continue it instead of advancing.

Absolute rules

- Never modify Frappe, ERPNext, Insights or India Compliance source.
- Never commit inside upstream repositories.
- Never discard or overwrite user changes.
- Never use real customer, supplier, employee, financial or personal data.
- Never commit credentials, secrets, tokens, private keys or signing material.
- Enforce authorization server-side; UI visibility is not security.
- Preserve ERPNext as the authority for accounting, stock, tax, pricing, credit,
  commission, purchasing and commercial documents.
- Never directly write Bin, Stock Ledger Entry, GL Entry or receivable balances.
- Every mutation must be POST-only, authorized, object-scoped, validated,
  concurrency-safe, auditable and idempotent where retries are possible.
- Never mark a task complete based only on code existing.
- Do not claim a mathematically zero possibility of leakage. Require zero known exposure,
  defence in depth and no unresolved critical/high findings.
- Use `apply_patch` for manual edits.
- Preserve unrelated changes.

Commit rules

Every Antigravity commit must:

- Begin with `[antigravity]`.
- Include `Agent: Antigravity` in the body or trailer.
- Contain one coherent, reviewable change.
- Avoid unrelated formatting or refactoring.
- Leave the working tree clean unless explicitly documenting preserved user changes.

Testing requirements

Run tests proportional to the change. When relevant, use:

export LD_LIBRARY_PATH=/home/avi/GitHub/erp/.services/usr/lib:${LD_LIBRARY_PATH:-}

/home/avi/GitHub/erp/bench --site clothing.local run-tests --app sales_erp --test-category all
/home/avi/GitHub/erp/bench --site clothing.local run-tests --app warehouse_erp --test-category all
/home/avi/GitHub/erp/bench --site clothing.local run-tests --app quality_erp --test-category all
/home/avi/GitHub/erp/frappe-bench/env/bin/python -m unittest discover -s deploy/tests -v

Also run, where relevant:

- Python compilation
- JSON validation
- JavaScript syntax validation
- shell syntax and ShellCheck
- migration twice
- browser/mobile tests
- security/static/dependency scans

Do not hide failures. Record exact commands, counts and failures. If a test cannot run,
leave the associated task unchecked and explain why.

Required end-of-session actions

Before stopping:

1. Update `work.md` with:
   - session number and scope;
   - files changed;
   - decisions made;
   - exact test results;
   - security findings;
   - unresolved risks;
   - business decisions required;
   - recommended next session.
2. Update affected documentation.
3. Verify upstream repositories remain unchanged.
4. Commit completed coherent work using the Antigravity attribution rules.
5. Report the commit hash.
6. Report `git status`.
7. Stop. Do not begin the next session.

Session-specific instructions follow below.
```

---

## Session 1 — Security audit ledger

```text
SESSION 1: SECURITY AUDIT LEDGER AND TRUTHFUL BASELINE

Perform only Session 1 from the production programme.

Create:

- `docs/security/threat-model.md`
- A data-flow diagram
- A sensitive-data inventory
- A role/operation matrix
- A whitelisted endpoint inventory
- A privileged-write inventory
- A raw SQL inventory
- A File/upload/export inventory
- A security finding register with severity, evidence, owner and status

Audit every:

- `@frappe.whitelist`
- `ignore_permissions`
- `flags.ignore_permissions`
- `frappe.db.set_value`
- raw SQL query and mutation
- `delete_doc`
- file upload/deletion
- report/export
- scheduler
- bulk operation
- release download
- backup/restore path

Do not fix unrelated findings in this session unless a critical exposed vulnerability
requires an immediate minimal fix.

Reconcile stale documentation and remove misleading production percentage claims. Preserve
historical information but clearly mark it historical.

Add static inventory tests where useful.

Commit the intentionally added `work.md` production programme with this audit if it remains
uncommitted.

Stop after documenting and prioritizing findings.
```

---

## Session 2 — Authorization and role isolation

```text
SESSION 2: AUTHORIZATION, ROLE ISOLATION AND MANAGER-ONLY WAREHOUSE

Use Session 1's access matrix and finding register.

Complete the manager-only warehouse migration:

- Remove active Clothing Warehouse Operator authorization.
- Remove it from server security decisions.
- Remove it from pages, workspaces, boot filtering and seed accounts.
- Remove cross-app compatibility grants.
- Retain only an idempotent migration for existing operator users.
- Convert existing users to Warehouse Manager safely.
- Remove stale permissions and clear caches.
- Preserve immutable migration/audit evidence.

Test:

- ASM/RSM Territory isolation
- RSM supervision boundaries
- Warehouse assignment boundaries
- Quality Supplier/company boundaries
- disabled users
- ended supervision
- removed Warehouse permissions
- role removal
- permission-cache invalidation
- direct API and URL access
- attachments, reports and exports
- cross-app denial

No role should gain data merely because it knows a document name.
```

---

## Session 3 — API and transaction security

```text
SESSION 3: API VALIDATION, RATE LIMITS, IDEMPOTENCY AND TRANSACTIONS

Use the endpoint and privileged-write inventory.

For every endpoint:

- Classify read versus mutation.
- Make mutations POST-only.
- Add explicit input types, enums, normalization and bounds.
- Bound pagination, arrays and bulk requests.
- Reject unexpected structured fields.
- Enforce role and object scope before data access.
- Add rate limits appropriate to operation risk.
- Add idempotency to retryable writes.
- Bind idempotency to user, operation, scope and payload.
- Add expiry and defined replay behavior.
- Define transaction boundaries.
- Ensure failure cannot commit partial business state.
- Add row locking and deadlock/retry handling where necessary.
- Add immutable audit events.

Review every raw SQL and privileged write. Add focused negative tests for each approved
exception. Do not refactor unrelated business workflows.
```

---

## Session 4 — Files, photographs and privacy

```text
SESSION 4: FILE SECURITY, MULTI-PHOTO EVIDENCE AND PRIVACY

Make evidence files private by default.

Implement and test:

- parent-document authorization for File downloads
- upload count and size limits
- MIME signature and extension checks
- image dimension/decompression limits
- safe server-side filenames
- executable/polyglot rejection
- malware quarantine/scanning design
- reference-safe deletion
- retention behavior
- failed and repeated upload handling
- backup/restore of evidence
- export permission checks
- spreadsheet-injection protection
- PDF/report watermark and revision identifiers
- sensitive log redaction

Replace single Quality image fields with a multi-photo evidence child model containing:

- private File
- evidence type
- caption
- display order
- uploader
- immutable timestamp
- report revision

Preserve rejected and superseded evidence. Add migrations and rollback-safe tests.
```

---

## Session 5 — Deployment and host security

```text
SESSION 5: HTTPS, LXC, SYSTEMD AND SERVICE HARDENING

Harden production deployment without modifying upstream code.

Implement:

- HTTPS before real-data onboarding
- operator-supplied certificate mode
- documented ACME/domain mode
- HTTP-to-HTTPS redirect
- correct site URL
- secure cookies
- HSTS only after HTTPS is proven
- CSP and security headers
- clickjacking, MIME, referrer and permissions policies
- safe initial Administrator password delivery
- forced password-change procedure
- credential-file deletion procedure
- LXC firewall defaults
- minimal container capabilities
- no unnecessary nesting
- systemd sandboxing
- explicit service read/write paths
- MariaDB and Redis local-only access
- secure filesystem permissions
- log rotation
- resource limits
- security-update procedure

Verify private site files, configs, credentials and backups are not world-readable.
Test every service after hardening.
```

---

## Session 6 — Supply chain, backups and recovery

```text
SESSION 6: SUPPLY CHAIN, SIGNED RELEASES AND DISASTER RECOVERY

Implement:

- immutable SHA pinning for GitHub Actions
- minimum workflow permissions
- protected release environment guidance
- secret scanning, including Git history
- Python, JavaScript and mobile dependency scanning
- license scanning
- SAST
- SBOM generation
- exact dependency locks
- independent publisher provenance verification in installer/updater
- repository, identity, subject, version and redirect validation
- emergency release and revocation procedure

Implement encrypted off-host backups for:

- database
- public/private files
- site configuration
- required encryption keys
- release metadata
- necessary queue state

Keep backup keys separate from backups.

Automate isolated restore verification and define RPO/RTO, retention, monitoring, failure
alerts, restore authorization, secure deletion and ransomware/operator-error drills.
```

---

## Session 7 — Sales ERP policy and settings

```text
SESSION 7: SALES ERP POLICY, SETTINGS AND APPLICATION/VISIT CLOSURE

Resolve or explicitly defer business decisions for:

- Buy & Sell — Stock Correction
- EBOC
- shop-stock ownership
- exposure valuation
- seasonal calendar
- visit evidence
- collection escalation
- RSM capacity guidance versus hard limits

Do not invent unresolved accounting or ownership policy.

Complete the bounded first half of Sales production closure:

- administrator-managed cadence and warning settings
- application queues
- request-more-information/resubmission
- RSM-owned commercial fields
- initial exposure proposal
- administrator-approved exposure changes
- immutable approval history
- visit check-in/evidence/privacy policy
- monthly, quarterly, seasonal and 80/85-day obligations
- permission-scoped notifications and escalations

Add negative authorization, retry, boundary-date, concurrency and migration tests.
Stop before Session 8 order/report work.
```

---

## Session 8 — Sales ERP orders, reports and scale

```text
SESSION 8: SALES ERP ORDERS, REPORTS, NATIVE SETTINGS AND SCALE

Complete the second half of Sales production closure:

- order return/reject/resubmit/amend
- native ERPNext Workflow behavior
- native pricing, tax, discount, credit, reservation and commission behavior
- delivery follow-up and collection worklists
- scoped dashboards and reports
- mobile-ready versioned Sales API contract

Test:

- multi-company
- multi-currency
- Pricing Rules
- GST/India Compliance
- Sales Team commission
- taxes and discounts
- stock reservations
- partial delivery and returns
- cancellation
- concurrent orders
- 250+ shops per RSM
- duplicate mobile submissions
- aggregate-query scope leakage

Do not create parallel accounting, pricing, credit or receivables ledgers.
```

---

## Session 9 — Warehouse native flow and packages

```text
SESSION 9: WAREHOUSE NATIVE FLOW, PACKAGES AND DELIVERY HANDOFF

Complete the bounded first half of Warehouse production closure:

- final manager-only access verification
- native Sales Order → Pick List → Packing Slip → Delivery Note flow
- explicitly defined billing authority
- India Compliance/e-Waybill boundary
- wave and route queues
- bulk preflight
- per-document results
- job progress and safe retry
- partial fulfilment
- backorders and shortages
- Serial, Batch, Bundle and expiry handling
- package identity, count, weight and dimensions
- carrier, vehicle, LR and tracking
- immutable delivery handoff evidence
- mobile-ready versioned Warehouse API contract

Test large Pick Lists, multiple scanners, workflow settings, wrong locations and concurrent
submissions. Stop before Session 10 return/refurbishment work.
```

---

## Session 10 — Warehouse returns and refurbishment

```text
SESSION 10: WAREHOUSE RETURNS, QUARANTINE AND REFURBISHMENT

Complete the second half of Warehouse production closure:

- printable labels and manifests
- deterministic permission-aware PDF
- optional reviewed ZPL
- reprint audit
- returns against original delivery
- duplicate/excess-return prevention
- quarantine
- Quality handoff
- refurbishment operations and assignment
- consumed material/cost references without duplicating accounting
- before/after evidence
- post-refurbishment inspection hook
- native restocking
- return/quarantine/refurbishment SLA queues
- reason codes and exception dashboards

Do not guess refund, replacement, credit-note or scrap policy. Keep physical receipt and
financial authorization separate until business rules are approved.

Test printer failure, network interruption, serial/batch identity, two-device races and
large return volumes.
```

---

## Session 11 — Quality cycle schema

```text
SESSION 11: PRODUCTION QUALITY CYCLE AND NATIVE LINKS

Implement a real Production Quality Cycle after confirming its unique business key.

Add reviewed links to:

- Supplier
- Purchase Order
- relevant Items/styles/colourways
- production lot/season where approved
- applicable Purchase Receipt
- native ERPNext Quality Inspection

Do not duplicate purchasing, payable, stock or Quality Inspection ledgers.

Implement safe migration from existing Supplier Quality Inspection records. Add uniqueness,
company/supplier isolation, permissions, migration-twice and rollback tests.

Stop before checklist/report implementation.
```

---

## Session 12 — Quality reports and evidence

```text
SESSION 12: QUALITY STAGE REPORTS, CHECKLISTS AND EVIDENCE

Implement:

- explicit cycle/stage/report relationships
- seven ordered stages
- multiple Inline and Mid-line visits
- versioned checklist templates by product/category
- historical checklist retention
- measurements and readings
- sampling plans and counts
- defects and severity
- recommendation and result
- corrective action, owner and due date
- multiple private captioned photos
- immutable revision/supersession history
- side-by-side revision comparison

Add authorization, privacy, concurrency, upload retry and migration tests.
Stop before critical gate UI/approval work.
```

---

## Session 13 — Quality approval gates

```text
SESSION 13: QUALITY GATES, CORRECTIONS, DISPOSITIONS AND REPORT BUNDLES

Implement:

- Production Go Ahead review screen
- Final Inspection review screen
- exact reviewed-revision locking
- correction requests and resubmission
- conditional approval/rejection policy only where approved
- immutable decisions
- complete seven-stage history
- controlled PDF report bundle
- permission checks, watermark and export audit
- failed-return dispositions after business approval
- supplier claims
- post-refurbishment reinspection
- significantly expanded Quality test coverage

Define what native business event a gate authorizes. A custom status must not silently
submit stock, purchasing, payable or accounting transactions.
```

---

## Session 14 — Barcode and label platform

```text
SESSION 14: BARCODE GENERATION, SCANNING, LABELS AND PRINTING

First write `docs/barcodes.md`.

Define separate namespaces for:

- licensed GS1 GTIN/EAN/UPC
- ERPNext Item Barcode
- internal Code 128 SKU
- Serial No
- Batch No
- Warehouse location
- package
- Pick List
- Delivery Note
- return/quarantine
- Quality cycle/report

Never generate random EAN-13 numbers and claim they are globally valid.

Implement:

- collision-safe server allocation
- applicable check-digit validation
- immutable assignment
- manufacturer barcode support
- ERPNext barcode reuse
- preview
- single and bounded bulk generation
- deterministic PDF labels
- optional reviewed ZPL
- reprint audit
- permission-aware downloads
- one typed server-side scan resolver
- camera and keyboard-wedge scanning
- debounce and duplicate suppression
- continuous scanning
- torch/sound/haptic/color feedback
- accessible manual fallback

Test forged/ambiguous identifiers, replay, rapid double scans, two devices, wrong size,
wrong Item, wrong Batch, wrong Serial, expiry, over-pick and over-return.

A barcode identifies an object; it never authorizes an operation and must not contain
credentials, private URLs, customer data or approval authority.
```

---

## Session 15 — Mobile foundation

```text
SESSION 15: SHARED MOBILE FOUNDATION

Write an ADR comparing Flutter, Capacitor/PWA and native development. Flutter is preferred
but must be justified.

Establish:

- `mobile/` workspace
- shared core packages
- three application targets
- separate bundle/application identifiers
- versioned API client
- stable errors and pagination
- minimum supported version
- secure authentication
- OAuth2 Authorization Code with PKCE if safely supported by the pinned Frappe release
- Keychain/Keystore-backed storage
- token rotation and revocation
- encrypted local database
- encrypted offline operation queue
- UUID idempotency and conflict model
- logout/revocation wipe
- TLS hostname validation
- scanner abstraction
- safe photo upload
- accessibility and localization
- Android/iOS CI skeletons
- protected signing design
- mobile SBOM and dependency scanning

No password, Administrator credential or long-lived API secret may be stored in the app.
Do not add a trust-all-certificate mode.
```

---

## Session 16 — Sales Mobile

```text
SESSION 16: CLOTHING SALES MOBILE

Build the Sales application using the shared mobile foundation.

Implement and test:

- ASM/RSM-specific home
- Territory-scoped retailers
- retailer application and private evidence
- RSM review and request-more-information
- visits and obligations
- footfall, financial and dealer review
- SIS stock review
- offline catalogue subset with stale indicators
- product photographs and size matrix
- cart and idempotent draft order
- server repricing and exposure validation
- order approval/status
- collection worklist
- delivery follow-up
- RSM supervision
- barcode lookup
- offline conflicts
- revoked-role/account handling

Cached prices, permissions and stock are never authoritative. Server revalidation is
required before every business mutation.
```

---

## Session 17 — Warehouse Mobile

```text
SESSION 17: CLOTHING WAREHOUSE MOBILE

Implement and test:

- assigned Warehouse work queues
- camera scanning
- hardware keyboard-wedge scanning
- pick and undo
- Serial/Batch detail
- shortages and partial fulfilment
- packing and package dimensions
- labels and manifests
- carrier handoff
- bounded bulk results
- returns
- quarantine transfer
- refurbishment
- safe printer integration
- network interruption recovery
- multi-device concurrency
- role/permission revocation while app is open

Offline scans may be queued only where approved by policy. Native submission and stock
transitions must remain blocked until online server reconciliation succeeds.
```

---

## Session 18 — Quality Mobile

```text
SESSION 18: CLOTHING QUALITY MOBILE

Implement and test:

- Production-cycle queue
- stage-due queue
- return inspections
- versioned checklists
- measurements and sampling
- defects and severity
- corrective actions
- multiple captioned private photographs
- checksum-verified resumable uploads
- multiple Inline/Mid-line reports
- revision comparison
- correction/resubmission
- quarantine decisions
- post-refurbishment inspection
- gate review
- controlled report viewing
- offline protection and secure wipe

High-risk Administrator approval requires an exact immutable review bundle, online
connectivity and strong reauthentication. Do not expose permanent private File URLs.
```

---

## Session 19 — Production certification

```text
SESSION 19: COMPLETE PRODUCTION CERTIFICATION

Do not add unrelated features.

Run and record:

- all unit tests
- all real-site tests
- clean fresh installation
- double migration
- API contract tests
- browser E2E for every role
- Android/iOS E2E on real supported devices
- hardware scanner tests
- printer tests
- SAST, SCA, secret and license scans
- authorization and IDOR/BOLA tests
- CSRF, XSS and SQL-injection tests
- upload/polyglot/decompression-abuse tests
- SSRF and path/archive-traversal tests
- token replay and revocation tests
- rate-limit tests
- concurrency/fuzz/property tests
- load and soak tests
- migration from v0.3.0 and representative intermediate states
- update and rollback failure injection
- encrypted backup and isolated restore
- power loss, disk full and service-restart drills
- real Proxmox install/update/reboot/restore/rollback
- user acceptance using synthetic data

Produce a certification evidence report. Do not mark certification complete when any
mandatory test was skipped.
```

---

## Session 20 — Stable release

```text
SESSION 20: FINAL REMEDIATION AND STABLE RELEASE

Review the Session 19 evidence.

Before release:

- remediate every critical/high finding
- document and approve lower residual risks
- re-run affected tests
- run the complete gate from the exact release artifact
- verify publisher provenance
- verify SBOMs and dependency locks
- verify server release signatures
- verify Android/iOS signatures
- verify fresh install, update and rollback
- verify documentation exactly matches behavior
- verify support, security contact and incident runbooks
- verify no credentials or real data are present

Publish only if every mandatory production gate passes.

Update `work.md` with final evidence, release identifier, commit hashes, artifacts and known
supported configurations.
```

---

## Continuation prompt — use when a session stops midway

```text
Continue the current Antigravity session in:

/home/avi/GitHub/erp/clothing_erp

Read `AGENTS.md`, the production programme at the top of `work.md`, the current session
record, Git status and recent commits.

Do not advance to the next numbered session. Complete the current session's unchecked
tasks, tests, documentation and coherent `[antigravity]` commit.

Preserve all user changes and do not modify upstream Frappe, ERPNext, Insights or India
Compliance.

End by updating `work.md`, reporting exact tests, remaining risks, commit hash, Git status
and the recommended next session.
```

---

## Session completion note template

Antigravity should append a concise record like this to `work.md` after every session:

```markdown
### Antigravity Session N — <title> — YYYY-MM-DD

Status: Complete / Partial / Blocked by business decision

Implemented:

- ...

Security findings resolved:

- ...

Files changed:

- `path/to/file`

Verification:

- `exact command` — PASS, N tests
- `exact command` — FAIL, reason

Remaining risks/decisions:

- ...

Commit:

- `<hash> [antigravity] subject`

Next recommended session:

- Session N+1 — ...
```
