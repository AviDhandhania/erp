# AGENTS.md — Development Guidelines for AI Agents and Contributors

This document defines the strict operating boundaries and development rules for developing the `clothing_erp` application.

---

## 1. Absolute Operating Rules

1. **Zero Core Modifications**:
   - **NEVER** edit files in `apps/frappe` or `apps/erpnext` (or the upstream `erpnext` repository).
   - Any feature, override, or hook must reside completely inside the `clothing_erp` application.

2. **Repository Isolation**:
   - `clothing_erp` maintains its own Git repository and version history.
   - Do not commit `clothing_erp` code into upstream ERPNext or Frappe repositories.
   - Do not delete or overwrite existing repositories.

3. **Data Integrity & Fictional Data**:
   - Never use real customer, supplier, financial, or personal data.
   - All test records must be clearly fictitious (e.g., `test-retailer@example.invalid`).
   - Never commit API keys, passwords, or credentials into source control.

4. **Change Safety**:
   - Always ask the user before performing destructive changes or system-wide operations (e.g., package installation, system services, drop-database).

5. **Stage Scope Discipline**:
   - Respect the current stage boundaries. **Do not implement products, sales, inventory, or accounting business logic until Stage 2 is explicitly requested.**

---

## 2. Architecture & Design Principles

- **Leverage Native ERPNext DocTypes**:
  - Garment Variants $\rightarrow$ ERPNext `Item` with `Item Variant` (Attributes: Size, Color).
  - Retailer Accounts $\rightarrow$ ERPNext `Customer` (Customer Group: Retailer/Boutique).
  - Wholesale Orders $\rightarrow$ ERPNext `Sales Order`.
  - Stock Movements $\rightarrow$ ERPNext `Stock Entry` and `Delivery Note`.
  - Manufacturers / Mills $\rightarrow$ ERPNext `Supplier`.
  - Do not create redundant parallel ledgers or duplicate inventory registers.

- **Server-Side Enforcement**:
  - Permissions, pricing validations, and order state transitions must be verified in Python controllers using Frappe document hooks or DocEvents.
  - UI client scripts are strictly for usability, not security.

- **Proxmox LXC & Docker Parity**:
  - Avoid OS-specific host path dependencies.
  - Ensure all features, migrations, and assets install cleanly in containerized Debian/Alpine environments.

---

## 3. Technology Pins

| Component | Pinned Version | Branch |
| :--- | :--- | :--- |
| **Frappe Framework** | `v16.55.2` | `version-16` |
| **ERPNext** | `v16.54.0` | `version-16` |
| **Python** | `3.11` / `3.12` | — |
| **MariaDB** | `11.4` / `10.6` | LTS |
| **Redis** | `7.x` | Alpine |
| **Node.js** | `18.x` / `20.x` | LTS |

---

## 4. Verification Checklist Before Finishing Any Task

- [ ] All new files belong strictly to `clothing_erp`.
- [ ] Upstream `erpnext` and `frappe` repositories remain untouched (`git status` is clean).
- [ ] Standalone unit tests pass (`python -m unittest discover -s clothing_erp/tests`).
- [ ] Site tests pass (`bench --site <site-name> run-tests --app clothing_erp`).
- [ ] Homepage navigation placeholders render properly in the browser.
- [ ] No secrets or temporary credentials committed.
