#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# RoboScope — Build script for standalone offline distribution
#
# Creates a self-contained directory 'dist/roboscope-offline-<platform>/'
# that can be zipped and deployed on the target machine without internet.
#
# Usage:  ./scripts/build-mac-and-linux.sh <platform>
#
# Platforms:
#   linux        — Linux x86_64
#   macos-arm64  — macOS Apple Silicon (ARM64)
#   macos-x86_64 — macOS Intel (x86_64)
#
# For Windows, use scripts/build-windows.ps1 on a Windows host.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PLATFORM="${1:-}"

if [ -z "$PLATFORM" ]; then
  echo "Usage: $0 <platform>"
  echo ""
  echo "Platforms:"
  echo "  linux        — Linux x86_64"
  echo "  macos-arm64  — macOS Apple Silicon (ARM64)"
  echo "  macos-x86_64 — macOS Intel (x86_64)"
  echo ""
  echo "For Windows, use: powershell -File scripts/build-windows.ps1"
  exit 1
fi

UV_BASE="https://github.com/astral-sh/uv/releases/latest/download"

case "$PLATFORM" in
  linux)
    UV_ARCHIVE="uv-x86_64-unknown-linux-gnu.tar.gz"
    UV_BIN_NAME="uv-linux-x86_64"
    WHEEL_PLATFORM="manylinux2014_x86_64"
    ;;
  macos-arm64)
    UV_ARCHIVE="uv-aarch64-apple-darwin.tar.gz"
    UV_BIN_NAME="uv-macos-arm64"
    WHEEL_PLATFORM="macosx_11_0_arm64"
    ;;
  macos-x86_64)
    UV_ARCHIVE="uv-x86_64-apple-darwin.tar.gz"
    UV_BIN_NAME="uv-macos-x86_64"
    WHEEL_PLATFORM="macosx_11_0_x86_64"
    ;;
  *)
    echo "Unknown platform: $PLATFORM"
    echo "Supported: linux, macos-arm64, macos-x86_64"
    echo "For Windows, use: powershell -File scripts/build-windows.ps1"
    exit 1
    ;;
esac

ZIP_NAME="roboscope_offline_${PLATFORM}.zip"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/roboscope-offline-$PLATFORM"

echo "==> RoboScope Build (offline, $PLATFORM)"
echo "    Root: $ROOT"
echo "    Dist: $DIST"
echo ""

# ── 1. Clean previous build ──────────────────────────────────
rm -rf "$DIST"
mkdir -p "$DIST"

# ── 2. Build frontend ────────────────────────────────────────
echo "==> Building frontend..."
cd "$ROOT/frontend"
npm ci --prefer-offline 2>/dev/null || npm install
npm run build

# Copy built frontend into backend as frontend_dist/
cp -r "$ROOT/frontend/dist" "$DIST/frontend_dist"
echo "    Frontend built: $DIST/frontend_dist"

# ── 3. Copy backend source ───────────────────────────────────
echo "==> Copying backend..."
cp -r "$ROOT/backend/src" "$DIST/src"
cp "$ROOT/backend/pyproject.toml" "$DIST/"

# Copy example test files for the seeded "Examples" project
if [ -d "$ROOT/backend/examples" ]; then
  cp -r "$ROOT/backend/examples" "$DIST/examples"
  echo "    Examples: $DIST/examples"
fi

# Copy migrations if they exist
if [ -d "$ROOT/backend/migrations" ]; then
  cp -r "$ROOT/backend/migrations" "$DIST/migrations"
  cp "$ROOT/backend/alembic.ini" "$DIST/" 2>/dev/null || true
fi

# ── Copy README ─────────────────────────────────────────────
cp "$ROOT/scripts/dist-README.md" "$DIST/README.md"
echo "    README: $DIST/README.md"

# ── 3b. Download uv binary for this platform ─────────────────
echo "==> Downloading uv binary for $PLATFORM..."
mkdir -p "$DIST/uv-bin"

curl -fsSL "$UV_BASE/$UV_ARCHIVE" | tar -xz -C "$DIST/uv-bin" --strip-components=1 2>/dev/null \
  && mv "$DIST/uv-bin/uv" "$DIST/uv-bin/$UV_BIN_NAME" \
  && echo "    uv binary: $UV_BIN_NAME" \
  || echo "    WARN: failed to download uv binary for $PLATFORM"

# ── 4. Download Python wheels for offline install ─────────────
echo "==> Downloading Python wheels for $PLATFORM ($WHEEL_PLATFORM)..."
mkdir -p "$DIST/wheels"

