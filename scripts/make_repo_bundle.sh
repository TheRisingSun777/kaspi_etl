#!/usr/bin/env bash
# scripts/make_repo_bundle.sh
set -Eeuo pipefail

# ---- discover repo context ----
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
REPO="$(basename "$ROOT")"
BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
STAMP="$(date -u +%Y%m%d_%H%M)"
OUTDIR="assistant_bundles"
TMP=".tmp_assistant_bundle_${REPO}_${STAMP}"

mkdir -p "$OUTDIR" "$TMP"

# ---- find a sane diff base ----
git fetch --all --quiet || true
if git rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
  BASE="origin/$BRANCH"
elif git rev-parse --verify --quiet origin/main >/dev/null; then
  BASE="origin/main"
elif git rev-parse --verify --quiet origin/master >/dev/null; then
  BASE="origin/master"
else
  BASE="$(git rev-list --max-parents=0 HEAD)"  # first commit as fallback
fi

# ---- meta files ----
git status -sb > "$TMP/git_status.txt" || true
git log -n 40 --oneline --decorate --graph > "$TMP/git_log.txt" || true

git diff --no-color "$BASE"...HEAD > "$TMP/changes.diff" || true
# if empty, leave a note so you don't see "Zero bytes"
if [ ! -s "$TMP/changes.diff" ]; then
  printf "# No diff between %s and HEAD at %s UTC\n" "$BASE" "$STAMP" > "$TMP/changes.diff"
fi

cat > "$TMP/bundle_info.txt" <<EOF
repo: $REPO
branch: $BRANCH
base: $BASE
created_utc: $STAMP
EOF

# ---- copy source (tracked + useful untracked) with safe excludes ----
# Use rsync for selective copy and exclusions. macOS has rsync by default.
RSYNC_EXCLUDES=(
  --exclude '.git'
  --exclude 'assistant_bundles'
  --exclude '.tmp_assistant_bundle_*'
  --exclude 'node_modules'
  --exclude '.next'
  --exclude 'dist'
  --exclude 'build'
  --exclude 'out'
  --exclude '.turbo'
  --exclude '__pycache__'
  --exclude '*.pyc'
  --exclude '.venv'
  --exclude 'venv'
  --exclude '.DS_Store'
  --exclude '*.sqlite'
  --exclude '*.sqlite3'
  --exclude 'server/merchant/*.cookie.json'
  --exclude '*.env'
  --exclude '.env*'
)

copy_dir () {
  [ -e "$1" ] && rsync -a "${RSYNC_EXCLUDES[@]}" "$1" "$TMP/" || true
}
copy_file () {
  [ -f "$1" ] && rsync -a "$1" "$TMP/" || true
}

# Common top-level content
copy_dir apps
copy_dir scripts
copy_dir server
copy_dir db
copy_dir docs
copy_dir data_raw/schema
copy_file README.md
copy_file requirements.txt
copy_file package.json
copy_file pnpm-workspace.yaml
copy_file pnpm-lock.yaml
copy_file package-lock.json
copy_file tsconfig.json
copy_file Makefile
copy_file .gitignore

# ---- add sanitized env samples if present ----
sanitize_env () {
  local src="$1" dst="$2"
  awk -F= 'BEGIN{OFS="="} /^[[:space:]]*#/ {print; next}
           NF>=2 {print $1,"***REDACTED***"; next}
           {print}' "$src" > "$dst"
}
mkdir -p "$TMP/env"
for f in .env .env.local .env.development .env.production; do
  if [ -f "$f" ]; then sanitize_env "$f" "$TMP/env/$(basename "$f").redacted"; fi
done
# app-level envs (shallow scan)
find apps -maxdepth 3 -type f -name ".env*" \
  ! -path "*/node_modules/*" ! -path "*/.git/*" 2>/dev/null |
while IFS= read -r ef; do
  sanitize_env "$ef" "$TMP/env/$(echo "$ef" | tr '/' '_').redacted"
done

# ---- zip it ----
ZIP="$OUTDIR/assistant_bundle_${REPO}_${STAMP}.zip"
(
  cd "$TMP"
  zip -r -9 "../$(basename "$ZIP")" . >/dev/null
)
rm -rf "$TMP"

echo "Bundle created: $ZIP"
