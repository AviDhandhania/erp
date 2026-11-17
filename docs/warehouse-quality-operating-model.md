# Warehouse and quality operating model

Status: requirements captured on 2026-11-16; implementation is intentionally deferred
until the remaining business details are supplied. This is the hand-off source for
warehouse fulfilment, returns/refurbishment and supplier-production quality workflows.
It distinguishes confirmed requirements, recommended quality-of-life improvements,
native ERPNext ownership and questions that must not be answered by assumption.

## Confirmed warehouse access model

Warehouse operations will be performed only by the **manager of each warehouse**.
The target model does not include a common warehouse operator role. Each manager must be
restricted to the manager's assigned Warehouse or Warehouses, and administrators retain
global oversight.

The existing `Clothing Warehouse Operator` and `Clothing Warehouse Manager` roles are
legacy implementation roles. The current code allows operators to work assigned Pick
Lists using Warehouse User Permission plus an open ToDo. The target requires a controlled
migration to manager-only access; merely hiding the operator link is not sufficient.

Preferred authorization foundation:

- native Frappe User Permission for each allowed ERPNext Warehouse;
- server-side rejection of mixed or unauthorized Warehouse documents;
- manager visibility over all relevant work in an assigned Warehouse, subject to the
  final decision on whether individual ToDo assignment is still required; and
- Administrator/System/Clothing Business Administrator oversight without weakening
  document permission checks.

## Normal order fulfilment

The confirmed operating sequence is:

1. An approved order reaches the responsible warehouse.
2. The warehouse manager scans the ordered items.
3. The warehouse manager sets up billing.
4. The warehouse manager hands the order to delivery.
5. The ASM follows up on delivery by contacting the retailer.

The native-first document flow should be:

`Sales Order -> Pick List/scanning -> packing -> Delivery Note -> billing document -> delivery handoff`

ERPNext Sales Order, Pick List, Delivery Note, Sales Invoice, Payment Terms, taxes,
serial/batch bundles, stock reservation and stock ledger remain authoritative. “Set up
billing” is not yet precise enough to grant accounting submission rights: the next design
must confirm whether the warehouse manager prepares a draft Sales Invoice, supplies only
packing/transport information, or may submit a billing document. Clothing ERP must not
let a warehouse manager alter protected prices, taxes, discounts, credit decisions or
accounting values outside native permissions and approval.

### Scanning and picking

The existing row-locked SKU, item-barcode, Batch No and Serial No verification is a valid
foundation. The target must additionally cover prebuilt Serial and Batch Bundles,
packing, partial fulfilment and standard Delivery Note creation. Every bulk or single
scan must recheck the document, Warehouse permission, remaining quantity, tracking data
and concurrent changes on the server.

### Delivery handoff

“Give order to delivery” needs a recorded handoff rather than a UI-only status. The final
design should link the native Delivery Note and packages to a delivery handoff/manifest,
record who accepted it and when, and retain carrier/vehicle/tracking/proof fields required
by later details. India Compliance e-Waybill behavior must remain attached to supported
native delivery/invoice documents.

### ASM delivery follow-up

After handoff or the agreed delivery event, the responsible ASM must receive a follow-up
obligation and contact the retailer. The completed follow-up should record confirmation,
date/time, contact person, outcome, shortage/damage/refusal issues and notes. The exact
trigger (handoff, dispatch or delivered), due interval, escalation and proof requirements
remain unconfirmed. It must use the ASM/RSM Territory and supervision model described in
[`field-sales-operating-model.md`](field-sales-operating-model.md).

## Product return, quality and refurbishment

The confirmed return sequence is:

1. Scan the returned item.
2. Quality department performs a quality check.
3. Only after quality passes, send the product to refining/refurbishment.
4. Refurbish the product.
5. Put it back into saleable stock.

### Native stock/accounting boundary

The scan must identify the original retailer and commercial reference where applicable,
the exact Item/size, quantity, serial/batch identity and receiving Warehouse. A standard
ERPNext return against Delivery Note/Sales Invoice should be used where this is a customer
sales return. The financial result—credit note, replacement, refund or no credit—remains
unconfirmed and must not be inferred from the physical return alone.

Returned stock must not immediately become saleable. The proposed physical flow uses
separate native Warehouses or Warehouse locations:

`Returns quarantine -> Quality passed -> Refining/refurbishment WIP -> Saleable stock`

Every movement must be a submitted native return/Stock Entry or another applicable ERPNext
stock document. Clothing ERP may orchestrate and approve these documents but must not
write Bin or Stock Ledger Entry directly or create a parallel inventory balance.

### Return scan controls

The target should validate:

- original Delivery Note/Sales Invoice or other authorized return source;
- retailer and company;
- Item, colour-specific SKU and Size variant;
- returned quantity versus delivered and previously returned quantity;
- Serial No uniqueness/status and Batch No where enabled;
- source and quarantine Warehouse permissions;
- return reason, condition on arrival and photographs where required; and
- idempotency so a repeated scan/request cannot receive the same unit twice.

