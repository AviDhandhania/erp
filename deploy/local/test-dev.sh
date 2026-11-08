#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${CLOTHING_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
cd "$ROOT/frappe-bench"
exec "$ROOT/bench" --site clothing.local run-tests --app clothing_erp --test-category all
