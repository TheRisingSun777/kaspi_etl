#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Activate venv
source venv/bin/activate

# Orders pipeline (best-effort if API unavailable)
make orders || true

# Ensure processed/join step
./venv/bin/python scripts/join_api_orders_to_sales.py

# Size recommendations
make size-recs

# Labels grouping if INPUT_LABELS provided
if [ -n "${INPUT_LABELS:-}" ]; then
  OUT_DATE_VALUE="${OUT_DATE:-$(date +%F)}"
  make group-labels INPUT="$INPUT_LABELS" OUT_DATE="$OUT_DATE_VALUE"
fi

# Build picklist (non-fatal)
./venv/bin/python scripts/crm_build_picklist.py || true

echo "run_e2e.sh completed"


