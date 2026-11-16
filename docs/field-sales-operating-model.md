# Field sales operating model

Status: requirements captured on 2026-11-16. The role, retailer-type, Territory assignment
and retailer-intake foundations are implemented; cadence, credit/exposure, visit review and
order approval stages remain pending the business details below. This document distinguishes
implemented foundations, confirmed requirements and questions that must not be guessed.

## Confirmed retailer classifications

Every retailer belongs to exactly one of these four operating types:

1. **Buy & Sell**
2. **Buy & Sell — Stock Correction**
3. **SIS (Shop-in-Shop)**
4. **EBOC (Exclusive Brand Outlet)**

The spelling `EBOC` is retained from the supplied requirement. Confirm whether this is
the permanent business term or whether it should be `EBO` before schema identifiers,
reports or migrations are finalized.

An administrator must have one clear place to maintain the groups and applicable global
defaults. The preferred native-first design is an ERPNext **Customer Group** parent with
four non-group children, because Customer already requires one leaf Customer Group and
administrators can maintain the tree in ERPNext. Clothing ERP should add a settings
DocType only for behavior that Customer Group cannot express, such as cadence, reminders,
escalation recipients or a stable mapping when a display label is renamed. No parallel
Customer master or accounting ledger should be introduced.

The operating type must be selected during retailer onboarding, carried to the approved
ERPNext Customer, exposed to authorized directories/reports and used by the scheduler.
Changing it later must be authorized and audited because it changes visit and order rules.

## Confirmed sales hierarchy and access

The Clothing ERP sales area is restricted to:

- **ASM — Area Sales Manager**
- **RSM — Regional Sales Manager**
- Administrator and explicitly authorized business/system administrators

A common salesperson is not granted Clothing ERP sales access. Canonical roles are now
`Clothing Area Sales Manager` and `Clothing Regional Sales Manager`; legacy role names are
migrated by the app rather than being treated as continuing authorization.

Confirmed hierarchy:

- An ASM is allotted a Territory and can see every authorized retailer inside it.
- An RSM is superior to the ASM.
- An RSM normally supervises about 3–4 ASMs.
- An RSM normally covers about 200–250 shops.
- Administrators have global oversight.

The implemented authority is one effective-dated app-owned Sales Territory Assignment:
one leaf Territory → one ASM → one supervising RSM. It automatically maintains native
Frappe Territory User Permissions so standard ERPNext document queries enforce the same
scope. An ASM sees all retailers in the assigned Territory; an RSM sees the union of the
Territories assigned to their ASMs. Per-retailer salesperson assignment is retired.
Counts such as 3–4 ASMs and 200–250 shops remain planning expectations; whether they are
hard limits or warnings is unconfirmed.

## ASM responsibilities

### All assigned retailers

The ASM can see every retailer in the allotted Territory and can create retailer
applications for prospective shops. An ASM-created application is routed to that ASM's
RSM, not to an arbitrary manager or a global unscoped queue.

After a warehouse hands an order to delivery, the responsible ASM must follow up by
contacting the retailer and record the delivery outcome or issue. Trigger timing and
escalation are defined as open requirements in
[`warehouse-quality-operating-model.md`](warehouse-quality-operating-model.md).

### SIS retailers

For every SIS retailer, the ASM must:

- complete a stock review once every quarter;
- receive the quarterly stock-review assignment automatically;
- complete a separate general visit every month, without a mandatory specialist agenda;
- perform the basic visit activities and submit a report; and
- take seasonal orders for the retailer.

A planned assignment and a completed visit are different records. Scheduling should not
pre-create a completed `Retailer Visit`. The likely design is a due visit/task record (or
a suitable native assignment) that is fulfilled by an immutable visit report. The exact
quarter definition and seasonal calendar are not yet confirmed.

### Buy & Sell retailers

For every Buy & Sell retailer, the ASM must:

- visit monthly;
- show samples;
- take the new monthly order; and
- collect money according to the outstanding report, within the stated 90–120 day period
  measured from Delivery Date.

ERPNext Payment Terms, Sales Invoice due dates, Payment Entries and Accounts Receivable /
outstanding reports must remain authoritative for money owed and money collected. Clothing
ERP may provide a scoped collection worklist, reminders and visit evidence, but must not
create a duplicate receivables ledger. It is not yet confirmed whether 90 days is the
first reminder, the normal due date or the beginning of a collection window, nor what
must happen at 120 days.

### Retailer application intake

The ASM can create a retailer application. The RSM must then contact the prospective
retailer, request any missing details, complete the additional RSM-owned fields and decide
approval or rejection. Approval includes setting the initial retailer credit/exposure
limit. Application creator, reviewer, timestamps, requested changes, supplied details,
decision and reason must be auditable.

## RSM responsibilities

### Retailer coverage

The RSM must personally visit every shop in the RSM's scope at least once within 80 days.
As the deadline approaches, the RSM receives notice for that shop. A five-day grace period
follows the 80-day target. If no qualifying RSM visit exists after day 85, the administrator
must receive a notice identifying the overdue RSM and shop.