### Return quality report

The quality department must create a report linked to the return. It should capture a
configured checklist, defects, measurements where applicable, condition/grade, decision,
inspector, inspection time, notes and appropriate photographs with captions. Native
ERPNext Quality Inspection should be reused where its reference and readings fit; an
app-owned return/refurbishment workflow may link it to the return and stock movements.

Quality failure disposition is not yet specified. The implementation must not assume that
failed goods are scrapped. Possible outcomes requiring confirmation include reject/return
to retailer, supplier claim, repair/rework, seconds stock, scrap or administrator review.

### Refining/refurbishment

A passed item moves to a refining/refurbishment queue. Work must record assignee,
operations performed, consumed material/cost if required, start/completion times, notes
and photos. Only completed refurbishment may move to saleable stock. A final post-refurbish
verification is recommended but is not yet a confirmed mandatory stage.

## Supplier-production quality cycle

When buying stock from a company/supplier, quality follows these seven ordered stages:

1. **First submission — fit sample**
2. **Second submission — refit sample**
3. **Size set submission**
4. **Production go ahead**
5. **Inline visits**
6. **Mid-line visits**
7. **Final inspection**

Quality staff must make a report for every quality check and attach appropriate photos.
These pre-production, visit and final-inspection records need an app-owned **Production
Quality Cycle** (final name may change) linked to native ERPNext Supplier, Purchase Order,
Items/styles/colourways and, where applicable, Purchase Receipt and Quality Inspection.
It must not duplicate purchasing, payable or stock ledgers.

The exact cycle granularity is not yet confirmed: one cycle may correspond to a Purchase
Order, supplier/style/season, colourway, production lot or another unit. This must be
decided before DocType keys and uniqueness rules are created.

### Stage reports

Each report is captured in `Supplier Quality Inspection` linked directly to its parent `Production Quality Cycle`:

- **Cycle and Native Links**: cycle key, Supplier, Purchase Order, Item/style/colourway, production lot, and season.
- **Stage & Visit Sequence**: stage (1-7), visit number (supporting multiple visits for Inline and Mid-line visits), visit type, and factory location details.
- **Versioned Checklists**: linked to versioned `Quality Checklist Template` (by item group / category); check points are frozen into child table `Quality Inspection Checklist Item` ensuring historical checklist retention across template updates.
- **Measurements & Readings**: child table `Quality Inspection Reading Item` capturing spec target, tolerances (+/-), actual reading, server-calculated variance, and In Spec / Out of Spec classification.
- **Sampling Plans & Defect Severity**: AQL 1.5/2.5/4.0 plans, lot size, sample size, passed/failed quantities, and child table `Quality Inspection Defect Item` tracking defect code, description, count, and severity (Minor, Major, Critical).
- **Recommendation & Result**: result (`Passed`, `Failed`, `Conditionally Passed`, `Pending Review`) and recommendation (`Accept Lot`, `Reject Lot`, `100% Re-inspection Required`, `Correction & Resubmission Required`, `Production Go Ahead Recommended`, `Rework & Reinspect`).
- **Corrective Actions**: corrective action required, action description, action owner (`User`), party name, due date, status (`Open`, `In Progress`, `Resolved`, `Overdue`, `Waived`), resolution notes, and auto-recorded resolution timestamp.
- **Multi-Photo Private Evidence**: child table `Quality Inspection Evidence` capturing private files, captions, display order, evidence types, uploader, timestamp, and revision tags.
- **Immutable Revisions & Side-by-Side Comparison**: revising a report creates an incremented revision under `SELECT ... FOR UPDATE` row locking; sets `supersedes` and updates original to `superseded_by` and `is_latest = 0`; approved reports cannot be revised; `compare_inspection_revisions` provides comprehensive side-by-side revision comparison diffs.

Photos use native private File records by default, are included in site backups and
follow reference-safe deletion. File type, size, privacy, malware handling and retention
must follow configured Frappe policy. A rejected or superseded report's evidence must not
be silently deleted.

### Production Go Ahead approval gate

At the Production Go Ahead stage, the administrator must review the reports together and
give approval. At minimum, the review bundle must show the First Submission, Second
Submission and Size Set reports, their photographs, open corrections and the Production
Go Ahead recommendation. Production must not advance through the Clothing ERP workflow
until the administrator approves the gate.

The decision must record approver, date/time, decision, conditions/reason and the exact
report revisions reviewed. Rejection or return-for-correction must not overwrite previous
evidence.

### Final Inspection approval gate

At Final Inspection, the administrator must again review all reports together and approve
or reject the final gate. The review bundle should include the full history from fit sample
through Inline and Mid-line visits to Final Inspection, all photos, corrections and both
gate decisions. Final approval must reference exact report revisions.

Whether final approval authorizes Purchase Receipt, shipment from supplier, billing or
another event is not yet confirmed. No stock or payable transaction should be submitted
merely because a custom quality status changed.

“Inline visits” and “mid-line visits” are plural in the requirement. The design must
confirm whether each stage permits multiple reports/visits and what minimum count or
completion rule applies.

