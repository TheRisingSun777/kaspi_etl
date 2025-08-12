#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
SAFE_BRANCH="${BRANCH//\//-}"
ROOT="$(git rev-parse --show-toplevel)"
OUT="$ROOT/assistant_bundles"
TMP="$(mktemp -d "$ROOT/.tmp_assistant_bundle_${SAFE_BRANCH}_XXXX")"
TS="$(date +%Y%m%d_%H%M)"

mkdir -p "$OUT"

copy() {
  local rel="$1"
  if [[ -e "$ROOT/$rel" ]]; then
    mkdir -p "$TMP/$(dirname "$rel")"
    rsync -a \
      --exclude '.next' \
      --exclude 'node_modules' \
      --exclude '.DS_Store' \
      --exclude 'make_assistant_bundle.sh' \
      "$ROOT/$rel" "$TMP/$rel"
  else
    echo "WARN: missing $rel"
  fi
}

# App bits
copy apps/kaspi_offers_dashboard/app/api/pricebot
copy apps/kaspi_offers_dashboard/components/pricebot
copy apps/kaspi_offers_dashboard/lib/pricebot
copy apps/kaspi_offers_dashboard/scripts
copy apps/kaspi_offers_dashboard/docs
copy apps/kaspi_offers_dashboard/package.json

# Repo-level metadata
copy pnpm-workspace.yaml
copy pnpm-lock.yaml

# Git diff for traceability (best-effort)
git -C "$ROOT" --no-pager diff --no-ext-diff origin/main..."$BRANCH" > "$TMP/changes.diff" || true

# Sanitize / add env example if present
if [[ -f "$ROOT/apps/kaspi_offers_dashboard/.env.example" ]]; then
  mkdir -p "$TMP/env"
  cp "$ROOT/apps/kaspi_offers_dashboard/.env.example" "$TMP/env/.env.example"
fi

ZIP="$OUT/assistant_bundle_${SAFE_BRANCH}_${TS}.zip"
(
  cd "$TMP"
  zip -r "$ZIP" . >/dev/null
)
echo "Bundle created: $ZIP"
