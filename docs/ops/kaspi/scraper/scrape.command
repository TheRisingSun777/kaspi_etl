#!/bin/bash
set -Eeuo pipefail

SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR/../../../../"

INPUT_DIR="docs/ops/kaspi/scraper/input"
RESULT_DIR="docs/ops/kaspi/scraper/result"
LOG_DIR="data_raw/perfumes/logs"
STATE_FILE="$RESULT_DIR/scrape_state.json"

if [[ $# -gt 0 ]]; then
  INPUT_FILE="$1"
else
  INPUT_FILE="$(ls -t "$INPUT_DIR"/*.xlsx 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${INPUT_FILE}" ]]; then
  echo "No .xlsx found in $INPUT_DIR. Drop a workbook there and rerun."
  exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Input file $INPUT_FILE was not found."
  exit 1
fi

mkdir -p "$RESULT_DIR" "$LOG_DIR"

SCRAPE_DATE="$(date +%d.%m.%Y)"
BASENAME="scrape_result_${SCRAPE_DATE}"
CSV_PATH="$RESULT_DIR/${BASENAME}.csv"
XLSX_PATH="$RESULT_DIR/${BASENAME}.xlsx"

rm -f "$CSV_PATH" "$XLSX_PATH" "$STATE_FILE"

echo "Using input workbook: $INPUT_FILE"
printf '\nStarting scrape...\n' 

npx tsx scripts/scrape_kaspi_offers.ts \
  --input "$INPUT_FILE" \
  --city 710000000 \
  --concurrency 150 \
  --out "$CSV_PATH" \
  --state "$STATE_FILE"

export CSV_PATH XLSX_PATH
python3 - <<'PY'
import os
import pandas as pd
from pathlib import Path

csv_path = Path(os.environ['CSV_PATH'])
xlsx_path = Path(os.environ['XLSX_PATH'])

if not csv_path.exists():
    raise SystemExit(f"CSV not found: {csv_path}")

df = pd.read_csv(csv_path)
df.to_excel(xlsx_path, index=False)
print(f"Converted {csv_path} -> {xlsx_path}")
PY

rm -f "$CSV_PATH"

printf '\nDone → %s\n' "$XLSX_PATH"
