#!/usr/bin/env bash
set -euo pipefail

BRANCH=${1:-feat/offers-dashboard}
OUT="assistant_bundle_${BRANCH}_$(date +%Y%m%d_%H%M).zip"
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "branch: $(git rev-parse --abbrev-ref "$BRANCH")" > "$TMP/METADATA.txt"
echo "commit: $(git rev-parse "$BRANCH")"           >> "$TMP/METADATA.txt"
echo "base:   origin/main"                          >> "$TMP/METADATA.txt"

# Copy target paths (no secrets)
copy() {
  local p="$1"
  if [ -e "$ROOT/$p" ]; then
    mkdir -p "$TMP/$(dirname "$p")"
    # exclude local cookie files if that folder exists
    rsync -a --exclude='*.cookie.json' "$ROOT/$p" "$TMP/$p"
  fi
}
copy apps/kaspi_offers_dashboard/app/api/pricebot
copy apps/kaspi_offers_dashboard/components/pricebot
copy apps/kaspi_offers_dashboard/lib/pricebot
copy apps/kaspi_offers_dashboard/scripts
copy apps/kaspi_offers_dashboard/docs
copy package.json
copy pnpm-workspace.yaml
copy pnpm-lock.yaml

# Add the diff (so I can see exactly what changed)
git -C "$ROOT" diff --no-ext-diff origin/main.."$BRANCH" -- apps scripts docs > "$TMP/changes.diff" || true

# Sanitize env if present
if [ -f "$ROOT/apps/kaspi_offers_dashboard/.env.example" ]; then
  mkdir -p "$TMP/env"
  cp "$ROOT/apps/kaspi_offers_dashboard/.env.example" "$TMP/env/.env.example"
fi

( cd "$TMP" && zip -qr "$OUT" . )
mv "$TMP/$OUT" "$ROOT/"
echo "Wrote $ROOT/$OUT"