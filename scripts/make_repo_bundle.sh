#!/usr/bin/env bash
set -euo pipefail

repo=$(basename "$(git rev-parse --show-toplevel)")
branch=$(git rev-parse --abbrev-ref HEAD)
sha=$(git rev-parse --short HEAD)
stamp=$(date +%Y%m%d_%H%M)
out="assistant_bundle_${repo}_${branch}_${stamp}.zip"

# Create a clean archive of the current HEAD respecting .gitattributes export-ignore rules
git archive --format=zip -o "$out" HEAD

# Optionally append curated datasets if present
zip -ur "$out" \
  data_crm/processed_sales_*.csv \
  data_crm/stock_on_hand_updated.csv \
  data_crm/mappings/ksp_sku_map_updated.xlsx \
  data_crm/orders_clean_preview.csv \
  data_crm/missing_skus.csv \
  data_crm/size_grid_all_models.* \
  data_crm/size_grid_by_model_group.* \
  2>/dev/null || true

# Inject a small manifest with context
printf '{"branch":"%s","commit":"%s","created":"%s"}' "$branch" "$sha" "$stamp" > manifest.json
zip -u "$out" manifest.json >/dev/null
rm -f manifest.json

# Print final filename
printf '%s\n' "$out"
