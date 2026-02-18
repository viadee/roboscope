#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Test script: verifies the install.sh inside dist/mateox works
#
# Usage:  ./scripts/test-install.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/mateox"
TEST_DIR=$(mktemp -d)

echo "==> Test: install.sh from dist"
echo "    Dist:    $DIST"
echo "    Temp:    $TEST_DIR"
echo ""

# Verify dist exists
if [ ! -d "$DIST" ]; then
  echo "ERROR: $DIST does not exist. Run scripts/build.sh first."
  exit 1
fi

# Copy dist to temp (simulates extracting the ZIP)
cp -r "$DIST/"* "$TEST_DIR/"

echo "==> Checking dist contents..."
echo "    requirements.txt: $([ -f "$TEST_DIR/requirements.txt" ] && echo 'OK' || echo 'MISSING')"
echo "    wheels:           $(ls "$TEST_DIR/wheels/" | wc -l | tr -d ' ') files"
echo "    frontend_dist:    $([ -d "$TEST_DIR/frontend_dist" ] && echo 'OK' || echo 'MISSING')"
echo "    src/:             $([ -d "$TEST_DIR/src" ] && echo 'OK' || echo 'MISSING')"
echo ""

# Show requirements
echo "==> requirements.txt:"
cat "$TEST_DIR/requirements.txt" 2>/dev/null || echo "    (file missing!)"
echo ""

# Test: can pip resolve all requirements from the wheels?
echo "==> Testing pip install --dry-run (no actual install)..."
cd "$TEST_DIR"
python3 -m venv .venv
source .venv/bin/activate

echo "    Python: $(python3 --version)"
echo "    Platform: $(python3 -c 'import sysconfig; print(sysconfig.get_platform())')"
echo ""

pip install --no-index --find-links=wheels -r requirements.txt --dry-run 2>&1
RESULT=$?

deactivate
rm -rf "$TEST_DIR"

echo ""
if [ $RESULT -eq 0 ]; then
  echo "==> TEST PASSED: All requirements can be resolved from wheels."
else
  echo "==> TEST FAILED: pip could not resolve all requirements (exit code $RESULT)."
  exit 1
fi
