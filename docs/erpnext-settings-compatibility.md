# ERPNext settings compatibility

Clothing ERP provides simplified operational screens, but ERPNext remains the business
system of record. Every custom operation must identify the ERPNext settings and native
controllers that apply before implementation.

## Rules

1. Never write directly to ERPNext ledger tables or reproduce a native commercial ledger.
2. Create and update standard business records through their Frappe documents so native
   validation, hooks, naming, defaults and permissions execute.
3. Never accept client-provided prices, commission, stock availability or permission claims.
4. When a custom screen displays a native value, apply relevant User Permissions and
   company, warehouse, currency, UOM and effective-date context.
5. If an ERPNext setting is not relevant to an operation, document that boundary instead
   of inventing a Clothing ERP equivalent.

## Current compatibility matrix

| Clothing ERP operation | ERPNext authority and settings | Handling |
|---|---|---|
| Generic catalogue pricing | Selling Settings default price list; Price List enabled/selling/currency; Item Price UOM, validity and party scope | Applied server-side. Party-specific rows are excluded until a retailer is selected. |
| Assigned-retailer catalogue pricing | Customer defaults, customer Price List, Pricing Rules, exchange-rate policy, currency and UOM conversion | Calls ERPNext's native item-pricing controller with a Sales Order context; no commercial document is written. |
| Catalogue draft ordering | Native Sales Order party/default, item pricing, taxes, maximum-discount and Sales Team/commission controllers | The browser sends only Customer, Item codes, quantities, delivery date and an idempotency token. The server revalidates access and Size-only variants, then inserts a standard draft through the native controller. Browser rates, discounts, stock and commission are ignored. |
| Catalogue stock display | Bin actual quantity; Warehouse User Permissions | Only aggregate quantities are returned. Configured warehouse assignments restrict the aggregation; warehouse names are not exposed. |
| Clothing catalogue metadata | Native Item templates plus app-owned Custom Fields | Style code, collection, fabric, fit and season are descriptive/reporting metadata on each colour-specific Item template. They do not create variants or replace Item Group, Brand or Size attributes. Filter values use permission-aware Item queries. |
| Product galleries | File upload size/type/privacy policy and site file storage | Uploads use native File records. Cleanup invokes native File deletion and protects referenced, shared, private-policy and packaged assets. |
| Retailer intake and approval | Customer naming/default validation, Selling Settings Customer Group/Territory, Contact, Address and User Permission | Salesperson intake forces the session user and uses configured selling defaults, falling back to app-owned leaf masters without changing Selling Settings. Approval inserts all records through native controllers and revalidates the assigned salesperson. |
| Retailer reassignment | Customer and Territory User Permissions | The Clothing ERP page replaces the existing Customer permission atomically under a row lock. Sales managers are restricted by native Territory permissions; system/business administrators have global scope. The app stores only an immutable audit event, not a competing live assignment field. |
| Retailer visits and reporting | Customer User Permissions and app role scope | A salesperson can record a visit only for an assigned native Customer. The Desk report uses permission-aware `get_list` queries and the same Retailer Visit permission conditions. |
| Dashboard and directories | Native document permissions, User Permissions, currencies and submitted document state | Queries use permission-aware lists and keep currency totals separated. |

## Pending ASM/RSM compatibility decisions

Requirements captured on 2026-11-16 replace the generic salesperson/manager target with
ASM/RSM-only sales access. The detailed source is
[`field-sales-operating-model.md`](field-sales-operating-model.md). The native-first mapping
to validate before implementation is:

