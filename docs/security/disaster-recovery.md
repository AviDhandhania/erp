# Disaster Recovery, Encrypted Backups and Restore Verification Plan

This document establishes the Disaster Recovery (DR) architecture, encrypted off-host backup pipeline, restore verification drills, and incident recovery runbooks for the Clothing ERP Suite.

---

## 1. Objectives & Metrics

| Metric | Target | Description |
| --- | --- | --- |
| **Recovery Point Objective (RPO)** | **$\le$ 1 hour** | Maximum acceptable data loss window. Supported by scheduled backups and transaction logging. |
| **Recovery Time Objective (RTO)** | **$\le$ 30 minutes** | Maximum allowable downtime from disaster declaration to restored user traffic. |
| **Integrity Target** | **100% authenticated** | Every backup artifact is encrypted and authenticated with AES-256-GCM / HMAC tags. |
| **Test Verification Frequency** | **Weekly automated drill** | Periodic automated restore drills into an isolated environment without production impact. |

---

## 2. Backup Architecture & Data Scope

A complete Clothing ERP recovery point encompasses all five required tiers:

```
Backup Bundle (clothing-encrypted-backup-YYYYMMDDTHHMMSSZ/)
├── database.sql.gz.enc      # Consistent MariaDB mysqldump with InnoDB table schemas & rows
├── files.tar.gz.enc         # All public/files and private/files attachments
├── site_config.json.enc     # Site config, DB credentials, and Frappe symmetric encryption_key
├── redis.rdb.enc            # Background worker queue state and pending job descriptors
└── encrypted_manifest.json  # Unencrypted metadata: timestamp, key_id, artifact checksums (NO KEYS)
```

### 2.1 Quiescence & Data Consistency
- Backups execute with workers quiesced and HTTP frontend returning `503 Service Unavailable` (`maintenance: 1`).
- Eliminates race conditions, partial table writes, and orphaned file attachments.
- Services resume immediately upon completion of local snapshot capture (typically under 10 seconds).

---

## 3. Cryptographic Protection & Key Segregation

### 3.1 Encryption at Rest
- All backup artifacts are encrypted using **AES-256-GCM** (Galois/Counter Mode) with 256-bit cryptographically random keys and 96-bit unique nonces per artifact, or OpenSSL PBKDF2 authenticated AES-256-CBC.
- GCM authentication tags guarantee that any bit flip, disk corruption, or malicious tampering is detected before decompression or restore.

### 3.2 Strict Key Segregation
> [!CRITICAL]
> The backup encryption key must **NEVER** be stored in the backup directory, inside the backup archive, or uploaded to the off-host backup destination.

Key distribution channels:
1. **Host Segregation**: Stored at `/etc/clothing-erp/backup.key` with permissions `0400` owned strictly by `root`.
2. **Environment Variable**: Supplied via `CLOTHING_BACKUP_KEY` in secure automation pipelines.
3. **Key Identification (`key_id`)**: The `encrypted_manifest.json` records only a 16-character SHA-256 fingerprint of the key (`key_id`). Operators can determine which key was used to encrypt the archive without exposing key material.

---

## 4. Off-Host Replication & Retention Tiers

Local snapshots alone do not constitute disaster recovery. If a Proxmox host or local storage pool fails, local snapshots are lost.

### 4.1 Off-Host Storage Targets
- Encrypted bundles are replicated immediately to off-host destinations:
  - **Proxmox Backup Server (PBS)**: Dedicated deduplicating backup datastore.
  - **Remote SFTP / SSH Target**: Segregated backup storage server.
  - **S3-Compatible Object Store**: Immutably locked bucket with Object Lock / Compliance Mode.

### 4.2 Retention Policy
The lifecycle manager enforces automated pruning according to legal, tax, and operational requirements:

| Tier | Retention Period | Description |
| --- | --- | --- |
| **Daily** | **7 days** | Hourly / daily recovery points for rapid operational rollback. |
| **Weekly** | **4 weeks** | Weekly snapshots taken every Sunday at 02:00 container time. |
| **Monthly** | **12 months** | End-of-month snapshots retained for fiscal year reconciliation. |
| **Annual** | **7 years** | Fiscal year-end snapshots retained for GST / statutory compliance. |

Pruning uses secure deletion: old directories are purged only after verifying that a newer valid generation exists.

---

