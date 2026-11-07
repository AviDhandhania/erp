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
   - Respect the current stage boundaries. Implement only the business workflows authorized in the current user request; deployment and foundation repair do not imply completion of later apparel features.

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

Deployment pins live in `deploy/versions.env`: Frappe v16.55.2, ERPNext v16.54.0,
Python 3.14.9, Node 24.22.2, Bench 5.31.1, Debian 13 MariaDB/Redis packages.
Never assume the earlier Python 3.11/Node 18 requirements apply to v16.
The existing local bench has an ERPNext develop checkout; do not downgrade a site's
schema to match release pins. Use an isolated new site/bench for release validation.

The canonical roadmap is this repository's `work.md`. Completed launch/role
foundations are not completion of catalogue, ordering or warehouse workflows.

---

## 4. Verification Checklist Before Finishing Any Task

- [ ] All new files belong strictly to `clothing_erp`.
- [ ] Upstream `erpnext` and `frappe` repositories remain untouched (`git status` is clean).
- [ ] Standalone unit tests pass (`python -m unittest discover -s clothing_erp/tests` (using a Frappe-capable Python environment)).
- [ ] Site tests pass (`bench --site <site-name> run-tests --app clothing_erp --test-category all`).
- [ ] The native launcher and app workspace render properly in the browser.
- [ ] No secrets or temporary credentials committed.

Deployment work also requires `python -m unittest discover -s deploy/tests -v`, shell syntax checks, and ShellCheck. Mocked host-command tests do not replace an actual Proxmox installation trial.

## 5. Release and lifecycle rules

- Production consumes published stable release artifacts, not arbitrary main/develop checkouts.
- Keep Clothing ERP source independent; upstream version pins are declarative release inputs.
- A release includes exact upstream commits, checksums and a schema-validated manifest.
- Build a separate environment before stopping the live site; never change active dependencies in place.
- Quiesce writers and record a verified database/config/file recovery point before migration.
- Recovery before activation restores code and data together. After background writers are released,
  repair the activated release; do not automatically discard their new writes.
- Test fault recovery and fresh database-backed installs before publishing a stable release.
- Never claim mocked Proxmox tests constitute a real host installation/update/reboot trial.
