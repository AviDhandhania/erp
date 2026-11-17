# Access Control Matrix — Clothing ERP Suite

## 1. Principles of Authorization

1. **Default Deny**: Unless a role is explicitly granted read, write, create, delete, submit, or cancel permissions on a DocType, page, report, or API endpoint, access is strictly forbidden.
2. **Server-Side Enforcement**: All permissions are evaluated in Python controllers (`has_permission`, `doc.check_permission`, or explicit role assertions like `require_role`, `is_clothing_admin`). Client-side UI hiding or link omission is treated as cosmetic and never as security.
3. **Object-Level Scoping**:
   - **Sales ERP**: Scoped strictly by **Sales Territory** (ASM assigned to leaf Territory; RSM assigned to supervisory union of ASM Territories via `tabASM Supervision`). Native Frappe `User Permission` on `Territory` is maintained automatically.
   - **Warehouse ERP**: Scoped strictly by **Warehouse** via native Frappe `User Permission` on `Warehouse`.
   - **Quality ERP**: Scoped strictly by **Supplier** and authorized purchasing company.
4. **Separation of Duties**:
   - Sales personnel cannot modify inventory ledgers, perform picking, or inspect quality gates.
   - Warehouse Managers cannot alter commercial pricing, submit financial invoices, or approve credit limits.
   - Quality Inspectors cannot alter stock balances or bypass warehouse physical intake.

---

## 2. Role Definitions

| Role Identifier | Desk Access | Scope Boundary | Description |
|---|---|---|---|
| **Administrator** | Full Desk | Global | System root user; required for critical quality gates (Production Go Ahead & Final Inspection) and server administration. |
| **System Manager** | Full Desk | Global | Technical Frappe system administrator (user accounts, roles, site settings, system maintenance). |
| **Clothing Business Administrator** | Full Desk | Global (Suite) | Business oversight across Sales, Warehouse, and Quality. Approves credit limits, assigns ASM/RSM supervision, and oversees exceptions. |
| **Clothing Regional Sales Manager** | Restricted Desk | Assigned ASM Territories | Supervises 3–4 ASMs. Approves retailer applications, proposes credit limit increases, reviews visits, monitors 80-day cadence. |
| **Clothing Area Sales Manager** | Restricted Desk | Assigned Leaf Territory | Field sales executive. Creates retailer applications, logs store visits, creates draft sales orders, completes delivery follow-ups. |
| **Clothing Warehouse Manager** | Restricted Desk | Assigned Warehouses | Responsible for fulfillment: barcode scan verification, Pick List shortage resolution, packing, dispatch, return quarantine intake. |
| **Clothing Quality Inspector** | Restricted Desk | Assigned Suppliers / Inspections | Performs 7-stage quality lifecycle inspections, captures measurements and defect photos, inspects returned garments. |
| **Clothing Quality Manager** | Restricted Desk | Assigned Suppliers / Inspections | Supervises quality inspections, reviews revisions, coordinates gate prerequisites. |
| *[DEPRECATED]* **Clothing Warehouse Operator** | Legacy (None) | None | **Marked for complete deprecation & removal in Session 2**. All active operational permissions are restricted to Warehouse Manager. |

---

## 3. DocType Permissions Matrix (CRUD + Submit / Cancel / Export)

Legend:
- `C` = Create
- `R` = Read (Subject to Territory / Warehouse / Supplier object-level filtering)
- `W` = Write / Edit
- `D` = Delete
- `S` = Submit (Submittable DocTypes)
- `X` = Cancel
- `E` = Export (CSV / Excel / PDF)
- `—` = Denied

### 3.1 Custom Suite DocTypes

