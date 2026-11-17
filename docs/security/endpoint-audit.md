# Security & Privileged Operation Audit Ledger — Clothing ERP Suite

## 1. Whitelisted API Endpoint Inventory (63 Endpoints)

All endpoints decorated with `@frappe.whitelist` across `sales_erp`, `warehouse_erp`, and `quality_erp` were discovered via AST parsing.

### 1.1 Sales ERP (`sales_erp`) — 35 Endpoints

| Endpoint & Location | HTTP Method | Allowed Roles | Object Scope / Authority Checks | Transaction / Row-Lock | Audit Event |
|---|---|---|---|---|---|
| `api.get_user_context` (L10) | GET/POST | All Authenticated | Self context (`frappe.session.user`) | None | None |
| `api.switch_preview_role` (L18) | POST | None | Throws `PermissionError` (Deprecated) | None | Security error logged |
| `api.get_salesperson_dashboard` (L51) | GET/POST | ASM, RSM, Admin | Scoped to assigned territories | None | None |
| `api.get_warehouse_dashboard` (L100) | GET/POST | Warehouse Mgr, Admin | Scoped to assigned warehouses | None | None |
| `api.get_retailer_directory` (L108) | GET/POST | ASM, RSM, Admin | `get_effective_sales_territory_names` | None | None |
| `api.get_retailer_detail` (L130) | GET/POST | ASM, RSM, Admin | Verified customer in territory | None | None |
| `catalogue.get_catalogue` (L197) | GET/POST | All Sales Roles | Price list & company validation; bounded | None | None |
| `catalogue.get_catalogue_filters` (L327) | GET/POST | All Sales Roles | Static item attributes | None | None |
| `pricing.get_product_pricing` (L202) | GET/POST | ASM, RSM, Admin | Price list read access | None | None |
| `pricing.set_template_price` (L262) | POST | Admin, Business Admin | Only Administrator can alter prices | `SELECT name FROM tabItem FOR UPDATE` | Price updated |
| `ordering.get_clothing_orders` (L253) | GET/POST | ASM, RSM, Admin | Scoped by assigned territories | None | None |
| `ordering.get_retailer_stock_exposure` (L314) | GET/POST | ASM, RSM, Admin | Territory customer check | Bounded aggregates | None |
| `ordering.get_clothing_order` (L398) | GET/POST | ASM, RSM, Admin | Verified territory ownership | None | None |
| `ordering.create_draft_sales_order` (L527) | POST | ASM, RSM, Admin | Customer territory check + credit exposure | Row lock on Customer | Draft Order Created |
| `ordering.submit_clothing_order` (L441) | POST | RSM, Business Admin | ASM forbidden; native SO controller | `SELECT name FROM tabSales Order FOR UPDATE` | Native SO submission |
| `ordering.cancel_clothing_order` (L497) | POST | RSM, Business Admin | ASM forbidden; native cancel controller | `SELECT name FROM tabSales Order FOR UPDATE` | Native SO cancellation |
| `retailer_assignment.get_reassignment_directory` (L159) | GET/POST | Admin, Business Admin | Only Admin/Business Admin | None | None |
| `retailer_assignment.get_retailer_assignment` (L217) | GET/POST | ASM, RSM, Admin | Territory check | None | None |
| `retailer_assignment.reassign_retailer` (L255) | POST | Admin, Business Admin | `assert_sales_admin()` | Row lock on Customer | Retailer Assignment Log |
| `retailer_assignment.bulk_reassign_retailers` (L337) | POST | Admin, Business Admin | `assert_sales_admin()`; bounded (<=100) | Atomic transaction | Retailer Assignment Log |
| `supervision.assign_asm_supervision` (L374) | POST | Admin, Business Admin | `assert_supervision_admin()` | Row locks on ASM Supervision & Territory | Supervision Assignment Log |
| `supervision.end_asm_supervision` (L502) | POST | Admin, Business Admin | `assert_supervision_admin()` | Row lock on ASM Supervision | Supervision Assignment Log |
| `supervision.get_territory_assignment_history` (L548) | GET/POST | RSM, Admin | Territory scope check | None | None |
| `supervision.get_asm_supervision_directory` (L577) | GET/POST | RSM, Admin | Admin/RSM scope | None | None |
| `supervision.sales_role_user_query` (L644) | GET/POST | ASM, RSM, Admin | Desk user query filter | None | None |
| `cadence.get_rsm_visit_cadence_report` (L428) | GET/POST | RSM, Admin | Territory-filtered 80-day cycle | Bounded queries | None |
| `cadence.get_asm_cadence_directory` (L871) | GET/POST | ASM, RSM, Admin | Territory-filtered ASM obligations | Bounded queries | None |
| `cadence.get_collection_obligations` (L946) | GET/POST | ASM, RSM, Admin | Territory-filtered 90-120 day window | Bounded queries | None |
| `delivery_follow_up.record_delivery_follow_up` (L110) | POST | ASM, RSM, Admin | `_can_record_follow_up(doc, user)` | Row lock on Obligation | Delivery Follow-up Log |
| `delivery_follow_up.get_delivery_follow_up_obligations` (L215) | GET/POST | ASM, RSM, Admin | Scoped list query | None | None |
| `retailer_application.get_territory_assignment` (L155) | GET/POST | ASM, RSM, Admin | Territory lookup | None | None |
| `retailer_application.approve` (L295) | POST | RSM, Business Admin | ASM forbidden; valid credit limit | Row lock on Application | Customer Created |
| `retailer_application.request_more_info` (L393) | POST | RSM, Business Admin | ASM forbidden | Row lock on Application | RFI recorded |
| `retailer_application.resubmit` (L425) | POST | ASM, RSM, Admin | Validates ASM territory ownership | Row lock on Application | Resubmitted recorded |
| `retailer_application.reject` (L454) | POST | RSM, Business Admin | ASM forbidden; mandatory reason | Row lock on Application | Rejection recorded |
| `retailer_visit.review_visit` (L225) | POST | RSM, Business Admin | ASM forbidden; validates supervision | Row lock on Retailer Visit | Visit Reviewed |
| `retailer_credit_limit_request.propose_credit_limit` (L329) | POST | RSM, Business Admin | ASM forbidden; positive limit | Row lock on Customer | Credit Request Created |
| `retailer_credit_limit_request.approve_credit_limit_request` (L174) | POST | Admin, Business Admin | `is_clothing_admin()` | Row lock on Request & Customer | Credit Limit Approved |
| `retailer_credit_limit_request.reject_credit_limit_request` (L254) | POST | Admin, Business Admin | `is_clothing_admin()`; mandatory reason | Row lock on Request | Credit Request Rejected |

