#!/usr/bin/env bash
set -euo pipefail

# sync_from_github.sh
# Pull the latest commits from GitHub origin/main into this Repl.
#
# Usage:
#   bash sync_from_github.sh
#
# Requirements:
#   - GITHUB_TOKEN secret must be set in Replit Secrets
#   - scripts/git-credential-github.sh must be present (already configured in .git/config)
#
# Notes:
#   - git fetch origin works natively because .git/config references
#     scripts/git-credential-github.sh as the credential helper.
#   - git reset --hard origin/main may be blocked by Replit if origin/main has
#     a different .replit file. This script handles that gracefully.

ORIGIN="origin"
TARGET="$ORIGIN/main"
SCRIPT_NAME="sync_from_github.sh"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ERROR: GITHUB_TOKEN is not set. Add it to Replit Secrets." >&2
  exit 1
fi

echo "==> Fetching from $ORIGIN..."
git fetch "$ORIGIN"

echo "==> Attempting git reset --hard $TARGET..."
if git reset --hard "$TARGET" 2>&1; then
  echo "Done. Repo is now at $(git rev-parse --short HEAD)."
  echo "Restart the workflow to pick up code changes."
  exit 0
fi

echo ""
echo "NOTE: git reset --hard was blocked (Replit prevents overwriting .replit)."
echo "==> Falling back to selective file sync from $TARGET (skipping .replit)..."

CHANGED=$(git diff --name-only HEAD "$TARGET" | grep -v '^\.replit$' | grep -v "^${SCRIPT_NAME}$" || true)
DELETED=$(git diff --name-only --diff-filter=D HEAD "$TARGET" | grep -v '^\.replit$' | grep -v "^${SCRIPT_NAME}$" || true)

if [[ -z "$CHANGED" ]]; then
  echo "Already up to date with $TARGET (only .replit differs)."
  exit 0
fi

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  if git ls-tree --name-only "$TARGET" -- "$file" | grep -q .; then
    echo "  checkout: $file"
    git checkout "$TARGET" -- "$file"
  fi
done <<< "$CHANGED"

if [[ -n "$DELETED" ]]; then
  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    echo "  delete: $file"
    rm -f "$file"
  done <<< "$DELETED"
fi

echo ""
echo "Sync complete. Files updated from $TARGET:"
echo "$CHANGED"
echo "Note: .replit and ${SCRIPT_NAME} were skipped. Restart workflow after sync."
