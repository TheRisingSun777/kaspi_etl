#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_ROOT="${SCRIPT_DIR}"

IN="${KASPI_INPUT_DIR:-${IN:-${OPS_ROOT}/Kaspi_orders/input}}"
OUTBASE="${KASPI_OUTBASE_DIR:-${OUTBASE:-${OPS_ROOT}/Kaspi_orders}}"
RUN_DATE="${KASPI_RUN_DATE:-${RUN_DATE:-today}}"
ZIP_MODE="${KASPI_ZIP_MODE:-${ZIP_MODE:-one}}"
PYTHON_BIN="${KASPI_PYTHON_BIN:-${PYTHON_BIN:-python3}}"

TS=$(date "+%Y-%m-%d_%H%M%S")
DEST="$OUTBASE/Archive/input_$TS"

# Run the builder
"${PYTHON_BIN}" "${OPS_ROOT}/build_kaspi_orders.py" \
  --input "$IN" \
  --outbase "$OUTBASE" \
  --date "$RUN_DATE" \
  --zip-mode "$ZIP_MODE"

# Archive whatever was in input (xlsx + zips) so tomorrow starts clean
mkdir -p "$DEST"
mv "$IN"/*.xlsx "$IN"/*.zip "$DEST" 2>/dev/null || true
echo "Archived input files to: $DEST"