---

### 1.2 Warehouse ERP (`warehouse_erp`) — 16 Endpoints

| Endpoint & Location | HTTP Method | Allowed Roles | Object Scope / Authority Checks | Transaction / Row-Lock | Audit Event |
|---|---|---|---|---|---|
| `fulfillment.get_fulfillment_tasks` (L41) | GET/POST | Warehouse Mgr, Admin | User Permission on Warehouse | Bounded pagination | None |
| `fulfillment.get_fulfillment_task` (L94) | GET/POST | Warehouse Mgr, Admin | Warehouse permission check | None | None |
| `fulfillment.verify_pick_item` (L440) | POST | Warehouse Mgr, Admin | Warehouse permission check | `SELECT name FROM tabPick List FOR UPDATE` | Pick Scan Recorded |
| `fulfillment.undo_pick_item_scan` (L485) | POST | Warehouse Mgr, Admin | Warehouse permission check | `SELECT name FROM tabPick List FOR UPDATE` | Scan Reversal Log |
| `fulfillment.resolve_pick_shortage` (L555) | POST | Warehouse Mgr, Admin | Warehouse permission check | `SELECT name FROM tabPick List FOR UPDATE` | Pick Shortage Log |
| `fulfillment.split_pick_shortage_row` (L609) | POST | Warehouse Mgr, Admin | Warehouse permission check | `SELECT name FROM tabPick List FOR UPDATE` | Row Split Log |
| `fulfillment.complete_pick_list` (L707) | POST | Warehouse Mgr, Admin | Submits native ERPNext Pick List | Row lock on Pick List & Bundles | Pick List Submitted |
| `fulfillment.create_delivery_note_from_pick` (L757) | POST | Warehouse Mgr, Admin | Warehouse permission check | Row lock on Pick List | Delivery Note Created |
| `fulfillment.create_packing_slip` (L825) | POST | Warehouse Mgr, Admin | Warehouse permission check | Row lock on Delivery Note | Packing Slip Created |
| `fulfillment.dispatch_delivery_note` (L903) | POST | Warehouse Mgr, Admin | Warehouse permission check | Row lock on Delivery Note | Delivery Dispatched |
| `fulfillment.bulk_create_delivery_notes_from_picks` (L961) | POST | Warehouse Mgr, Admin | Bounded batch (<=50); Warehouse check | Atomic per-document transaction | Bulk DN Log |
| `fulfillment.bulk_dispatch_delivery_notes` (L1009) | POST | Warehouse Mgr, Admin | Bounded batch (<=50); Warehouse check | Atomic per-document transaction | Bulk Dispatch Log |
| `fulfillment.get_task_manifest` (L1068) | GET/POST | Warehouse Mgr, Admin | Warehouse permission check | Read-only projection | Manifest Generation |
| `returns.intake_customer_return` (L112) | POST | Warehouse Mgr, Admin | Warehouse permission check | Row lock on Delivery Note | Quarantine Intake Log |
| `returns.move_to_refurbishment` (L273) | POST | Warehouse Mgr, Admin | Warehouse permission check | Row lock on Return Quarantine | Stock Transfer Log |
| `returns.complete_refurbishment` (L353) | POST | Warehouse Mgr, Admin | Warehouse permission check | Row lock on Return Quarantine | Restock Stock Entry Log |

