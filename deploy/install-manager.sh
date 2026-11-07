#!/usr/bin/env bash
# Install root-owned lifecycle commands; application users cannot replace these programs.
set -Eeuo pipefail
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install -d -m 755 /opt/clothing-erp/manager /var/lib/clothing-erp
install -m 644 "$SOURCE/deploy/release/common.py" "$SOURCE/deploy/release/lifecycle.py" /opt/clothing-erp/manager/
cat > /usr/local/bin/clothing-erp <<'COMMAND'
#!/usr/bin/env bash
set -Eeuo pipefail
exec /usr/bin/python3 /opt/clothing-erp/manager/lifecycle.py "$@"
COMMAND
chmod 755 /usr/local/bin/clothing-erp
clothing-erp register
cat > /etc/cron.d/clothing-erp-backup <<'CRON'
0 2 * * * root /usr/local/bin/clothing-erp backup >> /var/log/clothing-erp-backup.log 2>&1
CRON
