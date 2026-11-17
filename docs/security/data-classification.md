# Data Classification & Privacy Inventory — Clothing ERP Suite

## 1. Classification Framework & Sensitivity Tiers

Data handled by the Clothing ERP Suite is classified into four security sensitivity tiers, dictating encryption, access control, export permissions, logging redaction, and retention periods:

| Tier | Classification Level | Description | Handling & Protection Requirements |
|---|---|---|---|
| **Tier 1** | **Public** | Information approved for general distribution without restriction. | Integrity protected; no confidentiality controls needed. |
| **Tier 2** | **Internal** | Non-sensitive operational data accessible to all authenticated internal employees. | Requires authentication; accessible across active user roles. |
| **Tier 3** | **Confidential** | Sensitive operational, stock, commercial, and operational records. | Role-based and scope-restricted (Territory, Warehouse, Supplier); logged exports. |
| **Tier 4** | **Restricted / PII** | Personally Identifiable Information (PII), credentials, financial exposure, and tax identifiers. | Strict need-to-know, row-level access, encrypted at rest, export restricted, masked in logs. |

---

## 2. Comprehensive Field Inventory across Suite DocTypes

### 2.1 Retailer Application (`sales_erp`)
Captures prospective retailer intake, contact details, commercial requests, and initial approval evidence.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `shop_name` | Commercial | Tier 2 (Internal) | Sales ASM | Retailer identity | 7 years | Scoped CSV/PDF | Logged |
| `contact_person` | Personal (PII) | Tier 4 (Restricted) | Sales ASM | Primary store contact | 7 years | Role-scoped | Redact in error logs |
| `phone` | Personal (PII) | Tier 4 (Restricted) | Sales ASM | Contact telephone | 7 years | Role-scoped | Mask last 4 digits in general logs |
| `email` | Personal (PII) | Tier 4 (Restricted) | Sales ASM | Contact email address | 7 years | Role-scoped | Redacted in tracebacks |
| `gstin` | Commercial / Tax | Tier 4 (Restricted) | Sales ASM | India GST identification | 7 years | Admin/RSM only | Redacted in standard logs |
| `billing_address_line1` | Location / PII | Tier 4 (Restricted) | Sales ASM | Legal billing location | 7 years | Role-scoped | Redacted in tracebacks |
| `billing_city` / `state` / `pincode` | Location | Tier 3 (Confidential) | Sales ASM | Territorial billing area | 7 years | Scoped CSV/PDF | Allowed in audit log |
| `shipping_address_line1` | Location / PII | Tier 4 (Restricted) | Sales ASM | Physical delivery location | 7 years | Role-scoped | Redacted in tracebacks |
| `shipping_city` / `state` / `pincode` | Location | Tier 3 (Confidential) | Sales ASM | Delivery destination area | 7 years | Scoped CSV/PDF | Allowed in audit log |
| `territory` | Location / Scope | Tier 2 (Internal) | Sales ASM | Leaf territory assignment | 7 years | Scoped CSV/PDF | Allowed |
| `customer_group` | Commercial | Tier 2 (Internal) | Sales ASM | Retailer classification | 7 years | Scoped CSV/PDF | Allowed |
| `initial_credit_limit` | Financial | Tier 4 (Restricted) | Sales RSM | Proposed credit ceiling | 7 years | Admin/RSM only | Redacted in unprivileged logs |
| `requested_information` | Commercial | Tier 3 (Confidential) | Sales RSM | Clarification notes | 7 years | Scoped CSV/PDF | Allowed |
| `info_requested_by` / `on` | Audit | Tier 3 (Confidential) | System | RFI audit trail | 7 years | Scoped CSV/PDF | Allowed |
| `reviewed_by` / `on` | Audit | Tier 3 (Confidential) | System | Approval audit trail | 7 years | Scoped CSV/PDF | Allowed |
| `rejection_reason` | Commercial | Tier 3 (Confidential) | Sales RSM | Intake rejection justification | 7 years | Admin/RSM only | Allowed |

---