## Recommended warehouse quality-of-life features

These are recommendations requested for operational usability, not additional confirmed
business policy. Each must preserve native permissions and controllers.

### Fulfilment productivity

- Wave/batch work queues grouped by Warehouse, promised date, route/carrier and priority.
- Bounded bulk selection to prepare Pick Lists, packing slips, labels or handoff manifests.
- Scan-first mobile layout with permanent barcode focus, large quantities and clear sound/
  color feedback.
- Undo the last unsubmitted scan with an audit event; never undo submitted stock movement.
- Duplicate, wrong-item, over-pick, wrong-batch and wrong-serial feedback at scan time.
- Saved filters and exception queues for shortage, mismatch, partial and overdue orders.
- Bulk printing for Pick Lists, packing slips, labels and Delivery Notes.
- Package count, weight and dimensions with barcode/label support.
- Preflight validation before bulk transitions, followed by atomic processing where safe or
  explicit per-document success/failure results; never silently skip failed documents.
- Idempotency tokens and row locking for every scan, bulk action and handoff.

### Returns/refurbishment productivity

- Scan return against original delivery and automatically show remaining returnable quantity.
- Dedicated quarantine, awaiting-quality, refurbishment and ready-to-restock queues.
- Configurable defect/return reason codes plus free-text notes.
- Batch assignment of an inspector/refurbisher without bulk-approving quality decisions.
- Side-by-side intake, inspection and post-refurbishment photos.
- Ageing/SLA indicators and escalation for returns waiting at each stage.
- Printable return labels and internal movement labels.
- Dashboard counts by Warehouse, age, defect, disposition and blocked reason.

### Supplier-quality productivity

- Configurable stage checklist templates by product/category without changing historical
  reports when a template is edited.
- Clone applicable measurements from the previous submission while requiring a new result.
- Side-by-side comparison of fit, refit and size-set revisions and photographs.
- Due reminders, correction reminders and stage-ageing dashboard.
- One administrator review screen containing the entire approval bundle.
- Generated report bundle/PDF for controlled sharing, with access and revision markers.
- Search and filters by Supplier, Purchase Order, style, season, stage, result and due date.
- Explicit missing-report/photo/correction indicators before either approval gate.

## Workflow states to design

The next implementation plan must define server-enforced states for:

- fulfilment: ready to pick, picking, picked, packed, billing prepared, ready for handoff,
  handed to delivery, delivery follow-up due, retailer confirmed, issue/escalated;
- return: expected/initiated, received in quarantine, awaiting quality, quality passed,
  quality failed/on hold, awaiting refurbishment, refurbishing, refurbished, ready to
  restock, restocked and alternate final dispositions;
- supplier quality cycle: draft, stage report due, report submitted, correction requested,
  resubmitted, awaiting Production Go Ahead, go-ahead approved/rejected, production in
  progress, awaiting Final Inspection, final approved/rejected and closed/cancelled; and
- individual reports and approval decisions, including revision/supersession rules.

Transitions must be server-authorized, concurrency-safe and audited. A custom state must
never itself impersonate a native stock or accounting posting.

## Requirements still expected

The following details are intentionally open rather than guessed:

- whether a warehouse manager is assigned exactly one Warehouse or may manage several;
- whether individual ToDo assignment is still needed when only managers operate;
- what “set up billing” permits and who submits Sales Invoice/accounting documents;
- packing rules, package identity, carrier/delivery staff and handoff evidence;
- ASM delivery-follow-up trigger, due interval, fields and escalation;
- customer return financial policy: replacement, credit note, refund and authorization;
- failed-return quality dispositions and approval authority;
- whether post-refurbishment quality verification is mandatory;
- return/refurbishment valuation and cost accounting;
- Production Quality Cycle granularity and relationship to Purchase Orders/lots/styles;
- exact checklists, measurements, sampling plans and required photos for all seven stages;
- number/timing of Inline and Mid-line visits;
- who may author and submit quality reports and whether quality has manager/inspector roles;
- correction, rejection, conditional approval and exceptional override policy;
- event authorized by Production Go Ahead and Final Inspection approval;
- notification channels, SLA targets and escalation recipients; and
- migration/removal behavior for existing warehouse operators and open assignments.

## Non-negotiable implementation boundaries

- Do not modify ERPNext, Frappe, India Compliance or Insights source.
- Keep native commercial, stock, purchasing, accounting and quality documents authoritative.
- Never write Bin, Stock Ledger Entry, GL Entry or receivables directly.
- Keep returned goods unavailable in a quarantine location until authorized native movement.
- Enforce Warehouse scope and workflow transitions on the server, not only in the UI.
- Store photos through native File records with permission and reference-safe lifecycle.
- Make scheduled work, bulk actions and scan requests idempotent and concurrency-safe.
- Test cross-Warehouse access, bulk partial failures, duplicate scans, returns exceeding
  delivered quantity, serial/batch identity and both administrator approval gates.

