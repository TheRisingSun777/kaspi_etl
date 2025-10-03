#!/bin/bash
set -Eeuo pipefail

# Go to repo root (this .command lives in docs/ops/kaspi/)
cd "$(dirname "$0")/../../"

# ---- configuration ---------------------------------------------------------
CONF_FILE="docs/ops/kaspi/perfume_input_path.txt"   # 1-line text file with full path to your .xlsx
DEFAULT_INPUT="/Users/adil/Documents/Ideas/perfume_analysis_gpt_7.9.25_v1/Perfumes_V11_MC_V2.1_30.9.25.xlsx"

CITY="${CITY:-710000000}"
CONCURRENCY="${CONCURRENCY:-120}"

OUT="data_raw/perfumes/offers_$(date +%Y%m%d_%H%M).csv"
# ---------------------------------------------------------------------------

# Resolve input path
if [[ -f "$CONF_FILE" ]]; then
  INPUT="$(cat "$CONF_FILE")"
else
  INPUT="$DEFAULT_INPUT"
fi
# Allow override if a path is passed as first arg (works when an Automator app passes it)
if [[ -n "${1:-}" ]]; then INPUT="$1"; fi

# Ensure folders
mkdir -p "data_raw/perfumes" "data_raw/perfumes/logs" "data_raw/perfumes/debug"

# Environment checks
if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found. Install once: npm i -g pnpm"
  exit 1
fi

# One-time Playwright deps (no-op if already installed)
npx playwright install --with-deps chromium >/dev/null 2>&1 || true

echo "Scraping from: $INPUT"
echo "City: $CITY   Concurrency: $CONCURRENCY"
echo "Output: $OUT"
echo "Starting…"

# Run
pnpm scrape:perfumes --input "$INPUT" --city "$CITY" --concurrency "$CONCURRENCY" --out "$OUT"

echo "Done → $OUT"
# Reveal the output in Finder
open -R "$OUT"
