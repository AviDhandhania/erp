# Clothing ERP — Master Development Roadmap (`work.md`)

This file is the single source of truth for the implementation of the `clothing_erp` application.
In every subsequent prompt, check this file to identify the next task and update progress.

---

## Overall Progress Summary

- **Stage 1 — Development Foundation**: [x] COMPLETED
- **Stage 2 — Roles and Operational Interface Foundation**: [x] COMPLETED
- **Stage 3 — Salesperson Catalogue**: [ ] PENDING (Next Stage)
- **Stage 4 — Retailer Management**: [ ] PENDING
- **Stage 5 — Salesperson Ordering**: [ ] PENDING
- **Stage 6 — Warehouse Operations**: [ ] PENDING
- **Stage 7 — Retailer-Direct Orders**: [ ] PENDING
- **Stage 8 — Notifications and Operational Improvements**: [ ] PENDING
- **Stage 9 — Security and Integration Testing**: [ ] PENDING
- **Stage 10 — GitHub Release System**: [ ] PENDING
- **Stage 11 — Proxmox LXC Installer**: [ ] PENDING
- **Stage 12 — Update and Maintenance System**: [ ] PENDING

---

## Stage-by-Stage Specifications & Checklist

### Stage 1 — Development Foundation [x] COMPLETED
- [x] Inspect existing ERPNext repository, Git branch, and working tree (clean on `develop`, untouched).
- [x] Check installed system tools on Arch Linux.
- [x] Determine best local development setup (containerized Docker Compose / Dev Containers; user-space preview).
- [x] Pin compatible versions: Frappe Framework `v16.55.2`, ERPNext `v16.54.0`, MariaDB 11.4 LTS.
- [x] Create separate custom Frappe application `clothing_erp` in `/home/avi/GitHub/erp/clothing_erp`.
- [x] Initialize independent Git repository on branch `main`.
- [x] Create README.md and AGENTS.md defining project rules (zero modifications to ERPNext core).
- [x] Add placeholder navigation for Admin, Products, Sales, Retailers, Warehouse, Suppliers, Reports.
- [x] Verify local server starts and responds on port 8000.
- [x] Write and run standalone unit tests (`test_home.py`).

---

### Stage 2 — Roles and Operational Interface Foundation [x] IN PROGRESS
**Acceptance Criterion:** Users can access only authorized functionality through ERPNext-identical Desk interfaces.
- [x] Define operational and management roles:
  - `Clothing Salesperson`
  - `Clothing Warehouse Operator`
  - `Clothing Sales Manager`
  - `Clothing Warehouse Manager`
  - `Clothing Business Administrator`
- [x] Implement post-install role provisioning in `clothing_erp/install.py`.
- [x] Create backend security & authorization module `clothing_erp/security.py`:
  - Server-side role validation (`is_salesperson`, `is_warehouse_operator`, `is_sales_manager`, etc.).
  - Decorators/guards for API methods (`require_role`, permission checks).
  - Document-level permission queries for assigned retailers and warehouses.
- [x] Implement Frappe Desk Workspaces:
  - Main `Clothing ERP` Workspace.
  - Dedicated `Salesperson Portal` Workspace.
  - Dedicated `Warehouse Operations` Workspace.
