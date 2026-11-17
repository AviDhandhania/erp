# Security Threat Model — Clothing ERP Suite

## 1. System Overview & Architecture

The Clothing ERP Suite consists of three dedicated, modular applications installed on a unified Frappe / ERPNext framework instance:
- `sales_erp`: Field sales management, Territory-based ASM/RSM hierarchy, retailer onboarding, catalogue browsing, sales ordering, and visit/collection cadence tracking.
- `warehouse_erp`: Warehouse fulfillment, barcode-based picking and packing verification, Pick List shortage resolution, delivery dispatch, and customer return quarantine intake.
- `quality_erp`: Sequential 7-stage supplier quality lifecycle (Fit Sample through Final Inspection), gate approvals, and return quarantine defect inspection.

The system serves three primary user interfaces:
1. Browser Desk Interface (Sales ASMs, RSMs, Warehouse Managers, Quality Inspectors/Managers, Administrators).
2. Mobile Applications (Clothing Sales Mobile, Clothing Warehouse Mobile, Clothing Quality Mobile).
3. Automated Integration Services (Cron schedulers, Celery background workers, MariaDB, Redis, and Insights).

---

## 2. Data Flow Diagram (DFD)

The following diagram illustrates data flows, system boundaries, and trust transitions across the entire Clothing ERP environment:

```mermaid
flowchart TD
    subgraph Untrusted_External["Untrusted External Boundary"]
        Browser["Desk Web Browser (HTTPS)"]
        MobileApp["Mobile Apps (Sales / Warehouse / Quality)"]
        ExternalAttacker["External / LAN Attacker"]
    end

    subgraph DMZ_Ingress["Ingress & Edge Proxy Boundary"]
        Nginx["Reverse Proxy (nginx / TLS Termination)"]
    end

    subgraph Application_Tier["Application Tier (Frappe Framework / Python WSGI)"]
        Gunicorn["Gunicorn WSGI Workers"]
        DeskRouter["Desk Router & Session Manager"]
        WhitelistAPI["Whitelisted REST APIs (@frappe.whitelist)"]
        DocControllers["Document Controllers & DocEvents"]
        CeleryWorker["Background Workers (Celery / RQ)"]
    end

    subgraph State_Storage["State & Storage Tier"]
        MariaDB[("MariaDB (Relational State / InnoDB)")]
        RedisCache[("Redis Cache (Sessions & App Cache)")]
        RedisQueue[("Redis Queue (Background Job Broker)")]
        PrivateFiles[("Private File System (/private/files)")]
        PublicFiles[("Public File System (/public/files)")]
    end

    subgraph Management_Reporting["Management & Outbound Boundary"]
        Insights[("Frappe Insights / Analytics")]
        OutboundSMTP["Email / Notification Gateway (SMTP)"]
        BackupStorage[("Encrypted Off-site Backup Storage")]
    end

    Browser -->|HTTPS / WSS| Nginx
    MobileApp -->|HTTPS REST / Token| Nginx
    ExternalAttacker -.->|Port Scanning / Exploits| Nginx

    Nginx -->|HTTP Reverse Proxy (Unix Socket / Loopback)| Gunicorn
    Gunicorn --> DeskRouter
    Gunicorn --> WhitelistAPI
    WhitelistAPI --> DocControllers

    DocControllers -->|TCP / UNIX Socket (Parameterized SQL)| MariaDB
    DocControllers -->|UNIX Socket| RedisCache
    DocControllers -->|Enqueue Tasks| RedisQueue
    DocControllers -->|Encrypted / Restricted IO| PrivateFiles
    DocControllers -->|Public IO| PublicFiles

    RedisQueue --> CeleryWorker
    CeleryWorker -->|Process & Mutate| MariaDB
    CeleryWorker -->|Send Notifications| OutboundSMTP

    MariaDB -.->|Read Replica / Read-Only User| Insights
    MariaDB -.->|mysqldump / Mariabackup + GPG| BackupStorage
    PrivateFiles -.->|Encrypted Sync| BackupStorage
```

---

## 3. Trust Boundaries

