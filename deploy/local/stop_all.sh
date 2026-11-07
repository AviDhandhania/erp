#!/usr/bin/env bash
set -Eeuo pipefail
# The managed service owns only this project's processes; never pkill other benches.
if systemctl is-active --quiet clothing-erp-local; then
    exec sudo systemctl stop clothing-erp-http clothing-erp-local
fi
echo 'For a foreground ./scripts/start_all.sh session, press Ctrl+C in that terminal.'
echo 'Database and Redis are preserved. No other bench or system service was stopped.'
