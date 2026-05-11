#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Story HEAL-VENDORED — pull the latest `robotframework-roboscopeheal`
# source from the sibling repo (or a custom path) into RoboScope's
# `backend/vendor/robotframework-roboscopeheal/` tree. Shows the
# diff before clobbering anything; bails out if the user says no.
#
# Usage:
#   ./scripts/sync-roboscopeheal.sh                       # default: ../roboscope-rfheal
#   ./scripts/sync-roboscopeheal.sh /path/to/rfheal       # explicit source
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${1:-$ROOT_DIR/../roboscope-rfheal}"
VENDOR_DIR="$ROOT_DIR/backend/vendor/robotframework-roboscopeheal"

if [ ! -d "$SOURCE_DIR/src/RoboScopeHeal" ]; then
  echo "ERROR: source directory missing or wrong shape:"
  echo "  expected: $SOURCE_DIR/src/RoboScopeHeal/"
  echo
  echo "Either clone the sibling repo there, or pass an explicit path:"
  echo "  $0 /path/to/roboscope-rfheal"
  exit 2
fi
if [ ! -d "$VENDOR_DIR" ]; then
  echo "ERROR: vendor directory missing — was the layout changed?"
  echo "  expected: $VENDOR_DIR"
  exit 2
fi

echo "=========================================================="
echo "Source: $SOURCE_DIR"
echo "Target: $VENDOR_DIR"
echo "=========================================================="
echo

# Compute the diff so the user knows exactly what's about to change.
# `--brief --recursive` lists differing files without dumping every
# line; the user can `diff -ru` themselves if they want detail.
#
# Excludes cover the sibling-repo-only directories we deliberately
# don't vendor (tests, uv.lock, .gitignore, dev caches) — see
# HEAL-VENDORED story for the rationale.
echo "--- Diff (brief, recursive) ---"
DIFF_OUTPUT=$(
  diff --brief --recursive \
    --exclude __pycache__ --exclude '*.egg-info' --exclude .pytest_cache \
    --exclude .mypy_cache --exclude .venv --exclude dist --exclude .git \
    --exclude tests --exclude uv.lock --exclude .gitignore \
    "$SOURCE_DIR" "$VENDOR_DIR" || true
)
if [ -z "$DIFF_OUTPUT" ]; then
  echo "(no changes — vendor is up to date)"
  exit 0
fi
echo "$DIFF_OUTPUT"
echo

# Refuse to clobber unless the user explicitly confirms. CI / scripted
# callers can set ROBOSCOPE_SYNC_ASSUME_YES=1 to skip the prompt.
if [ "${ROBOSCOPE_SYNC_ASSUME_YES:-}" != "1" ]; then
  read -r -p "Overwrite vendor with source? [y/N] " ans
  case "$ans" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 1 ;;
  esac
fi

# Mirror the same exclusions used by the diff above so we don't
# clobber the vendor with build artefacts from the source repo.
rsync -a --delete \
  --exclude __pycache__ --exclude '*.egg-info' --exclude .pytest_cache \
  --exclude .mypy_cache --exclude .venv --exclude dist --exclude .git \
  "$SOURCE_DIR/src/RoboScopeHeal/" "$VENDOR_DIR/src/RoboScopeHeal/"

for f in pyproject.toml README.md LICENSE NOTICE CHANGELOG.md; do
  if [ -f "$SOURCE_DIR/$f" ]; then
    cp "$SOURCE_DIR/$f" "$VENDOR_DIR/$f"
  fi
done

echo
echo "Sync complete. Verify with:"
echo "  cd backend && uv sync"
echo "  .venv/bin/python -c 'import RoboScopeHeal; print(RoboScopeHeal.__version__)'"
