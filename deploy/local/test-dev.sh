#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${CLOTHING_WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
"$ROOT/.venv/bin/python" -m unittest discover -s "$ROOT/clothing_erp/clothing_erp/tests" -v
cd "$ROOT/frappe-bench"
exec "$ROOT/bench" --site clothing.local run-tests --app clothing_erp --test-category all