---

### 1.3 Quality ERP (`quality_erp`) — 8 Endpoints

| Endpoint & Location | HTTP Method | Allowed Roles | Object Scope / Authority Checks | Transaction / Row-Lock | Audit Event |
|---|---|---|---|---|---|
| `quality.create_quality_inspection` (L64) | POST | Quality Inspector, Quality Mgr, Admin | Sequential stage validation (1-7) | Row lock on Supplier & PO | Inspection Created |
| `quality.revise_quality_inspection` (L100) | POST | Quality Inspector, Quality Mgr, Admin | Inspects rejected report; increments revision | Row lock on Inspection | Inspection Revised |
| `quality.approve_quality_gate` (L142) | POST | Quality Mgr, Admin (Admin for PGA & Final) | Verifies stage prerequisites; admin check | Row lock on Inspection | Gate Approved |
| `quality.reject_quality_gate` (L189) | POST | Quality Mgr, Admin | Mandatory non-empty reason | Row lock on Inspection | Gate Rejected |
| `quality.get_quality_review_bundle` (L216) | GET/POST | Quality Mgr, Admin | Bounded review bundle projection | None | None |
| `quality.record_return_quarantine` (L279) | POST | Warehouse Mgr, Quality Mgr, Admin | Quarantine warehouse validation | Row lock on Return Quarantine | Quarantine Intake |
| `quality.inspect_return_quarantine` (L315) | POST | Quality Inspector, Quality Mgr, Admin | Quality inspection decision validation | Row lock on Return Quarantine | Inspection Decision |
| `quality.get_quality_dashboard_summary` (L363) | GET/POST | Quality Inspector, Quality Mgr, Admin | Supplier / item aggregation | Parameterized counts | None |

---

## 2. Privileged `ignore_permissions=True` Audit (55 Locations)

Every occurrence of `ignore_permissions=True` was analyzed to verify its necessity, preceding authority checks, and security isolation:

### 2.1 Installation & Provisioning (26 Calls)
- **Files**: `sales_erp/install.py` (8), `sales_erp/seed.py` (7), `warehouse_erp/install.py` (4), `warehouse_erp/seed.py` (3), `quality_erp/install.py` (2), `quality_erp/seed.py` (2).
- **Purpose**: Idempotent post-installation setup of system roles, DocPerms, seed customers, suppliers, and items.
- **Security Proof**: Runs exclusively during bench install/migration (`after_install`, `after_migrate`) or via direct CLI commands (`bench seed-clothing-demo`). Never accessible to unprivileged web requests.

### 2.2 Retailer Application Approval (4 Calls)
- **File**: `sales_erp/doctype/retailer_application/retailer_application.py` (Lines 252, 266, 325, 352).
- **Purpose**: On RSM approval of a prospective retailer, creates native ERPNext `Customer`, `Address`, `Contact`, and `Dynamic Link` records.
- **Security Proof**: Preceded by `require_role(ROLE_RSM)`, territory verification, and row-locking on the application. ASMs are strictly forbidden from approving applications. Native validation hooks on Customer are preserved.

### 2.3 Sales Order Creation (1 Call)
- **File**: `sales_erp/ordering.py` (Line 588).
- **Purpose**: Inserts a draft `Sales Order` into ERPNext.
- **Security Proof**: Preceded by strict validation of user's assigned territory, positive line item counts, item variant validity, and customer credit exposure check. The order is inserted strictly as a `Draft` (DocStatus 0); native submission controllers still evaluate native DocPerms.

### 2.4 Credit Limit Approval & Requests (4 Calls)
- **File**: `sales_erp/doctype/retailer_credit_limit_request/retailer_credit_limit_request.py` (Lines 218, 227, 297, 302).
- **Purpose**: Saves the decision on `Retailer Credit Limit Request` and inserts system `Notification Log` alerts.
- **Security Proof**: Preceded by `is_clothing_admin(user)` verification. Rejection and approval require row locking and live customer credit limit verification.