| DocType | Administrator / System Mgr | Clothing Business Admin | Regional Sales Mgr (RSM) | Area Sales Mgr (ASM) | Warehouse Manager | Quality Inspector | Quality Manager |
|---|---|---|---|---|---|---|---|
| **ASM Supervision** | C R W D E | C R W D E | R E (Scoped) | R (Own only) | — | — | — |
| **Retailer Application** | C R W D E | C R W D E | C R W E (Scoped) | C R W (Own/Draft) | — | — | — |
| **Retailer Visit** | C R W D E | C R W D E | C R W E (Scoped) | C R W (Own/Scoped) | — | — | — |
| **Retailer Credit Limit Request** | C R W D E | C R W D E | C R W E (Propose) | R (View only) | — | — | — |
| **Retailer Assignment History** | R E | R E | R E (Scoped) | R (Scoped) | — | — | — |
| **ASM Visit Obligation** | C R W D E | C R W D E | R W E (Scoped) | R W (Scoped) | — | — | — |
| **RSM Visit Obligation** | C R W D E | C R W D E | R E (Scoped) | R (Scoped) | — | — | — |
| **Delivery Follow-Up Obligation** | C R W D E | C R W D E | R E (Scoped) | R W (Scoped) | — | — | — |
| **Clothing Product Image** | C R W D E | C R W D E | R | R | R | R | R |
| **Supplier Quality Inspection** | C R W D E | C R W D E | — | — | — | C R W | C R W E |
| **Return Quarantine** | C R W D E | C R W D E | — | — | C R W (Intake) | C R W (Inspect) | C R W E |

### 3.2 Native ERPNext Core DocTypes (Governed by Suite)

| DocType | Administrator / System Mgr | Clothing Business Admin | Regional Sales Mgr (RSM) | Area Sales Mgr (ASM) | Warehouse Manager | Quality Inspector | Quality Manager |
|---|---|---|---|---|---|---|---|
| **Customer** (Retailer) | C R W D S E | C R W E | R E (Scoped) | R (Scoped) | R (Scoped) | — | — |
| **Sales Order** | C R W D S X E | C R W S X E | R (Scoped) | C R W (Draft only) | R (Approved only) | — | — |
| **Pick List** | C R W D S X E | C R W S X E | — | — | R W S (Scoped) | — | — |
| **Delivery Note** | C R W D S X E | C R W S X E | R (Scoped) | R (Scoped) | C R W S (Scoped) | — | — |
| **Packing Slip** | C R W D S X E | C R W S X E | — | — | C R W S (Scoped) | — | — |
| **Stock Entry** | C R W D S X E | C R W S X E | — | — | C R W S (Scoped) | — | — |
| **Serial & Batch Bundle** | C R W D S X E | C R W S X E | — | — | C R W S (Scoped) | — | — |
| **Supplier** | C R W D E | C R W E | — | — | R | R (Scoped) | R (Scoped) |
| **Purchase Order** | C R W D S X E | C R W S X E | — | — | R | R (Scoped) | R (Scoped) |
| **Item** (Garment SKU/Variant) | C R W D E | C R W E | R | R | R | R | R |
| **Item Price** | C R W D E | C R W E | R | R | — | — | — |
| **Territory** | C R W D E | C R W E | R (Scoped) | R (Scoped) | — | — | — |
| **Warehouse** | C R W D E | C R W E | — | — | R (Scoped) | — | — |

---

## 4. UI Desk Pages & Reports Access

| Resource | Resource Type | Allowed Roles | Access Scope Enforced |
|---|---|---|---|
| `clothing_catalogue` | Page | ASM, RSM, Business Admin, Admin | Global catalogue; variant stock visibility filtered by user company. |
| `clothing_orders` | Page | ASM, RSM, Business Admin, Admin | Scoped by assigned Sales Territories; ASM sees own/territory drafts; RSM sees territory orders. |
| `product_pricing` | Page | Business Admin, Admin (Read for RSM) | Read-only matrix for sales; mutation restricted to Administrator. |
| `retailer_assignments` | Page | Business Admin, Admin | Only authorized administrators can assign or reassign ASMs/RSMs. |
| `fulfillment_tasks` | Page | Warehouse Manager, Business Admin, Admin | Scoped strictly to user's assigned warehouse(s); Pick Lists and Delivery Notes. |
| `retailer_visit_report` | Report | ASM, RSM, Business Admin, Admin | Scoped strictly to user's assigned sales territories. |

---

## 5. Whitelisted API Security Matrix