### 2.2 Retailer Visit (`sales_erp`)
Records store visits, dealer feedback, footfall observations, and supervisory review.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `customer` / `customer_name` | Commercial | Tier 2 (Internal) | Sales ASM | Visited store identifier | 3 years | Scoped CSV/PDF | Allowed |
| `salesperson` / `rsm` | Audit / User | Tier 2 (Internal) | Sales ASM | Visitor and supervisor identity | 3 years | Scoped CSV/PDF | Allowed |
| `visit_date` | Audit | Tier 2 (Internal) | Sales ASM | Physical visit timestamp | 3 years | Scoped CSV/PDF | Allowed |
| `visitor_role` / `visit_type` | Commercial | Tier 2 (Internal) | Sales ASM | Cadence type (Monthly/SIS/RSM) | 3 years | Scoped CSV/PDF | Allowed |
| `outcome` / `notes` | Commercial | Tier 3 (Confidential) | Sales ASM | Store observations and actions | 3 years | Scoped CSV/PDF | Redact accidental PII |
| `financial_assessment` | Financial | Tier 4 (Restricted) | Sales RSM | Creditworthiness rating | 5 years | Admin/RSM only | Redacted in logs |
| `customer_footfall` | Commercial | Tier 3 (Confidential) | Sales RSM | Walk-in traffic observation | 3 years | Scoped CSV/PDF | Allowed |
| `stock_condition` | Stock | Tier 3 (Confidential) | Sales RSM | Display / stock cleanliness | 3 years | Scoped CSV/PDF | Allowed |
| `recommended_credit_limit` | Financial | Tier 4 (Restricted) | Sales RSM | Exposure recommendation | 5 years | Admin/RSM only | Redacted in logs |
| `dealer_feedback` | Commercial | Tier 3 (Confidential) | Sales RSM | Proprietary retailer feedback | 3 years | Admin/RSM only | Allowed |
| `reviewed_by` / `on` / `notes` | Audit | Tier 3 (Confidential) | System | Supervisory review trail | 3 years | Scoped CSV/PDF | Allowed |

---

### 2.3 Retailer Credit Limit Request (`sales_erp`)
Administrator-approved exposure adjustment requests linked to visits or operational growth.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `customer` / `customer_name` | Commercial | Tier 2 (Internal) | Sales RSM | Retailer reference | 7 years | Scoped CSV/PDF | Allowed |
| `company` / `currency` | Commercial | Tier 2 (Internal) | Sales RSM | Accounting entity context | 7 years | Scoped CSV/PDF | Allowed |
| `current_credit_limit` | Financial | Tier 4 (Restricted) | System | Live baseline credit ceiling | 7 years | Admin/RSM only | Redacted in general logs |
| `proposed_credit_limit` | Financial | Tier 4 (Restricted) | Sales RSM | Requested new credit ceiling | 7 years | Admin/RSM only | Redacted in general logs |
| `source_visit` | Commercial | Tier 3 (Confidential) | Sales RSM | Justifying visit reference | 7 years | Scoped CSV/PDF | Allowed |
| `reason` | Commercial | Tier 3 (Confidential) | Sales RSM | Written credit justification | 7 years | Admin/RSM only | Allowed |
| `proposer` / `proposed_on` | Audit | Tier 3 (Confidential) | System | Request origination audit | 7 years | Admin/RSM only | Allowed |
| `approver` / `decided_on` | Audit | Tier 4 (Restricted) | System | Decision maker audit | 7 years | Admin/RSM only | Allowed in security logs |
| `rejection_reason` | Commercial | Tier 3 (Confidential) | Business Admin | Denial reason | 7 years | Admin/RSM only | Allowed |

---

### 2.4 ASM Supervision & Assignment History (`sales_erp`)
Defines the supervisory hierarchy and sales territory boundaries.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `territory` | Location / Scope | Tier 2 (Internal) | Business Admin | Sales Territory boundary | Active + 5 yrs | Scoped CSV/PDF | Allowed |
| `asm` / `asm_name` | Personal / User | Tier 2 (Internal) | Business Admin | Assigned Area Sales Manager | Active + 5 yrs | Scoped CSV/PDF | Allowed |
| `rsm` / `rsm_name` | Personal / User | Tier 2 (Internal) | Business Admin | Supervising Regional Sales Manager | Active + 5 yrs | Scoped CSV/PDF | Allowed |
| `effective_from` / `to` | Audit | Tier 2 (Internal) | Business Admin | Effective date range | Active + 5 yrs | Scoped CSV/PDF | Allowed |
| `reason` | Audit | Tier 3 (Confidential) | Business Admin | Reassignment reason | Active + 5 yrs | Admin only | Allowed |
| `assigned_by` / `assigned_on` | Audit | Tier 3 (Confidential) | System | Admin action audit trail | Active + 5 yrs | Admin only | Allowed in security logs |
| `asm_user_permission` / `rsm_user_permission` | Credential / Scope | Tier 3 (Confidential) | System | Native Frappe permission mirror | Active | Forbidden | Allowed in security logs |

---