| Requirement | Preferred native authority | Clothing ERP responsibility still needed |
|---|---|---|
| Four retailer operating types | ERPNext Customer Group leaf records | Stable semantic mapping, cadence settings, authorized/audited type changes if native labels are editable |
| ASM retailer visibility | Territory plus User Permission | ASM role boundary and complete Territory-scoped endpoints |
| RSM supervises ASMs | Evaluate native Sales Person hierarchy without replacing User Permission security | Explicit User relationship, capacity warnings, review and approval scope |
| Monthly/quarterly/80-day visits | Customer, Territory and native assignment where sufficient | Idempotent obligation scheduler, completion evidence, review states and escalation |
| ASM order and RSM approval | Standard Sales Order and ERPNext Workflow/controller | Restricted Clothing ERP submission/review UI and hierarchy checks |
| Money collection | Sales Invoice, Payment Terms, Payment Entry and Accounts Receivable | Scoped collection worklist, visit linkage, reminders and escalation only |
| Accounting credit limit | Customer/Customer Group Credit Limit and native Sales Order checks | RSM sets the initial limit during retailer approval; later RSM change proposals require administrator approval and audit; no direct bypass |
| Stock held at shop plus incoming stock | Native Warehouse, stock ledger and standard stock/delivery documents once ownership is defined | Derived exposure calculation and order block; valuation and ownership are unresolved |

The final row must not be implemented using receivables outstanding alone. Native Customer
credit and physical store-stock exposure represent different facts unless the remaining
business rules explicitly unify them.

## Pending warehouse and supplier-quality compatibility decisions

Requirements captured on 2026-11-16 replace the operator/manager warehouse target with
manager-only Warehouse operations and add return/refurbishment plus seven supplier-quality
stages. The detailed source is
[`warehouse-quality-operating-model.md`](warehouse-quality-operating-model.md).

| Requirement | Preferred native authority | Clothing ERP responsibility still needed |
|---|---|---|
| Manager Warehouse scope | Warehouse and User Permission | Manager-only role boundary, queues and cross-Warehouse denial |
| Order scanning | Pick List, Item Barcode, Serial/Batch Bundle | Scan-first interface, idempotency, locking, batch/wave convenience |
| Packing and dispatch | Pick List, Delivery Note and native package/transport fields where applicable | Packing workflow and recorded delivery handoff without fake stock status |
| Billing preparation | Sales Invoice, taxes, pricing, credit and accounting permissions | Restricted preparation UI only after authority is confirmed; no commercial overrides |
| ASM delivery follow-up | Customer, Sales Order/Delivery Note and ASM Territory scope | Due obligation, contact outcome, issue/escalation audit |
| Customer return | Return Delivery Note/Sales Invoice and native stock/accounting controllers | Scan intake, quarantine workflow, duplicate/excess-return prevention |
| Return quality | Quality Inspection and private File attachments where applicable | Return-specific checklist, decision, evidence and workflow linkage |
| Refurbishment | Stock Entry and dedicated native Warehouse locations | Work queue, audit and gate before movement back to saleable stock |
| Supplier production cycle | Supplier, Purchase Order, Item, Purchase Receipt and Quality Inspection | Seven-stage reports, revisions, photos and administrator approval bundles |

A custom completion or approval state must never directly alter stock, receivables,
payables or general ledger values. Only the applicable submitted native document may make
that posting.

## Required checks for upcoming stages

Draft ordering now calls the native pricing and Sales Order controllers. Before native
submission is enabled, pinned-release integration coverage must additionally prove:

- customer/default price lists, Pricing Rules, currencies, UOMs and taxes during a real insert;
- item maximum discounts and any future permitted operational discount policy;
- customer credit limits and configured credit controller behavior;
- stock availability, negative-stock and stock-reservation configuration;
- native Sales Person/Sales Team commission rate, contribution and incentives;
- Sales Order naming, approval/workflow, cancellation and duplicate-request protection.

Warehouse fulfilment must use native Pick List and Delivery Note behavior, including
warehouse permissions, serial/batch bundles, stock reservation, negative-stock rules,
partial delivery and cancellation. A custom display status must never create a stock
movement.

This matrix is reviewed whenever a new ERPNext version is added to the release manifest.

The existing developer bench intentionally runs ERPNext `develop` with Frappe v16 and is
not a production compatibility target. Its patch log had recorded ERPNext's v16 Contact
field migration although ERPNext's own field was absent. Clothing ERP now invokes the
upstream idempotent installer when those upstream-owned columns are missing; it does not
copy their definitions or alter upstream source. Local native draft insertion and replay
pass. Release CI must still validate full creation and submission on the exact pinned pair
before Stage 5 can be marked complete.