| Boundary ID | Description | Security Controls Across Boundary |
|---|---|---|
| **TB-1: Client to Edge** | Between end-user devices (desktop browsers, mobile phones) and Nginx reverse proxy. | Modern TLS (TLS 1.2/1.3), HSTS, HTTPS redirect, secure cookies (`Secure`, `HttpOnly`, `SameSite=Lax`), CSRF tokens. |
| **TB-2: Edge to App Server** | Between Nginx and Frappe WSGI processes (Gunicorn). | Local socket/loopback only, host header validation, request size limits, proxy header sanitization (`X-Forwarded-For`). |
| **TB-3: App to Database** | Between Python application layer and MariaDB. | Parameterized queries exclusively, row-level locking (`SELECT ... FOR UPDATE`), least-privilege DB user, local unix socket/loopback binding. |
| **TB-4: App to Caches/Queues**| Between Python application layer and Redis/Valkey instances. | Bound to localhost/Unix socket, password authentication, separate Redis DB instances for cache, queue, and socket. |
| **TB-5: File System Storage** | Between application workers and the host filesystem. | Private files stored outside document root (`/private/files`), authenticated stream through `/api/method/frappe.utils.file_manager.download_file`, Unix file permissions (0640/0750). |
| **TB-6: Backup & Disaster Recovery** | Between host container and external backup storage. | Client-side GPG encryption before transmission, isolated write-only credentials, separated key management. |
| **TB-7: Cross-Role & Scope** | Between different business actors sharing the same database. | Mandatory server-side authorization: Sales Territory scoping, Warehouse permissions, Supplier scoping, and role-based DocPerms. |

---

## 4. Threat Actor Profiles & Attack Vectors

### 4.1 Internet / LAN Attackers
- **Profile**: External unauthenticated adversaries targeting public endpoints, open ports, or network broadcasts.
- **Vectors**: Network port probing, DDoS/resource exhaustion, brute-force login attempts, TLS interception/downgrade, exploitation of unpatched dependencies, SQL injection, and path traversal.
- **Mitigations**:
  - Expose only TCP 443 (HTTPS) and TCP 80 (HTTP redirect to HTTPS); MariaDB (3306) and Redis (6379, 11000, 12000, 13000) bound strictly to `127.0.0.1` or unix domain sockets.
  - Fail2ban / rate-limiting on login and authentication endpoints.
  - Mandatory TLS 1.2+ with modern cipher suites.
  - AST-verified SQL query parameterization preventing SQL injection.

### 4.2 Malicious or Compromised Sales Accounts (ASM / RSM)
- **Profile**: An Area Sales Manager or Regional Sales Manager attempting to inspect competitors' retail data, access unassigned territories, manipulate pricing, or fabricate orders.
- **Vectors**: IDOR (Insecure Direct Object Reference) on customer or order IDs, modifying HTML hidden inputs, bypassing territory filters by direct API invocation, tampering with visit logs.
- **Mitigations**:
  - Server-side scope enforcement (`get_effective_sales_territory_names`): All queries filter by assigned leaf territories; UI hiding is never trusted.
  - Territory User Permission mirrors maintained automatically on every supervision assignment.
  - Pricing logic enforced by native ERPNext controllers (`Pricing Rule`, `Item Price`); direct rate overrides rejected.
  - Row locking on order creation and visit submission.

### 4.3 Malicious or Compromised Warehouse Accounts (Warehouse Manager / Legacy Operator)
- **Profile**: A warehouse worker attempting to alter inventory counts, divert dispatches, tamper with billing amounts, or access unauthorized stock locations.
- **Vectors**: Manipulating Pick List verification quantities, forging serial/batch numbers, executing arbitrary warehouse transfers, approving billing invoices without commercial authority.
- **Mitigations**:
  - Manager-only access model: Migration and retirement of `Clothing Warehouse Operator` role.
  - Warehouse scoping via native `User Permission` for ERPNext `Warehouse`.
  - Row-locked bundle allocation (`SELECT ... FOR UPDATE` on `Serial and Batch Bundle`).
  - Strict separation of duties: Warehouse Managers cannot submit or amend commercial invoices or alter accounting ledgers.

### 4.4 Malicious or Compromised Quality Accounts (Inspector / Manager)
- **Profile**: Quality personnel attempting to bypass mandatory inspection stages, forge sample inspection approvals, falsify measurements, or delete negative defect records.
- **Vectors**: Direct calls to `approve_quality_gate` without completing prerequisite stages, skipping 4. Production Go Ahead, tampering with return quarantine records.
- **Mitigations**:
  - Strict 7-stage sequential quality validation enforced in Python controller: Fit Sample $\rightarrow$ Refit Sample $\rightarrow$ Size Set $\rightarrow$ Production Go Ahead $\rightarrow$ Inline Visits $\rightarrow$ Mid-line Visits $\rightarrow$ Final Inspection.
  - Critical gates (Production Go Ahead and Final Inspection) require Administrator privilege.
  - Immutable revision logs: Superseded reports are marked read-only with explicit `supersedes` pointers.