### 2.5 Visit & Cadence Obligations (`sales_erp`)
Tracks mandatory monthly, quarterly, 80-day RSM visits and 90-120 day collection cadences.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `customer` / `customer_name` | Commercial | Tier 2 (Internal) | Sales ASM | Retailer reference | 3 years | Scoped CSV/PDF | Allowed |
| `territory` | Location / Scope | Tier 2 (Internal) | Sales ASM | Territory context | 3 years | Scoped CSV/PDF | Allowed |
| `cycle_start` / `due_date` / `grace_end_date` | Commercial | Tier 2 (Internal) | System | Cadence timeline | 3 years | Scoped CSV/PDF | Allowed |
| `invoice_no` / `outstanding_amount` | Financial | Tier 4 (Restricted) | System | Outstanding invoice tracking | 7 years | Role-scoped | Redact in unprivileged logs |
| `qualifying_visit` | Commercial | Tier 3 (Confidential) | System | Visit satisfying obligation | 3 years | Scoped CSV/PDF | Allowed |
| `satisfied_on` / `satisfied_by` | Audit | Tier 3 (Confidential) | System | Satisfaction audit trail | 3 years | Scoped CSV/PDF | Allowed |
| `last_escalated_on` / `notes` | Audit | Tier 3 (Confidential) | System | Escalation history | 3 years | Admin/RSM only | Allowed |

---

### 2.6 Delivery Follow-Up Obligation (`sales_erp`)
Tracks ASM confirmation of delivery handoff with retailers.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `delivery_note` | Commercial | Tier 3 (Confidential) | Warehouse Mgr | ERPNext Delivery Note link | 5 years | Scoped CSV/PDF | Allowed |
| `customer` / `customer_name` | Commercial | Tier 2 (Internal) | Sales ASM | Retailer reference | 5 years | Scoped CSV/PDF | Allowed |
| `contact_person` | Personal (PII) | Tier 4 (Restricted) | Sales ASM | Person contacted at store | 5 years | Role-scoped | Redact in error logs |
| `contact_datetime` | Audit | Tier 3 (Confidential) | Sales ASM | Timestamp of communication | 5 years | Scoped CSV/PDF | Allowed |
| `outcome` / `issue_notes` | Commercial | Tier 3 (Confidential) | Sales ASM | Delivery outcome or dispute | 5 years | Scoped CSV/PDF | Redact customer PII |
| `satisfied_on` / `satisfied_by` | Audit | Tier 3 (Confidential) | System | Audit trail | 5 years | Scoped CSV/PDF | Allowed |

---

### 2.7 Supplier Quality Inspection (`quality_erp`)
Captures 7-stage quality lifecycle measurements, quality scores, photos, and gate decisions.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `supplier` | Commercial | Tier 3 (Confidential) | Quality Mgr | Manufacturing partner reference | 7 years | Role-scoped | Allowed |
| `item_code` | Stock | Tier 2 (Internal) | Quality Insp | Garment template/SKU inspected | 7 years | Scoped CSV/PDF | Allowed |
| `purchase_order` | Commercial | Tier 3 (Confidential) | Quality Mgr | Linked ERPNext PO | 7 years | Role-scoped | Allowed |
| `stage` | Commercial | Tier 2 (Internal) | Quality Insp | Sequential inspection stage (1-7) | 7 years | Scoped CSV/PDF | Allowed |
| `revision` / `supersedes` | Audit | Tier 3 (Confidential) | Quality Insp | Version tracking and immutability | 7 years | Scoped CSV/PDF | Allowed |
| `inspector` / `inspection_date` | Personal / Audit | Tier 3 (Confidential) | Quality Insp | Accountability trail | 7 years | Scoped CSV/PDF | Allowed |
| `spec_measurements` | Commercial / Tech | Tier 3 (Confidential) | Quality Insp | Detailed garment measurements | 7 years | Controlled PDF | Allowed |
| `fabric_quality_score` / `stitching_quality_score` | Commercial | Tier 3 (Confidential) | Quality Insp | Quantitative defect scoring | 7 years | Controlled PDF | Allowed |
| `photo_evidence` | Photograph (Evidence) | Tier 4 (Restricted) | Quality Insp | Defect and sample photographs | 7 years | Private stream | Must not be public URL |
| `approved_by` / `approval_date` | Audit | Tier 4 (Restricted) | Administrator | Gate authorization signature | 7 years | Controlled PDF | Allowed in security logs |
| `comments` | Commercial | Tier 3 (Confidential) | Quality Insp | Rejection reasons & remarks | 7 years | Controlled PDF | Allowed |

---

### 2.8 Return Quarantine (`quality_erp`)
Tracks receipt, isolation, defect inspection, and refurbishment of returned garments.