The eventual scheduler must be idempotent, timezone-aware and safe across retries. It must
not emit duplicate tasks or notifications for the same retailer/cycle. A successful visit
must close the corresponding obligation and establish the next due cycle. The exact
advance-warning day or days are not yet specified.

### RSM visit report

Each RSM visit must capture at least:

- dealer review/opinion;
- assessment of the shop's financial situation;
- number of customer walk-ins, recorded as an agreed customer footfall measure;
- review of the retailer's credit/exposure limit on every visit; and
- the RSM's recommendation, evidence and notes.

The administrator reviews RSM visit reports. After the initial limit is set during RSM
approval of a new retailer, a later recommendation to change that retailer's
credit/exposure limit does not change the live limit until an administrator approves it.
The proposal, old value, proposed value, reason, proposer, approver, decision and effective
time must be immutable audit data.

### ASM supervision

The RSM must:

- review the reports produced from ASM visits;
- approve or return/reject orders created by ASMs;
- approve or reject retailer applications created by supervised ASMs;
- ask for and complete further retailer details after contact; and
- set the initial credit/exposure limit while approving a new retailer.

Order approval must be a real server-side workflow over the standard ERPNext Sales Order.
UI visibility alone is not authorization. Active ERPNext Workflow, pricing, tax,
commission, stock reservation and credit checks must never be bypassed.

## Credit and shop-stock exposure

The confirmed business rule is that a shop may hold only a limited value of stock. When an
ASM prepares a new order, the following combined exposure must not exceed the approved
limit:

`value of stock already present at the shop + value of new incoming stock`

The RSM reviews this limit at every RSM visit; administrators approve changes.

This is not automatically equivalent to ERPNext's native Customer credit limit. Native
credit control is primarily based on accounting exposure/outstanding and can include
submitted Sales Orders according to ERPNext settings. It does not, by itself, prove the
quantity and value of stock physically held at a retailer. Before implementation, the
business must define:

- who owns SIS/EBOC/shop stock before consumer sale;
- which native stock document and Warehouse represents stock at each shop;
- how stock already sold, returned, damaged or corrected is reconciled;
- whether exposure is valued at selling price, transfer price, landed cost or another rate;
- whether tax, discounts and pending deliveries are included;
- whether each retailer has one company-specific limit or multiple company limits; and
- whether the accounting credit limit and physical stock-exposure limit are separate
  controls or one approved value used by both checks.

Until those points are confirmed, Clothing ERP must not claim that the native Customer
credit-limit table alone implements this rule. The final design should reuse native
Customer Credit Limit for genuine accounting credit and native Warehouses/stock ledgers
for physical stock, adding only an audited approval layer and derived exposure check where
necessary.

## Workflow states that must be designed

The next implementation plan must define explicit server-enforced states for:

- retailer application: ASM draft, submitted to RSM, more information requested,
  resubmitted, RSM approved/rejected, and final customer creation;
- ASM visit obligation and report: due, completed, submitted to RSM, approved,
  returned/rejected and corrected where permitted;
- RSM visit obligation and report: upcoming, due, grace, overdue/escalated, completed,
  submitted to administrator, approved or returned;
- Sales Order: ASM draft, submitted for RSM approval, returned/rejected, approved, and
  then native ERPNext submission/fulfilment states; and
- later credit/exposure change: RSM proposal, administrator approved/rejected and applied.

Reviewed records must not be silently editable. Corrections should be new revisions,
amendments or explicit return-and-resubmit actions with an audit trail.

## Requirements still expected in the next prompt

The following details are intentionally open rather than guessed:

- obligations specific to **Buy & Sell — Stock Correction**;
- obligations specific to **EBOC**;
- whether SIS, EBOC or any other store stock is company-owned/consignment stock;
- exact stock-correction workflow and approval authority;
- exact monthly and quarterly calendar semantics;
- seasonal definitions, order windows and reminder timing;
- the RSM advance-warning threshold before day 80;
- what qualifies as a visit and whether geolocation/photo/check-in evidence is required;
- required ASM general-visit and order-review fields;
- exact footfall format and period;
- whether 3–4 ASMs and 200–250 shops are hard capacity rules or planning guidance;
- the 90/120-day collection escalation and blocking behavior;
- credit/exposure valuation and interaction with ERPNext accounting credit limits;
- who can return, reject, amend or exceptionally override applications, visits and orders;
- notification channels and escalation recipients; and
- migration treatment for existing users, roles, applications, visits and retailer
  assignments.

## Non-negotiable implementation boundaries

- Do not modify ERPNext, Frappe, India Compliance or Insights source.
- Keep ERPNext Customer, Territory, Customer Group, Sales Order, Delivery Note, Sales
  Invoice, Payment Entry, Warehouse and accounting/stock ledgers authoritative.
- Enforce role, hierarchy, Territory, state transition and approval rules on the server.
- Use native ERPNext settings and controllers wherever they express the requirement.
- Do not duplicate receivables, inventory, pricing, tax or commission ledgers.
- Make scheduled generation and escalation idempotent and test boundary dates.
- Add permission, cross-user, concurrency and audit tests before exposing each workflow.

