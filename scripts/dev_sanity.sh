#!/usr/bin/env bash
set -euo pipefail

echo "Fill the two paths below, then run this script."
echo 'DELIVERY_XLSX="/path/to/KSP_Delivery_rates_V5.xlsx"'
echo 'OFFERS_XLSX="/path/to/Business_model_V3.xlsx"'
echo
cat <<'CMDS'
# After setting the env vars, run:
python3 backend/db/migrate.py --reset
python3 backend/ingest/inspect_xlsx.py "$DELIVERY_XLSX" --mode delivery
python3 backend/ingest/load_baseline.py
python3 backend/ingest/inspect_xlsx.py "$OFFERS_XLSX" --mode offers
python3 backend/ingest/load_offers.py
CMDS