| Fieldname | Category | Sensitivity Tier | Owner | Purpose | Retention | Export Rule | Masking / Log Policy |
|---|---|---|---|---|---|---|---|
| `retailer` | Commercial | Tier 2 (Internal) | Warehouse Mgr | Customer returning items | 5 years | Scoped CSV/PDF | Allowed |
| `delivery_note` / `return_delivery_note` | Commercial | Tier 3 (Confidential) | Warehouse Mgr | Originating delivery documents | 5 years | Scoped CSV/PDF | Allowed |
| `item_code` / `quantity` | Stock | Tier 3 (Confidential) | Warehouse Mgr | Quarantined stock count | 5 years | Scoped CSV/PDF | Allowed |
| `quarantine_warehouse` / `target_warehouse` | Stock / Location | Tier 3 (Confidential) | Warehouse Mgr | Isolated storage bin | 5 years | Scoped CSV/PDF | Allowed |
| `return_reason` | Commercial | Tier 3 (Confidential) | Warehouse Mgr | Stated return rationale | 5 years | Scoped CSV/PDF | Allowed |
| `inspected_by` / `inspected_on` | Audit | Tier 3 (Confidential) | Quality Insp | Defect inspection audit | 5 years | Scoped CSV/PDF | Allowed |
| `photo_evidence` | Photograph (Evidence) | Tier 4 (Restricted) | Quality Insp | Defect evidence photos | 5 years | Private stream | Must not be public URL |
| `inspection_notes` | Commercial | Tier 3 (Confidential) | Quality Insp | Repair / scrap instructions | 5 years | Scoped CSV/PDF | Allowed |
| `stock_entry` / `restock_entry` | Stock / Audit | Tier 3 (Confidential) | System | ERPNext stock movement links | 5 years | Scoped CSV/PDF | Allowed |

---

### 2.9 Credentials, Tokens & Security Secrets (System-Wide)

| Artifact / Field | Category | Sensitivity Tier | Storage Location | Protection Control | Masking / Logging Policy |
|---|---|---|---|---|---|
| User Passwords | Credential | Tier 4 (Restricted) | `tabUser.password` | Salted SHA-256 / PBKDF2 hashes | Never logged; stripped in WSGI middleware |
| API Secrets / Keys | Credential | Tier 4 (Restricted) | `tabUser.api_secret` | Encrypted at rest via Frappe encryption key | Never displayed; logged as `*****` |
| Session Cookies / Tokens | Token | Tier 4 (Restricted) | Redis session DB | Signed cookies (`Secure`, `HttpOnly`, `SameSite=Lax`) | Redacted from web server and application logs |
| Mobile Refresh Tokens | Token | Tier 4 (Restricted) | Redis / Hardware Keystore | Hardware Keystore (Client) / Hashed (Server) | Redacted in tracebacks and analytics |
| Database Passwords | Credential | Tier 4 (Restricted) | `site_config.json` | Mode 0600 on disk, dedicated `frappe` user | Excluded from error payloads and crash dumps |
| GPG Backup Keys | Encryption Key | Tier 4 (Restricted) | Out-of-band key storage | Separated from backup archives | Strictly forbidden on production web workers |

---

## 3. Data Privacy, Redaction & Export Controls

### 3.1 Log Masking Policy
Application logs, worker output, and crash reports must automatically filter and redact:
- Any field named `password`, `api_secret`, `secret`, `token`, `key`, `authorization`, `cookie`.
- India GSTIN values (mask middle 10 alphanumeric characters in unprivileged logs).
- Customer telephone numbers (mask characters except initial 2 and final 2).
- Email addresses in raw exception traces.
- Private File URLs pointing to defect evidence or retailer documents.

### 3.2 Spreadsheet Injection Mitigation (CSV Exports)
All CSV and text export routines must sanitize string fields starting with `= `, `+ `, `- `, or `@ ` by prepending a single quote (`'`) to neutralize dynamic formula execution when opened in Excel or Calc.

### 3.3 Deletion and Anonymization Policy
- **Retailer PII**: Upon termination of business relations, personal contact names, personal phone numbers, and personal emails are anonymized to `anonymized@retailer.invalid` after the statutory 7-year tax/GST audit retention window expires.
- **Evidence Deletion**: Photograph attachments are deleted via reference-safe procedures only: files cannot be unlinked or removed if referenced by an active Quality Inspection or Return Quarantine record.
- **Audit Trails**: Document revision history, supervision assignment history, and credit limit approval records are **immutable** and cannot be deleted by non-administrators under any circumstances.
