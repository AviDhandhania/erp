# Independent source, one installed system

```mermaid
flowchart LR
  A[Clothing ERP repository] --> C[Tested GitHub release]
  B[Unmodified upstream app tags] --> C
  C --> D[Manifest with exact commits and runtimes]
  D --> E[New Proxmox LXC]
  D --> F[clothing-erp update]
  E --> G[nginx: container IP on port 80]
  G --> H[Native login and app launcher]
  H --> I[ERPNext]
  H --> J[Clothing ERP Suite Launcher]
  H --> K[Sales ERP]
  H --> L[Warehouse ERP]
  H --> M[Quality ERP]
  H --> N[India Compliance]
  H --> O[Insights]
```

“Separate” means separate applications/repositories and independent upstream pins.
The apps share Frappe's authentication, database and standard business documents.
A second fake ERP service or duplicated stock/accounting database is not involved.

### Authoritative App and DocType Ownership

1. **`clothing_erp` (Suite Launcher & Home)**:
   - Canonical Desk entry point, workspace navigation, launcher tile scoping.
   - Product gallery asset management and orphan cleanup.
   - Compatibility forwarding for legacy endpoints.
2. **`sales_erp` (Field Sales & Distribution)**:
   - Authoritative Sales DocTypes: `ASM Supervision` (Sales Territory Assignment), `Retailer Application`, `Retailer Visit`, `RSM Visit Obligation`, `Retailer Credit Limit Request`, `Retailer Assignment History`, `Clothing Product Image`.
   - Authoritative services: Territory-based order placement, catalogue matrices, credit limit approval workflow with live customer limit validation, 80-day RSM visit cadence & obligations.
3. **`warehouse_erp` (Fulfilment & Warehouse Operations)**:
   - Authoritative services: Scan verification, Pick List shortage resolution, Pick List completion, Delivery Note validation, nested warehouse tree scoping, and Serial and Batch Bundle row locking.
   - Canonical roles: `Clothing Warehouse Manager` (mutation authority), `Clothing Business Administrator` (global oversight), with audited migration path for legacy operator accounts.
4. **`quality_erp` (Supplier Quality & Returns Quarantine)**:
   - Authoritative Quality DocTypes: `Supplier Quality Inspection`, `Return Quarantine`.
   - Authoritative services: 7-stage sequential quality lifecycle enforcement (Fit Sample $\rightarrow$ Refit Sample $\rightarrow$ Size Set $\rightarrow$ Production Go Ahead $\rightarrow$ Inline Visits $\rightarrow$ Mid-line Visits $\rightarrow$ Final Inspection), versioned inspection reports, and administrative review bundle retrieval.

Each published release contains an app source archive and `release.json` describing
its exact Clothing ERP source commit, ERPNext/Frappe/Insights/India Compliance
tag commits, Python, Node,
Bench and uv versions, plus checksummed runtime dependency locks. A source checksum and SHA256SUMS detect artifact corruption;
GitHub Actions also publishes provenance attestations. Normal installation uses
GitHub's HTTPS release-asset endpoints. Local clients do not currently verify the
Sigstore attestation; checksums alone are not an independent publisher signature.

The update manager prepares a new native bench under `/home/frappe/releases/`.
Each bench owns all five app checkouts, Python environment, Node runtime and built
assets. The common site files are shared; a single symlink selects the active bench.
Native systemd services and nginx use that stable symlink. Core updates therefore
need no merges into the clothing repository and no dependency replacement inside
an actively serving environment.

Migrations change the shared database. They run only with all application writers
stopped and the HTTP maintenance gate closed, after a database/config/file backup.
Before the activation commit point, failure restores the old database, attachments,
queue snapshot and code.
After frontend readiness is confirmed and the release is committed, background
writers are started; recovery after that point repairs the new services without
silently discarding their writes. Explicit rollback saves a new recovery point and
then restores the selected previous code/data/queue together.

This follows Frappe's rule that reverse schema migrations are unsupported:
[official migration documentation](https://docs.frappe.io/framework/user/en/database-migrations).
Proxmox uses the [native container toolkit](https://pve.proxmox.com/pve-docs/pct.1.html);
Docker nesting is not needed inside the LXC.
