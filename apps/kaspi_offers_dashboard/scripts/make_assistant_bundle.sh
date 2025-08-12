#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/make_assistant_bundle.sh [branch]
# Example: scripts/make_assistant_bundle.sh feat/offers-dashboard

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
SAFE_BRANCH="${BRANCH//\//-}"                # sanitize for filenames
TS="$(date +%Y%m%d_%H%M)"
OUTDIR="$ROOT/assistant_bundles"
TMP="$OUTDIR/_tmp_${SAFE_BRANCH}_${TS}"

mkdir -p "$OUTDIR" "$TMP"

copy() {
  local rel="$1"
  local src="$ROOT/$rel"
  local dst="$TMP/$rel"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    rsync -a "$src" "$dst"
  else
    echo "WARN: missing $rel" >&2
  fi
}

# What to include (adjust freely)
copy apps/kaspi_offers_dashboard/app/api/pricebot
copy apps/kaspi_offers_dashboard/components/pricebot
copy apps/kaspi_offers_dashboard/lib/pricebot
copy apps/kaspi_offers_dashboard/scripts
copy apps/kaspi_offers_dashboard/docs
copy apps/kaspi_offers_dashboard/package.json

# root-level files
copy pnpm-workspace.yaml
copy pnpm-lock.yaml

# Optional: include sanitized env example if present
if [[ -f "$ROOT/apps/kaspi_offers_dashboard/.env.example" ]]; then
  copy apps/kaspi_offers_dashboard/.env.example
fi

# Optional: include a diff against main
git diff --no-ext-diff "origin/main...$BRANCH" > "$TMP/changes.diff" || true

ZIPFILE="$OUTDIR/assistant_bundle_${SAFE_BRANCH}_${TS}.zip"
(
  cd "$TMP"
  zip -r "$ZIPFILE" .
)
echo "Bundle created: $ZIPFILE"

# Cleanup temp dir
rm -rf "$TMP"
