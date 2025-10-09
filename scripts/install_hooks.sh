#!/bin/sh
# Install Git hooks for the repository (idempotent).

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOK_SOURCE="${REPO_ROOT}/hooks/pre-commit"
HOOK_DEST="${REPO_ROOT}/.git/hooks/pre-commit"

if [ ! -d "${REPO_ROOT}/.git" ]; then
  echo "Error: ${REPO_ROOT} does not appear to be a Git repository." >&2
  exit 1
fi

if [ ! -f "$HOOK_SOURCE" ]; then
  echo "Error: hook template not found at $HOOK_SOURCE" >&2
  exit 1
fi

mkdir -p "$(dirname "$HOOK_DEST")"
cp "$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

echo "Installed protected-paths pre-commit hook to .git/hooks/pre-commit."
