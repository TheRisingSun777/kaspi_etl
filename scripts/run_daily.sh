#!/usr/bin/env bash
set -euo pipefail

# cd to repo root
cd "$(dirname "$0")/.."

# Activate venv
if [ -f "venv/bin/activate" ]; then
  . venv/bin/activate
fi

STAMP=$(date +%Y%m%d)
NOW=$(date '+%F %T')
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/daily_run_${STAMP}.log"

log() { echo "[$NOW] $*" | tee -a "$RUN_LOG"; }

log "Starting daily run"

# 1) Pull orders (best-effort)
if make orders; then
  log "Orders fetched via API"
else
  log "Orders fetch failed (continuing with cached JSON if present)"
fi

# 2) Stage orders CSV
./venv/bin/python scripts/api_orders_to_csv.py || log "Staging orders CSV: no cache or empty"

# 3) Join to processed sales and update stock
./venv/bin/python scripts/join_api_orders_to_sales.py || log "Join/stock update encountered an error"

# 4) Sizes and picklist
make size-recs || log "Size recs step failed (continuing)"
./venv/bin/python scripts/crm_build_picklist.py || log "Picklist step failed (continuing)"

# 5) Packing PDFs and zip
make pack-pdfs || log "Pack PDFs step failed (continuing)"
ZIP_OUT=$(make -s zip-exports || true)

# 6) Summary counts
PROC_CSV="data_crm/processed_sales_latest.csv"
PROCESSED_ROWS=0
if [ -f "$PROC_CSV" ]; then
  # subtract header
  PROCESSED_ROWS=$(($(wc -l < "$PROC_CSV") - 1))
fi
PACK_PDF_COUNT=$(ls data_crm/exports/pack_*.pdf 2>/dev/null | wc -l | tr -d ' ')
log "Processed rows: $PROCESSED_ROWS; Pack PDFs: $PACK_PDF_COUNT; Zip: ${ZIP_OUT##*$'\n'}"

log "Daily run finished"