# Helper: extract dependencies from pyproject.toml (works with Python 3.10+)
_read_deps() {
  cd "$ROOT/backend"
  python3 -c "
import pathlib
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        import sys
        lines = pathlib.Path('pyproject.toml').read_text().splitlines()
        in_deps = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('dependencies') and '=' in stripped:
                in_deps = True
                continue
            if in_deps:
                if stripped == ']':
                    break
                dep = stripped.strip(',').strip('\"').strip(\"'\")
                if dep and dep != '[':
                    print(dep)
        sys.exit(0)
data = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
for dep in data['project']['dependencies']:
    print(dep)
"
}

DEPS_FILE=$(mktemp)
_read_deps > "$DEPS_FILE"
REQ_FILE="$DEPS_FILE"

# Story HEAL-VENDORED — `robotframework-roboscopeheal` is in pyproject.toml's
# runtime deps so `uv sync` resolves it via [tool.uv.sources], but the package
# is NOT published on PyPI yet. Passing the unfiltered deps file to
# `pip download` makes pip's resolver bail on the missing index entry —
# dropping every other wheel along with it (symptom that broke main on
# 2026-06-01: "No matching distribution found for fastapi>=0.115.0" — pip
# never even tried, because resolution aborted upstream). Strip the line
# for the download pass; the build produces the vendored wheel from source
# a few steps below (RFHEAL_VENDOR block) so the offline install still
# resolves it via --find-links.
PIPDL_REQ_FILE=$(mktemp)
grep -v '^robotframework-roboscopeheal' "$REQ_FILE" > "$PIPDL_REQ_FILE"

# Download platform-specific binary wheels
for pyver in 3.10 3.11 3.12 3.13 3.14; do
  abi="cp${pyver//./}"
  echo "    Downloading wheels for $WHEEL_PLATFORM (Python $pyver)..."
  python3 -m pip download \
    -r "$PIPDL_REQ_FILE" \
    -d "$DIST/wheels" \
    --platform "$WHEEL_PLATFORM" \
    --python-version "$pyver" \
    --implementation cp \
    --abi "$abi" \
    --only-binary :all: \
    2>&1 | grep -i "error\|saved" || true
done

# Also download for host platform (catches pure-python deps missed by cross-platform pass)
echo "    Downloading wheels for host platform..."
python3 -m pip download \
  -r "$PIPDL_REQ_FILE" \
  -d "$DIST/wheels" \
  2>/dev/null || true

# Ensure conditional transitive deps are included
# (e.g., tomli is needed by alembic on Python <3.11 but not on 3.12+,
#  greenlet is required by SQLAlchemy on x86_64/aarch64/AMD64/WIN32)
echo "    Downloading conditional dependencies..."
for pkg in "tomli>=2.0.0" "exceptiongroup>=1.0.0" "typing_extensions>=4.0.0" "greenlet>=3.1.0"; do
  python3 -m pip download "$pkg" -d "$DIST/wheels" --no-deps 2>/dev/null || true
done

# Story HEAL-VENDORED — build the vendored `robotframework-
# roboscopeheal` wheel from `backend/vendor/...` and drop it
# alongside the pip-downloaded wheels. Until v0.2 is on PyPI this
# is the only way the offline install path can satisfy the dep.
# `python -m build` produces a pure-Python wheel; `install.sh`'s
# `pip install --no-index --find-links wheels/` picks it up by
# version match, no special-case install logic needed.
RFHEAL_VENDOR="$ROOT/backend/vendor/robotframework-roboscopeheal"
if [ -d "$RFHEAL_VENDOR" ]; then
  echo "    Building robotframework-roboscopeheal wheel from vendor..."
  # `python -m build` requires the `build` package — install it
  # transiently if missing rather than expecting it to be there.
  python3 -m pip install --quiet --upgrade build 2>/dev/null || true
  (cd "$RFHEAL_VENDOR" \
   && python3 -m build --wheel --outdir "$DIST/wheels" 2>&1 \
   | grep -iE "built|error|warn" || true)
else
  echo "    WARN: $RFHEAL_VENDOR missing — heal library won't be in this bundle." >&2
fi

# Save requirements for install scripts
cp "$REQ_FILE" "$DIST/requirements.txt"
rm -f "$DEPS_FILE" "$PIPDL_REQ_FILE"
echo "    Wheels: $(ls "$DIST/wheels" | wc -l | tr -d ' ') packages"

# ── 4b. Bundle Playwright browser-pack as a SEPARATE optional ZIP ──
#
# The Robot Framework Browser library can ONLY obtain its Chromium binary
# by downloading it (`rfbrowser init` → npm + the Playwright CDN). On an
# air-gapped / proxy-restricted target that fails and Browser tests die
# with "browserType.launch: Executable doesn't exist". Harvest the binaries
# HERE (the build host has internet) into a SEPARATE
# `roboscope_browser_pack_linux.zip` so the main offline ZIP stays lean —
# only users running Browser tests download the extra pack and unzip it
# next to the app, producing a `browser-pack/` dir the backend auto-detects.
# At env-create time the backend LINKS each env's .local-browsers to the
# single shared pack (no per-env duplication).
#
# ONLY for the native-Linux leg: Playwright browser binaries are platform-
# specific native executables and CANNOT be cross-built. The macOS legs
# cross-download wheels on an ubuntu host (--platform), so a `rfbrowser
# init` there would yield Linux browsers — wrong for a macOS target.
# Native macOS packs need a macOS runner (follow-up).
if [ "$PLATFORM" = "linux" ]; then
  echo "==> Building offline Playwright browser-pack ZIP (native Linux)..."
  PACK_STAGING="$ROOT/dist/browser-pack-linux"
  PACK_DIR="$PACK_STAGING/browser-pack"
  rm -rf "$PACK_STAGING"
  TMP_VENV=$(mktemp -d)/bp-venv
  UV_BIN_ABS="$DIST/uv-bin/$UV_BIN_NAME"
  if "$UV_BIN_ABS" venv "$TMP_VENV" >/dev/null 2>&1 \
     && "$UV_BIN_ABS" pip install --python "$TMP_VENV/bin/python" \
          robotframework-browser-batteries >/dev/null 2>&1; then
    # `-batteries` ships the Node wrapper in the wheel; rfbrowser init then
    # only fetches the browser binaries (the variant users install, so its
    # build numbers match what they run against). chromium ONLY — the
    # arg-less `init` also pulls Firefox + WebKit (~1.2 GB pack); chromium
    # (headed + headless shell) covers the vast majority of Browser tests.
    PATH="$TMP_VENV/bin:$PATH" "$TMP_VENV/bin/rfbrowser" init chromium 2>&1 \
      | grep -iE "error|browser|download" || true
    LOCAL_BROWSERS=$("$TMP_VENV/bin/python" - <<'PYEOF'
import pathlib, sys
sp = next(pathlib.Path(sys.prefix).glob("lib/python*/site-packages"), None)
lb = sp / "Browser" / "wrapper" / "node_modules" / "playwright-core" / ".local-browsers" if sp else None
print(lb if lb and lb.is_dir() else "")
PYEOF
)
    if [ -n "$LOCAL_BROWSERS" ] && [ -d "$LOCAL_BROWSERS" ]; then
      mkdir -p "$PACK_DIR"
      cp -R "$LOCAL_BROWSERS" "$PACK_DIR/.local-browsers"
      echo "robotframework-browser-batteries / rfbrowser init chromium (linux native)" \
        > "$PACK_DIR/PROVENANCE.txt"
      printf '%s\n' \
        "Unzip this folder INTO your roboscope-offline-linux directory so it sits" \
        "next to start-mac-and-linux.sh. RoboScope auto-detects browser-pack/ and" \
        "shares it across all environments — no per-env download needed." \
        > "$PACK_DIR/README.txt"
      PACK_ZIP="$ROOT/dist/roboscope_browser_pack_linux.zip"
      rm -f "$PACK_ZIP"
      ( cd "$PACK_STAGING" && zip -r -q "$PACK_ZIP" browser-pack )
      echo "    Browser-pack ZIP: $(du -sh "$PACK_ZIP" | cut -f1) at $PACK_ZIP"
    else
      echo "    WARN: rfbrowser init produced no .local-browsers — browser-pack skipped." >&2
    fi
  else
    echo "    WARN: browser-pack venv/install failed — continuing without it." >&2
  fi
  rm -rf "$(dirname "$TMP_VENV")" "$PACK_STAGING"
else
  echo "==> Skipping browser-pack for $PLATFORM (browsers can't be cross-built; native macOS runner needed)."
fi

# ── 5. Create .env template ──────────────────────────────────
cat > "$DIST/.env.example" << 'ENVEOF'
# RoboScope Configuration
# Copy this to .env and adjust as needed.

# Database (SQLite default — no setup required)
DATABASE_URL=sqlite:///./roboscope.db

# Secret key for JWT tokens (change in production!)
SECRET_KEY=CHANGE-ME-IN-PRODUCTION

# Server
HOST=0.0.0.0
PORT=8145
DEBUG=false

# Logging
LOG_LEVEL=INFO
# LOG_FORMAT — `text` (default for standalone start) for human-readable
# console logs, or `json` for log shippers / Docker / CI.
LOG_FORMAT=text

# Auto-open the app in your default browser after startup. Default OFF
# (commented) so headless installs don't surprise you. Set to 1 to enable.
# OPEN_BROWSER=1

# Directories (defaults shown — adjust if needed)
# WORKSPACE_DIR=~/.roboscope/workspace
# REPORTS_DIR=~/.roboscope/reports
# VENVS_DIR=~/.roboscope/venvs
ENVEOF

# ── 6. Create install/start/stop scripts ─────────────────────
UV_BIN_UNIX="uv-bin/$UV_BIN_NAME"

cat > "$DIST/install-mac-and-linux.sh" << INSTALLEOF
#!/usr/bin/env bash
set -euo pipefail
cd "\$(dirname "\$0")"

echo "==> Installing RoboScope..."

UV_BIN="$UV_BIN_UNIX"

if [ -f "\$UV_BIN" ]; then
  chmod +x "\$UV_BIN"
else
  echo "Error: uv binary not found at \$UV_BIN."
  exit 1
fi

# Create virtual environment with uv
./"\$UV_BIN" venv .venv

# Install dependencies offline
./"\$UV_BIN" pip install --python .venv/bin/python --no-index --find-links=wheels -r requirements.txt

# Copy default config if not exists
[ -f .env ] || cp .env.example .env

echo ""
echo "==> RoboScope installed successfully!"
echo "    Start with: ./start-mac-and-linux.sh"
INSTALLEOF
chmod +x "$DIST/install-mac-and-linux.sh"

cat > "$DIST/start-mac-and-linux.sh" << 'STARTEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present
if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

# Default to readable text logs for the human running this binary.
# .env can override (LOG_FORMAT=json) to keep log shippers happy.
export LOG_FORMAT="${LOG_FORMAT:-text}"

PORT="${PORT:-8145}"

# Check if port is already in use
if lsof -i :"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Error: Port $PORT is already in use."
  echo ""
  if command -v lsof >/dev/null 2>&1; then
    echo "Process using port $PORT:"
    lsof -i :"$PORT" -sTCP:LISTEN 2>/dev/null || true
  fi
  echo ""
  echo "Options:"
  echo "  1. Stop the other process:  ./stop-mac-and-linux.sh"
  echo "  2. Change the port in .env: PORT=9000"
  exit 1
fi

# Activate venv
if [ -d ".venv" ]; then
  source .venv/bin/activate
else
  echo "Error: Run ./install-mac-and-linux.sh first."
  exit 1
fi

echo "==> Starting RoboScope..."
echo "    URL: http://localhost:${PORT}"
echo "    API: http://localhost:${PORT}/api/v1/docs"
echo "    Default login: admin@roboscope.local / admin123"
echo ""

python -m uvicorn src.main:app --host "${HOST:-0.0.0.0}" --port "${PORT}"
STARTEOF
chmod +x "$DIST/start-mac-and-linux.sh"

cat > "$DIST/stop-mac-and-linux.sh" << 'STOPEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present
if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

PORT="${PORT:-8145}"

echo "==> Stopping RoboScope on port $PORT..."

PIDS=$(lsof -ti :"$PORT" -sTCP:LISTEN 2>/dev/null || true)
if [ -z "$PIDS" ]; then
  echo "    No process found on port $PORT."
  exit 0
fi

for PID in $PIDS; do
  echo "    Stopping PID $PID..."
  kill "$PID" 2>/dev/null || true
done

# Wait up to 5 seconds for graceful shutdown
for i in $(seq 1 10); do
  if ! lsof -ti :"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "    RoboScope stopped."
    exit 0
  fi
  sleep 0.5
done

# Force kill if still running
PIDS=$(lsof -ti :"$PORT" -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "    Force stopping..."
  for PID in $PIDS; do
    kill -9 "$PID" 2>/dev/null || true
  done
fi

echo "    RoboScope stopped."
STOPEOF
chmod +x "$DIST/stop-mac-and-linux.sh"

# ── 7. Create ZIP ─────────────────────────────────────────────
echo ""
echo "==> Creating ZIP archive..."
cd "$ROOT/dist"
zip -r "$ZIP_NAME" "roboscope-offline-$PLATFORM/" -x "roboscope-offline-$PLATFORM/.venv/*" "roboscope-offline-$PLATFORM/__pycache__/*"
echo ""
echo "==> Build complete!"
echo "    Distribution: $ROOT/dist/$ZIP_NAME"
echo "    Directory:    $DIST"
echo ""
PLATFORM_DISPLAY="$(echo "$PLATFORM" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
echo "To deploy on $PLATFORM_DISPLAY:"
echo "  1. Extract $ZIP_NAME"
echo "  2. Run ./install-mac-and-linux.sh"
echo "  3. Run ./start-mac-and-linux.sh"
