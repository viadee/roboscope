#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Test script: verifies the offline dist directory for a given platform
#
# Usage:  ./scripts/test-install-mac-and-linux.sh [platform]
#
# Platforms: linux, macos-arm64, macos-x86_64
# If not specified, the platform is auto-detected from the host.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Resolve platform argument (default: auto-detect from host)
PLATFORM="${1:-}"
if [ -z "$PLATFORM" ]; then
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)  PLATFORM="linux" ;;
    Darwin-arm64)  PLATFORM="macos-arm64" ;;
    Darwin-x86_64) PLATFORM="macos-x86_64" ;;
    *) PLATFORM="linux" ;;
  esac
fi

# Map platform to pip --platform flag for cross-platform dry-run
case "$PLATFORM" in
  linux)        PIP_PLATFORM="manylinux2014_x86_64" ;;
  macos-arm64)  PIP_PLATFORM="macosx_11_0_arm64" ;;
  macos-x86_64) PIP_PLATFORM="macosx_11_0_x86_64" ;;
  *)
    echo "Unknown platform: $PLATFORM"
    echo "Supported: linux, macos-arm64, macos-x86_64"
    exit 1
    ;;
esac

DIST="$ROOT/dist/roboscope-offline-$PLATFORM"
TEST_DIR=$(mktemp -d)

echo "==> Test: offline dist for platform '$PLATFORM'"
echo "    Dist:     $DIST"
echo "    Temp:     $TEST_DIR"
echo "    pip plat: $PIP_PLATFORM"
echo ""

# Verify dist exists
if [ ! -d "$DIST" ]; then
  echo "ERROR: $DIST does not exist. Run scripts/build-mac-and-linux.sh $PLATFORM first."
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
# We use pip's --platform flag rather than installing into a fresh venv so that
# cross-platform wheels (e.g. windows wheels tested on a Linux runner) can be
# validated without needing a matching Python environment.
echo "==> Testing pip install --dry-run (no actual install)..."
cd "$TEST_DIR"

echo "    Python: $(python3 --version)"
echo "    pip platform: $PIP_PLATFORM"
echo ""

python3 -m pip install \
  --no-index \
  --find-links=wheels \
  -r requirements.txt \
  --dry-run \
  --platform "$PIP_PLATFORM" \
  --python-version 3.12 \
  --implementation cp \
  --abi cp312 \
  --only-binary :all: \
  2>&1
RESULT=$?
rm -rf "$TEST_DIR"

echo ""
if [ $RESULT -eq 0 ]; then
  echo "==> TEST PASSED: All requirements can be resolved from wheels."
else
  echo "==> TEST FAILED: pip could not resolve all requirements (exit code $RESULT)."
  exit 1
fi