## 5. Automated Isolated Restore Verification Drills

Disaster recovery readiness requires proving that backups can be restored successfully.

The automated drill tool (`deploy/release/encrypted_backup.py` and `clothing-erp drill`):
1. **Key Verification**: Compares the supplied key's fingerprint against `manifest.key_id`.
2. **Decryption**: Decrypts artifacts into a temporary scratch directory (`/tmp/isolated-drill-XXXXXXXX/`).
3. **Integrity Validation**:
   - Decompresses `database.sql.gz` and verifies `CREATE TABLE` and InnoDB structure statements.
   - Inspects `files.tar.gz` and rejects any symlinks or directory traversal elements.
   - Parses `site_config.json` and verifies the presence of `encryption_key`.
4. **Isolated DB Test**: Restores the database into an isolated temporary schema (e.g. `test_dr_drill`) to verify zero database errors.
5. **Secure Cleanup**: Wipes temporary plaintext directories immediately upon drill completion.

### Verification Command:
```bash
# Run isolated drill inside the container
python3 -c '
from deploy.release.encrypted_backup import verify_isolated_restore
results = verify_isolated_restore("/var/lib/clothing-erp/encrypted_backups/clothing-encrypted-backup-20261117T180000Z", key="...")
print("Status:", results["status"])
'
```

---

## 6. Restore Authorization Matrix

A production database restoration alters commercial records, inventory balances, and tax filings. Restoration must be formally authorized:

| Role | Authorize Pre-Update Rollback | Authorize Full Disaster Restore | Authorize Key Rotation |
| --- | :---: | :---: | :---: |
| **Administrator / Ops Lead** | Yes | Yes (with ticket) | Yes |
| **Clothing Business Administrator** | Yes | Yes | No |
| **Warehouse Manager** | No | No | No |
| **Quality Manager** | No | No | No |
| **External Attacker / Unverified User** | Denied | Denied | Denied |

---

## 7. Disaster Recovery Runbooks

### Runbook 1: Ransomware or Total Host Compromise
**Scenario**: The Proxmox host or container filesystem has been compromised, corrupted, or encrypted by ransomware.

1. **Containment**:
   - Immediately disconnect the compromised host/container network interface.
   - Do not attempt in-place repair on the compromised container.
2. **Provision Clean Infrastructure**:
   - Deploy a fresh Debian 13 LXC using `deploy/proxmox/install.sh` on trusted clean hardware.
3. **Retrieve Encryption Key**:
   - Retrieve the master backup key from the segregated offline password manager / hardware security module (HSM).
4. **Fetch Off-Host Backup**:
   - Download the latest encrypted backup bundle from the off-host PBS / S3 storage:
     ```bash
     scp backup-server:/backups/clothing-encrypted-backup-20261117T180000Z.tar /tmp/
     ```
5. **Decrypt and Restore**:
   - Run the restoration tool:
     ```bash
     python3 /opt/clothing-erp/manager/encrypted_backup.py restore /tmp/clothing-encrypted-backup-20261117T180000Z --key "$CLOTHING_BACKUP_KEY"
     ```
6. **Verify Services & Re-enable Traffic**:
   - Verify web frontend: `curl -k https://127.0.0.1/api/method/ping`
   - Check application desk login and confirm latest Sales Orders and Pick Lists.
   - Re-point DNS / router port forwarding to the new container IP.

---

### Runbook 2: Operator Error / Accidental Data Deletion
**Scenario**: An operator accidentally dropped a critical table or executed an unintended bulk deletion.

1. **Stop Writes Immediately**:
   - Enable HTTP maintenance gate to prevent new transactions:
     ```bash
     clothing-erp quiesce
     ```
2. **Snapshot Current Displaced State**:
   - Capture a dirty snapshot of the current database and attachments so that any valid subsequent orders can be extracted manually:
     ```bash
     clothing-erp backup --tag "pre-rollback-dirty"
     ```
3. **Restore Last Known Good Recovery Point**:
   - Identify the latest clean backup before the error:
     ```bash
     clothing-erp rollback --yes
     ```
4. **Resume Traffic**:
   - Re-enable services and verify desk access:
     ```bash
     clothing-erp resume
     ```
5. **Reconcile Gap Records**:
   - Inspect transactions from the dirty snapshot and re-enter or import any valid orders created between the backup and the incident.