| API Group / Endpoint | HTTP Method | Allowed Roles | Object Scoping & Server Authority Checks |
|---|---|---|---|
| **Sales Ordering** | | | |
| `get_catalogue` | GET | ASM, RSM, Business Admin, Admin | Bounded pagination; read-only projection; price list validation. |
| `get_clothing_orders` | GET | ASM, RSM, Business Admin, Admin | Filters orders by `get_effective_sales_territory_names(user)`. |
| `create_draft_sales_order` | POST | ASM, RSM, Business Admin, Admin | Validates customer belongs to user's territory; verifies stock exposure limit. |
| `submit_clothing_order` | POST | RSM, Business Admin, Admin | ASM cannot submit; validates native ERPNext sales order workflow. |
| `cancel_clothing_order` | POST | RSM, Business Admin, Admin | Validates draft or unfulfilled state; cancels linked stock reservations. |
| **Retailer Applications** | | | |
| `approve` (Application) | POST | RSM, Business Admin, Admin | ASM cannot approve; inserts Customer/Address/Contact under row lock. |
| `request_more_info` | POST | RSM, Business Admin, Admin | Sets status to `Information Requested`; records comments. |
| `resubmit` | POST | ASM, RSM, Business Admin, Admin | Only allowed if status is `Information Requested`; verifies user owns territory. |
| `reject` (Application) | POST | RSM, Business Admin, Admin | Requires non-empty rejection reason; marks application `Rejected`. |
| **Credit Adjustments** | | | |
| `propose_credit_limit` | POST | RSM, Business Admin, Admin | ASM cannot propose; creates pending request with justification. |
| `approve_credit_limit_request` | POST | Administrator, Business Admin | Row locks request (`FOR UPDATE`); re-evaluates live limit; sets customer credit. |
| `reject_credit_limit_request` | POST | Administrator, Business Admin | Mandatory rejection reason; row locks request. |
| **Cadence & Follow-up** | | | |
| `get_rsm_visit_cadence_report` | GET | RSM, Business Admin, Admin | Territory-filtered 80-day cycle calculations. |
| `record_delivery_follow_up` | POST | ASM, RSM, Business Admin, Admin | Checks `_can_record_follow_up(doc, user)` based on delivery territory. |
| **Warehouse Fulfillment** | | | |
| `get_fulfillment_tasks` | GET | Warehouse Manager, Business Admin, Admin | Scoped to warehouses in user's `User Permission`. |
| `verify_pick_item` | POST | Warehouse Manager, Business Admin, Admin | Row-locks Pick List; verifies barcode, batch, serial; updates picked qty. |
| `undo_pick_item_scan` | POST | Warehouse Manager, Business Admin, Admin | Row-locks Pick List; rolls back picked quantity for unsubmitted pick. |
| `resolve_pick_shortage` | POST | Warehouse Manager, Business Admin, Admin | Validates shortage reason; updates ERPNext Pick List row. |
| `complete_pick_list` | POST | Warehouse Manager, Business Admin, Admin | Submits native Pick List; closes assignments; creates bundles. |
| `dispatch_delivery_note` | POST | Warehouse Manager, Business Admin, Admin | Row-locks Delivery Note; validates transporter info; records LR details. |
| **Quality Inspections** | | | |
| `create_quality_inspection` | POST | Quality Inspector, Quality Manager, Admin | Enforces 7-stage sequential progression (stages 1-7). |
| `approve_quality_gate` | POST | Quality Manager, Admin (Admin for PGA & Final) | Verifies stage prerequisites; requires Administrator for stages 4 and 7. |
| `reject_quality_gate` | POST | Quality Manager, Admin | Mandatory rejection reason; triggers correction cycle. |
| `record_return_quarantine` | POST | Warehouse Manager, Business Admin, Admin | Intakes customer returns into physical quarantine warehouse. |
| `inspect_return_quarantine` | POST | Quality Inspector, Quality Manager, Admin | Records defect inspection decision (Pass/Restock, Refurbish, Scrap). |

---

## 6. Access Revocation & Cache Invalidation

When an employee is terminated, re-assigned, or has roles revoked:
1. **Disabled User (`tabUser.enabled = 0`)**:
   - Frappe session is invalidated immediately via `frappe.sessions.clear_sessions(user)`.
   - Redis cached user roles and permissions (`user_roles:<user>`, `user_permissions:<user>`) are evicted.
   - Any subsequent HTTP request returns HTTP 403 Forbidden / Login Redirect.
2. **Supervision Re-assignment (`ASM Supervision`)**:
   - Calling `end_asm_supervision` or `assign_asm_supervision` modifies `tabUser Permission` on `Territory`.
   - Evicts Redis permission cache for both ASM and RSM.
   - The user immediately loses access to the old territory's orders, retailers, visits, and obligations.
3. **Warehouse Assignment Removal (`User Permission` on Warehouse)**:
   - Deleting the `User Permission` row evicts cached warehouse permissions.
   - Immediate rejection on `get_fulfillment_tasks` and `verify_pick_item` for documents referencing that warehouse.