- [x] Match ERPNext Desk UI/UX design language exactly:
  - Frappe Navbar with App Switcher (`Clothing ERP`, `ERPNext`, `Frappe`).
  - Search bar (`Ctrl + K`), Notifications, User Avatar menu.
  - Desk sidebar with Workspaces list.
  - Number Cards (Today's Orders, Monthly Sales, Active Retailers, Pending Picking).
  - Quick action shortcuts and card sections.
  - Responsive mobile-first layout.
- [x] Implement Salesperson operational interface foundation:
  - Dashboard with orders, sales, assigned retailers, follow-ups.
  - Quick actions for ordering, catalog, and visit logging.
- [x] Implement Warehouse Operator operational interface foundation:
  - Dashboard with assigned pick lists, packing queue, dispatch readiness.
  - Barcode scanning foundation.
- [x] Add server-side APIs for user context, role switching, and operational metrics.
- [x] Write automated tests for roles, authorization checks, and interface endpoints (`test_roles.py`, `test_operational_interfaces.py`).
- [x] Update documentation and commit changes locally.

---

### Stage 3 — Salesperson Catalogue [ ] PENDING
**Acceptance Criterion:** Salespeople can browse existing ERPNext clothing products and select variants.
- [ ] Query standard ERPNext `Item` and `Item Variant` records.
- [ ] Clothing custom fields: Style code, Collection, Fabric, Fit, Season.
- [ ] Product images and thumbnail gallery.
- [ ] Size-Colour variant matrix (e.g. Size on X-axis, Colour on Y-axis).
- [ ] Stock availability display from specified warehouses.
- [ ] Customer-specific wholesale price lists lookup.
- [ ] Filters: Category, Brand, Size, Colour, Fit.
- [ ] Mobile-optimized product card and matrix modal.
- [ ] Automated tests for variant querying, stock lookup, and pricing permissions.

---

### Stage 4 — Retailer Management [ ] PENDING
**Acceptance Criterion:** Approved registrations become valid ERPNext Customers.
- [ ] Retailer directory for assigned salesperson (`Customer` doctype).
- [ ] Simplified retailer registration form (Shop name, contact, phone, GSTIN, territory).
- [ ] Duplicate detection logic (phone, email, GSTIN).
- [ ] Multi-tier approval flow (Pending -> Approved by Sales Manager).
- [ ] Automatic creation/linking of ERPNext `Customer` on approval.
- [ ] Retailer Visit tracking (Date, notes, follow-up date).
- [ ] Salesperson-to-customer assignment restrictions.
- [ ] Automated tests for registration, approval, and duplicate prevention.

---

### Stage 5 — Salesperson Ordering [ ] PENDING
**Acceptance Criterion:** Salespeople can create valid ERPNext Sales Orders using the custom UI.
- [ ] Shopping cart with size-colour matrix quantities.
- [ ] Server-side price recalculation and pricing rule validation.
- [ ] Stock reservation and availability check before submission.
- [ ] Credit policy and discount limit validation.
- [ ] Convert submitted request into standard ERPNext `Sales Order`.
- [ ] Idempotent submission to prevent duplicate orders.
- [ ] Order tracking statuses (Requested, Awaiting Approval, Confirmed, Picking, Packing, Dispatched, Delivered).
- [ ] Automated tests for cart operations, pricing validation, concurrency, and sales order creation.

---

### Stage 6 — Warehouse Operations [ ] PENDING
**Acceptance Criterion:** An order can be picked, packed, and dispatched while ERPNext maintains correct stock records.
- [ ] Warehouse Operator Dashboard showing assigned `Pick List`s.
- [ ] Barcode scanning and SKU verification interface.
- [ ] Quantity verification and shortage reporting.
- [ ] Packing session management and box/package count.
- [ ] Dispatch confirmation with carrier and tracking reference.
- [ ] Automatic generation of ERPNext `Delivery Note` and stock ledger updates.
- [ ] Handling of stock exceptions, damaged goods, and partial deliveries.
- [ ] Automated tests for picking, packing, dispatch, and delivery note generation.

---

### Stage 7 — Retailer-Direct Orders [ ] PENDING
**Acceptance Criterion:** Retailer requests can enter the same standard order workflow.
- [ ] Secure request intake portal via tokenized link or OTP verification.
- [ ] Retailer catalog browsing with retail pricing.
- [ ] Request submission into `Clothing Order Request` (no direct unapproved sales order).
- [ ] Manager approval workflow to convert request into ERPNext `Sales Order`.
- [ ] Instant acknowledgement reference and status tracking.
- [ ] Rate limiting and security controls.
- [ ] Automated tests for token authentication, intake, and conversion.

---

### Stage 8 — Notifications and Operational Improvements [ ] PENDING
**Acceptance Criterion:** Authorized users receive correct updates and can track the order lifecycle.
- [ ] Frappe real-time event publishing on order status transitions.
- [ ] Warehouse task assignment alerts.
- [ ] Out-of-stock and shortage notifications.
- [ ] Reconnection handling and state refresh.
- [ ] Role-specific operational summaries and performance metrics.
- [ ] Automated tests for event emission and subscriber authorization.

---

### Stage 9 — Security and Integration Testing [ ] PENDING
**Acceptance Criterion:** Critical business workflows pass documented tests.
- [ ] Comprehensive permission matrix audit.
- [ ] Concurrency testing for simultaneous stock deductions.
- [ ] Unauthorized direct URL and API access tests.
- [ ] Multi-user end-to-end integration test (Salesperson -> Manager -> Warehouse).
- [ ] Database migration rollback verification.
- [ ] Data sanitization verification (no secrets in source).

---

### Stage 10 — GitHub Release System [ ] PENDING
**Acceptance Criterion:** A tested release can be installed on a clean server.
- [ ] Semantic versioning configuration (`v0.2.0`, etc.).
- [ ] GitHub Actions CI workflows for test execution and linting.
- [ ] Docker image packaging and publishing to GitHub Container Registry.
- [ ] Release manifest with pinned dependencies.
- [ ] Release documentation and changelog.

---

### Stage 11 — Proxmox LXC Installer [ ] PENDING
**Acceptance Criterion:** A clean supported Proxmox host can install Clothing ERP using a documented helper-style script.
- [ ] Helper-style Bash installer (`install-clothing-erp-lxc.sh`).
- [ ] Preflight system checks (CPU, RAM, storage, network).
- [ ] Unprivileged Debian LXC container creation.
- [ ] Automated runtime configuration (MariaDB, Redis, Frappe Bench).
- [ ] Site initialization, persistent volumes, and health verification.

---

### Stage 12 — Update and Maintenance System [ ] PENDING
**Acceptance Criterion:** A previously installed version can be upgraded to a tested newer release with documented recovery steps.
- [ ] Update utility script (`clothing-erp update`).
- [ ] Automated database and files backup before migration.
- [ ] Release package verification and schema migration.
- [ ] Rollback procedures and disaster recovery guide.