### 4.5 Lost Mobile Devices / Stolen Session Tokens
- **Profile**: A field salesperson or warehouse manager whose smartphone is lost, stolen, or compromised via malware.
- **Vectors**: Extraction of access tokens or cached customer data from local device storage, session replay attacks, offline submission replay.
- **Mitigations**:
  - Tokens stored exclusively in iOS Keychain / Android Keystore hardware-backed secure storage.
  - Short-lived access tokens with server-side revocation capability.
  - Explicit device logout and administrator session termination (`clear_user_sessions`).
  - Encrypted local offline databases wiped upon remote revocation or excessive failed unlock attempts.
  - Offline queue submissions require UUID idempotency keys and undergo full server-side permission revalidation upon sync.

### 4.6 Malicious Uploads & Polyglot Files
- **Profile**: An adversary uploading executable scripts, webshells, or malformed media masquerading as retailer shop photos or garment defect evidence.
- **Vectors**: Polyglot JPEG/PHP files, SVG files containing stored XSS payloads, zip bombs, directory traversal via filename (`../../var/www/shell.php`).
- **Mitigations**:
  - Private storage by default for all business evidence (`/private/files`).
  - Strict MIME-type sniffing, extension whitelisting (disallow SVG/HTML/PHP/executable extensions for image fields), and file signature validation.
  - Server-side filename sanitization and randomization.
  - Dimension and size limits on image uploads to prevent memory-exhaustion DoS.

### 4.7 Dependency & Supply-Chain Compromise
- **Profile**: Compromised upstream PyPI, npm, or GitHub packages introducing backdoors or data exfiltration routines.
- **Vectors**: Typosquatting packages, compromised maintainer credentials, tampering with release tarballs during distribution.
- **Mitigations**:
  - Absolute pin of all dependencies (Frappe v16.55.2, ERPNext v16.54.0, India Compliance v16.10.0, Insights v3.15.1, Python 3.14.9, Node 24.22.2).
  - SHA256 checksum verification and Sigstore provenance attestations on release artifacts.
  - Third-party GitHub Actions pinned to immutable full commit SHAs, never mutable tags.
  - Automated Software Bill of Materials (SBOM) generation.

### 4.8 Backup Theft & Disaster Recovery Compromise
- **Profile**: An attacker intercepting database dumps in transit or gaining read access to off-site backup storage.
- **Vectors**: Unencrypted database dumps containing plaintext customer PII, GSTINs, financial ledgers, and password hashes; backup key co-location.
- **Mitigations**:
  - Client-side GPG encryption of all MariaDB dumps and private files prior to off-site upload.
  - Off-site backup destination credentials possess write-only permissions.
  - Backup decryption keys stored strictly out-of-band and never co-located with backup archives.
  - Routine automated restore drills in isolated sandboxes to verify integrity without production exposure.

### 4.9 Database & Host Compromise (LXC / Systemd)
- **Profile**: Lateral movement from a compromised container service to the underlying host or database.
- **Vectors**: Container escape, privilege escalation via systemd unit misconfiguration, world-readable configuration files.
- **Mitigations**:
  - Unprivileged LXC container configuration without Docker nesting unless strictly isolated.
  - Systemd service hardening: `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`.
  - MariaDB socket permissions restricted (0750); site configuration files (`site_config.json`) set to mode 0600 owned by `frappe:frappe`.

---

## 5. Security Threat Summary Matrix

| Threat Category | Likelihood | Impact | Primary Mitigations |
|---|---|---|---|
| Cross-Territory Sales Data Leak | Medium | High | Leaf Territory scoping in Python, User Permission mirrors, AST-validated queries. |
| Unauthorized Quality Gate Approval | Low | Critical | Hard gate sequence check, Administrator requirement on PGA & Final Inspection. |
| Insecure File Upload / Shell Upload | Medium | Critical | Private file directory, extension whitelisting, MIME signature checking, server-side rename. |
| Stolen Mobile Device / Token Replay | High | Medium | Hardware Keystore/Keychain, short-lived tokens, server revocation, encrypted offline DB. |
| Raw SQL Injection | Low | Critical | 100% Parameterized queries via `%s` / tuple binding; static AST test enforcement. |
| Supply Chain / Tampered Artifact | Low | Critical | Immutable action commit SHAs, SBOM, Sigstore publisher provenance verification. |
| Production Plaintext HTTP Sniffing | High | Critical | Mandatory HTTPS redirect, HSTS, secure cookie flags, disable plaintext admin credential display. |