### 2.5 Retailer Supervision & Permissions Sync (4 Calls)
- **File**: `sales_erp/supervision.py` (Lines 95, 177, 369), `sales_erp/retailer_assignment.py` (Lines 299, 304, 325).
- **Purpose**: Inserts/deletes native Frappe `User Permission` records for `Territory` to mirror supervision assignments.
- **Security Proof**: Preceded by `assert_supervision_admin()`. Unprivileged users cannot modify supervision records or manipulate user permissions.

### 2.6 Warehouse Serial & Batch Bundle Allocation (5 Calls)
- **File**: `warehouse_erp/fulfillment.py` (Lines 381, 469, 540, 694, 889).
- **Purpose**: Creates and submits native ERPNext `Serial and Batch Bundle` entries during pick list scan completion.
- **Security Proof**: Preceded by warehouse scoping validation and row-locking of the Pick List. The bundle matches scanned barcodes against the ERPNext item ledger.

### 2.7 Gallery Image Lifecycle (1 Call)
- **File**: `sales_erp/gallery.py` (Line 43).
- **Purpose**: Background cleanup of unreferenced temporary product gallery images.
- **Security Proof**: Executed via background scheduled task (`sweep_stale_clothing_product_images`); checks file reference counts before deletion.

---

## 3. Direct Database Mutations & Deletion Audit

### 3.1 Direct `frappe.db.set_value` Calls (12 Locations)
- `sales_erp/cadence.py` (L178, L223, L319, L789, L833): Atomic status updates for automated visit cadence obligations during cron sweeps (`Satisfied`, `Overdue`, `Escalated`). Preceded by date checks.
- `sales_erp/supervision.py` (L124, L169, L211, L218): Setting `status='Superseded'` and `effective_to` on superseded `ASM Supervision` records. Preceded by `assert_supervision_admin()`.
- `sales_erp/install.py` (L69), `sales_erp/seed.py` (L532, L538): Configuration setup during migration/seeding.

### 3.2 Direct `frappe.delete_doc` Calls (7 Locations)
- `sales_erp/supervision.py` (L177): Deletes stale `User Permission` on territory reassignment. Preceded by `assert_supervision_admin()`.
- `sales_erp/retailer_assignment.py` (L299): Deletes legacy per-customer User Permissions. Preceded by `assert_sales_admin()`.
- `sales_erp/gallery.py` (L43): Deletes orphaned temporary gallery images.
- `sales_erp/install.py` (L38, L40, L42, L161): Deletes legacy roles and deprecated permissions on install.

---

## 4. Raw SQL Query (`frappe.db.sql`) Audit (82 Queries)

All 82 raw SQL queries were audited for parameterization and row-level concurrency:
- **Parameterization**: 100% of queries accepting external parameters pass values via tuple or dictionary parameter bindings (`%s` / `%(param)s`). Zero instances of direct unsanitized variable string interpolation.
- **Row-Locking (`FOR UPDATE`)**: Row locks are applied on all critical state transitions:
  - `tabSales Order` during submission and cancellation.
  - `tabCustomer` during credit limit changes and order creation.
  - `tabPick List` and `tabSerial and Batch Bundle` during item verification and completion.
  - `tabDelivery Note` during return intake and dispatch.
  - `tabSupplier Quality Inspection` during gate decisions and revisions.
  - `tabReturn Quarantine` during quarantine inspections and refurbishment moves.
  - `tabASM Supervision` during territory assignments.

---

## 5. Identified Security Gaps & Remediation Schedule

| Finding | Severity | Description | Remediation Target |
|---|---|---|---|
| **GAP-01: Implicit GET Endpoints** | Low | Several read endpoints do not specify `methods=["GET"]`, accepting any HTTP method by default. | Session 3 (API Security) |
| **GAP-02: Legacy Warehouse Operator Role** | High | `ROLE_WAREHOUSE_OPERATOR` is still granted read on native DocTypes in `warehouse_erp/install.py`. | Session 2 (Authorization) |
| **GAP-03: Single Photo Quality Evidence** | Medium | Quality inspections and return quarantine currently use a single `Attach Image` field rather than a multi-photo child table. | Session 4 (Files & Privacy) |
| **GAP-04: Static Security Assertions** | Medium | Need automated unit tests verifying that all mutating endpoints enforce POST and reject SQL string interpolation. | Session 1 (Automated Checks) |
