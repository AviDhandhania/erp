#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${CLOTHING_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
cd "$ROOT/frappe-bench"
"$ROOT/bench" --site clothing.local run-tests --app sales_erp --test-category all
"$ROOT/bench" --site clothing.local run-tests --app warehouse_erp --test-category all
exec "$ROOT/bench" --site clothing.local run-tests --app quality_erp --test-category all
