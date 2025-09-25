#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ZIP="$ROOT_DIR/kaspi_etl_analysis_bundle.zip"
SIZE_LIMIT=$((450 * 1024 * 1024)) # 450 MB

EXCLUDES=(
  "kaspi_etl_analysis_bundle.zip"
  ".git/*"
  ".git"
  "venv/*"
  "venv"
  "*/node_modules/*"
  "*.pyc"
  "__pycache__/*"
  "*/__pycache__/*"
  ".tmp_assistant_bundle_*"
  ".tmp_assistant_bundle_*/*"
  "apps/kaspi_offers_dashboard/data_raw/*"
  "apps/kaspi_offers_dashboard/.next/*"
  "apps/kaspi_offers_dashboard/.next"
  "apps/kaspi_offers_dashboard/.turbo/*"
  "apps/kaspi_offers_dashboard/.turbo"
  "docs/ops/kaspi/Kaspi_orders/Archive/*"
  "docs/ops/kaspi/Kaspi_orders/Archive"
  "docs/ops/kaspi/Kaspi_orders/Today/*"
  "docs/ops/kaspi/Kaspi_orders/Today"
  "docs/ops/kaspi/Kaspi_orders/input/*"
  "docs/ops/kaspi/Kaspi_orders/input"
  "docs/ops/kaspi/Kaspi_orders/*.zip"
  "docs/ops/kaspi/Kaspi_orders/*/*.zip"
  "docs/ops/kaspi/Kaspi_orders/*/*.pdf"
  "docs/ops/kaspi/Kaspi_orders/*/*/*.pdf"
)

pushd "$ROOT_DIR" >/dev/null

rm -f "$OUTPUT_ZIP"

ZIP_ARGS=("-r" "$OUTPUT_ZIP" ".")
for pattern in "${EXCLUDES[@]}"; do
  ZIP_ARGS+=("-x" "$pattern")
done

zip "${ZIP_ARGS[@]}" >/dev/null

if [ ! -f "$OUTPUT_ZIP" ]; then
  echo "Failed to create bundle at $OUTPUT_ZIP" >&2
  exit 1
fi

bundle_size=$(stat -f%z "$OUTPUT_ZIP")

if [ "$bundle_size" -gt "$SIZE_LIMIT" ]; then
  human_size=$(du -h "$OUTPUT_ZIP" | cut -f1)
  echo "Warning: bundle size $human_size exceeds 450MB limit." >&2
  exit 2
fi

human_size=$(du -h "$OUTPUT_ZIP" | cut -f1)
echo "Created $OUTPUT_ZIP ($human_size)"

popd >/dev/null
