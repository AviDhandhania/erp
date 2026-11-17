# Independent source, one installed system

```mermaid
flowchart LR
  A[Clothing ERP repository] --> C[Tested GitHub release]
  B[Unmodified upstream app tags] --> C
  C --> D[Manifest with exact commits and runtimes]
  D --> E[New Proxmox LXC]
  D --> F[clothing-erp update]
  E --> G[nginx: HTTPS 443 / HTTP 80 redirect]
  G --> H[Native Desk login & app launcher]
  H --> I[ERPNext]
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

1. **`sales_erp` (Field Sales & Distribution)**:
   - Authoritative Sales DocTypes: `ASM Supervision` (Sales Territory Assignment), `Retailer Application`, `Retailer Visit`, `RSM Visit Obligation`, `Retailer Credit Limit Request`, `Retailer Assignment History`, `Clothing Product Image`.
   - Authoritative services: Territory-based order placement, catalogue matrices, product gallery lifecycle and sweeps, credit limit approval workflow with live customer limit validation, 80-day RSM visit cadence & obligations.
2. **`warehouse_erp` (Fulfilment & Warehouse Operations)**:
   - Authoritative services: Scan verification, Pick List shortage resolution, Pick List completion, Delivery Note validation, nested warehouse tree scoping, and Serial and Batch Bundle row locking.
   - Canonical roles: `Clothing Warehouse Manager` (mutation authority), `Clothing Business Administrator` (global oversight), with audited migration path for legacy operator accounts.
3. **`quality_erp` (Supplier Quality & Returns Quarantine)**:
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
Each bench owns all suite app checkouts (`sales_erp`, `warehouse_erp`, `quality_erp`), upstream apps, Python environment, Node runtime and built
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

---

### Mobile Architecture & Multi-Target Foundation

The mobile suite is organized as an independent Dart/Flutter monorepo located in `mobile/`, managed with Melos:

```mermaid
flowchart TD
    Core["mobile/packages/core (Auth, Network, SQLCipher, Scanner, Queue)"]
    Design["mobile/packages/design_system (Tokens, Themes, Components)"]

    Core --> Sales["mobile/apps/sales_app (com.clothingerp.sales)"]
    Design --> Sales

    Core --> Warehouse["mobile/apps/warehouse_app (com.clothingerp.warehouse)"]
    Design --> Warehouse

    Core --> Quality["mobile/apps/quality_app (com.clothingerp.quality)"]
    Design --> Quality

    Sales -->|"OAuth2 PKCE / HTTPS"| Backend["ERPNext / Clothing ERP API"]
    Warehouse -->|"OAuth2 PKCE / HTTPS"| Backend
    Quality -->|"OAuth2 PKCE / HTTPS"| Backend
```

1. **Target Separation & Minimum Versions**:
   - **Clothing Sales Mobile** (`com.clothingerp.sales`): Dedicated to Area Sales Managers (ASM) and Regional Sales Managers (RSM).
   - **Clothing Warehouse Mobile** (`com.clothingerp.warehouse`): Dedicated to Warehouse Managers and fulfillment operators.
   - **Clothing Quality Mobile** (`com.clothingerp.quality`): Dedicated to Quality Inspectors and Quality Managers.
   - Minimum Supported Platforms: Android SDK 28 (Android 9.0+) and iOS 15.0+.

2. **Security & Cryptography Doctrine**:
   - **OAuth 2.0 with PKCE (RFC 7636)**: Uses SHA-256 code challenge and high-entropy verifier; zero user passwords or Administrator secrets stored on client devices.
   - **Hardware-Backed Secure Storage**: Refresh tokens and database encryption keys stored exclusively in Apple Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`) and Android Keystore (`EncryptedSharedPreferences` with AES-256 GCM).
   - **Encrypted Local Storage (SQLCipher)**: Full local database encrypted with AES-256 using keys derived from hardware secure storage. Complete cryptographic wipe upon logout or remote revocation.
   - **Strict TLS & Hostname Validation**: All network traffic requires HTTPS with strict hostname matching and certificate verification. Zero "trust-all-certificates" bypasses allowed.

3. **Offline Queue & Concurrency Model**:
   - Mutations are enqueued into an encrypted local queue with client-generated UUID v4 idempotency keys.
   - Server state and business permissions are strictly revalidated on sync; offline queue state never authorizes transactions.
   - Business conflicts (e.g. concurrency changes, expired batches, over-picks) transition items to `conflict` state, halting retries until explicit user resolution.

4. **Hardware Scanner & Peripheral Subsystem**:
   - Keyboard-wedge listener detects rapid character pulses (<50ms inter-character interval).
   - OEM broadcast intent binding for rugged warehouse handhelds (Zebra DataWedge, Honeywell Mobility Edge).
   - Camera barcode scanner with torch/flashlight control and multi-sensory feedback (synth audio, haptic vibration, visual status colors).
   - Safe photo intake with client-side EXIF/GPS stripping, 2MB size bounding, and SHA-256 cryptographic hashing.
