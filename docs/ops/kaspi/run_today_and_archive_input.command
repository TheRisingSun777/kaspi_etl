#!/bin/zsh
set -euo pipefail

IN="/Users/adil/Documents/kaspi/Kaspi_orders/input"
OUTBASE="/Users/adil/Documents/kaspi/Kaspi_orders"
TS=$(date "+%Y-%m-%d_%H%M%S")
DEST="$OUTBASE/Archive/input_$TS"

# Run the builder
/Users/adil/.venvs/kaspi/bin/python "/Users/adil/Documents/kaspi/build_kaspi_orders.py" \
  --input "$IN" \
  --outbase "$OUTBASE" \
  --date today \
  --zip-mode one

# Archive whatever was in input (xlsx + zips) so tomorrow starts clean
mkdir -p "$DEST"
mv "$IN"/*.xlsx "$IN"/*.zip "$DEST" 2>/dev/null || true
echo "Archived input files to: $DEST"
