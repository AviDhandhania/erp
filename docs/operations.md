# Operator commands

Run as root **inside the production LXC**:

| Task | Command |
| --- | --- |
| Inspect installed components | `clothing-erp status` |
| Check a stable release | `clothing-erp check` |
| Update the supported stack | `clothing-erp update` |
| Select a published release | `clothing-erp update --version v0.3.1` |
| Enforce clothing-only component changes | `clothing-erp update --app-only` |
| Create a consistent recovery point | `clothing-erp backup` |
| Finish interrupted recovery/startup | `clothing-erp recover --yes` |
| Restore previous code and data | `clothing-erp rollback --yes` |

From the Proxmox host, prefix a command with `pct exec <CTID> --`.

## Persistent layout

| Path | Contents |
| --- | --- |
| `/home/frappe/frappe-bench` | Active bench symlink |
| `/home/frappe/releases/vX.Y.Z/bench` | Release code, Python environment and assets |
| `/home/frappe/releases/vX.Y.Z/.runtime` | Release Node/Python/Bench tools |
| `/home/frappe/shared/clothing.local` | Site config, public/private attachments and site files |
| `/var/lib/clothing-erp/state.json` | Root-owned current/previous release and interrupted-operation journal |
| `/var/lib/clothing-erp/backups/` | Root-only database, attachment/config backups with checksums |
| `/opt/clothing-erp/manager` | Root-owned update command implementation |
| `/root/clothing-erp-credentials` | Initial generated Administrator password |

Do not edit deployed app checkouts. Updates reject dirty Git working trees rather
than erase local changes. Extend the custom app and publish a new release instead.
The legacy installer is adopted on its first managed update: the old bench and
site data are moved into the retained release/shared layout; neither is discarded.
The developer workspace at `/home/avi/GitHub/erp` is intentionally unaffected.

## Backup and rollback

Updates take a recovery point before migration. A daily root cron job also creates
one at 02:00 container time. These are consistent backups: nginx returns HTTP 503
and application workers/services are stopped for the capture. The backup includes
a MariaDB SQL dump, public and private attachments, the site config containing
the encryption key, and a checked Redis RDB snapshot containing pending jobs. Checksums are checked before restore. The manager supports the
single installer-generated database only; it does not select arbitrary databases.

Keep an **off-container copy** of recovery points. The current implementation does
not delete old backups/releases automatically; monitor free space and archive old
unneeded generations after verifying off-container copies. At least one previous
bench and its matching recovery point must remain available for rollback.

A rollback restores the old database contents. It saves current data first, and
retains displaced attachments, but it does not merge post-upgrade orders into the
older database or undo externally sent emails/payments. Background services remain
stopped until the new frontend/database have passed readiness. If startup fails
after the commit point, `recover` retries the new services; it does not silently
rewind the database. Explicit `rollback --yes` is available if that release must be
reverted. Copy the preserved newer backup elsewhere before manual data recovery.

A failed restore leaves HTTP maintenance enabled and the recovery journal intact.
Resolve the underlying storage/DB issue, then run `clothing-erp recover --yes`.
Never clear maintenance or delete the operation journal merely to hide a failure.
Concurrent update/backup/rollback commands are rejected by a lock. An update killed
with SIGKILL can be recovered using that same journal.

## Diagnostics

```bash
journalctl -u clothing-erp-web -u clothing-erp-socketio
journalctl -u clothing-erp-worker -u clothing-erp-schedule
cat /var/log/clothing-erp-install.log
cat /var/log/clothing-erp-backup.log
```

nginx listens on port 80. MariaDB, Redis and gunicorn use loopback; realtime uses a
Unix socket behind nginx. Database passwords and encryption keys are never included
in releases or command arguments. PostgreSQL, external DB servers, multi-site
benches and external attachment storage are outside this native platform contract.

For a public hostname, configure HTTPS and the site's host_name using standard
nginx/Frappe administration. Debian OS updates and Proxmox host maintenance are
separate operator responsibilities; application recovery points do not roll back
OS package upgrades or the Proxmox host.
