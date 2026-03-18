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
#   windows      — Windows x86_64
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
  echo "  windows      — Windows x86_64"
  exit 1
fi

UV_BASE="https://github.com/astral-sh/uv/releases/latest/download"
IS_WINDOWS=false

case "$PLATFORM" in
  linux)
    UV_ARCHIVE="uv-x86_64-unknown-linux-gnu.tar.gz"
    UV_ARCHIVE_TYPE="tar"
    UV_BIN_NAME="uv-linux-x86_64"
    WHEEL_PLATFORM="manylinux2014_x86_64"
    ;;
  macos-arm64)
    UV_ARCHIVE="uv-aarch64-apple-darwin.tar.gz"
    UV_ARCHIVE_TYPE="tar"
    UV_BIN_NAME="uv-macos-arm64"
    WHEEL_PLATFORM="macosx_11_0_arm64"
    ;;
  macos-x86_64)
    UV_ARCHIVE="uv-x86_64-apple-darwin.tar.gz"
    UV_ARCHIVE_TYPE="tar"
    UV_BIN_NAME="uv-macos-x86_64"
    WHEEL_PLATFORM="macosx_11_0_x86_64"
    ;;
  windows)
    UV_ARCHIVE="uv-x86_64-pc-windows-msvc.zip"
    UV_ARCHIVE_TYPE="zip"
    UV_BIN_NAME="uv-windows.exe"
    WHEEL_PLATFORM="win_amd64"
    IS_WINDOWS=true
    ;;
  *)
    echo "Unknown platform: $PLATFORM"
    echo "Supported: linux, macos-arm64, macos-x86_64, windows"
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

if [ "$UV_ARCHIVE_TYPE" = "tar" ]; then
  curl -fsSL "$UV_BASE/$UV_ARCHIVE" | tar -xz -C "$DIST/uv-bin" --strip-components=1 2>/dev/null \
    && mv "$DIST/uv-bin/uv" "$DIST/uv-bin/$UV_BIN_NAME" \
    && echo "    uv binary: $UV_BIN_NAME" \
    || echo "    WARN: failed to download uv binary for $PLATFORM"
else
  curl -fsSL "$UV_BASE/$UV_ARCHIVE" -o "$DIST/uv-bin/$UV_ARCHIVE" 2>/dev/null \
    && (cd "$DIST/uv-bin" && unzip -qo "$UV_ARCHIVE" uv.exe && mv uv.exe "$UV_BIN_NAME" && rm -f "$UV_ARCHIVE") \
    && echo "    uv binary: $UV_BIN_NAME" \
    || echo "    WARN: failed to download uv binary for $PLATFORM"
fi

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

# Windows: uvicorn[standard] includes uvloop which is Unix-only; strip extras
WIN_DEPS_FILE=$(mktemp)
sed 's/uvicorn\[standard\]/uvicorn/' "$DEPS_FILE" > "$WIN_DEPS_FILE"

if [ "$IS_WINDOWS" = true ]; then
  REQ_FILE="$WIN_DEPS_FILE"
else
  REQ_FILE="$DEPS_FILE"
fi

# Download platform-specific binary wheels
for pyver in 3.10 3.11 3.12 3.13 3.14; do
  abi="cp${pyver//./}"
  echo "    Downloading wheels for $WHEEL_PLATFORM (Python $pyver)..."
  python3 -m pip download \
    -r "$REQ_FILE" \
    -d "$DIST/wheels" \
    --platform "$WHEEL_PLATFORM" \
    --python-version "$pyver" \
    --implementation cp \
    --abi "$abi" \
    --only-binary :all: \
    2>&1 | grep -i "error\|saved" || true
done

# For Unix platforms, also download for host platform (catches deps missed by cross-platform pass)
if [ "$IS_WINDOWS" = false ]; then
  echo "    Downloading wheels for host platform..."
  python3 -m pip download \
    -r "$REQ_FILE" \
    -d "$DIST/wheels" \
    2>/dev/null || true
fi

# Ensure conditional transitive deps are included
# (e.g., tomli is needed by alembic on Python <3.11 but not on 3.12+)
echo "    Downloading conditional dependencies..."
for pkg in "tomli>=2.0.0" "exceptiongroup>=1.0.0" "typing_extensions>=4.0.0"; do
  python3 -m pip download "$pkg" -d "$DIST/wheels" --no-deps 2>/dev/null || true
done

# Save requirements for install scripts
cp "$REQ_FILE" "$DIST/requirements.txt"
rm -f "$DEPS_FILE" "$WIN_DEPS_FILE"
echo "    Wheels: $(ls "$DIST/wheels" | wc -l | tr -d ' ') packages"

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

# Directories (defaults shown — adjust if needed)
# WORKSPACE_DIR=~/.roboscope/workspace
# REPORTS_DIR=~/.roboscope/reports
# VENVS_DIR=~/.roboscope/venvs
ENVEOF

# ── 6. Create platform-specific install/start/stop scripts ───
if [ "$IS_WINDOWS" = false ]; then
  # Unix (Linux / macOS) scripts
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

else
  # Windows scripts
  cat > "$DIST/install-windows.bat" << 'BATEOF'
@echo off
echo ==> Installing RoboScope...

cd /d "%~dp0"

:: Create virtual environment with uv
uv-bin\uv-windows.exe venv .venv

:: Install dependencies offline
uv-bin\uv-windows.exe pip install --python .venv\Scripts\python.exe --no-index --find-links=wheels -r requirements.txt

if not exist .env copy .env.example .env

echo.
echo ==> RoboScope installed successfully!
echo     Start with: start-windows.bat
BATEOF

  cat > "$DIST/start-windows.bat" << 'BATEOF'
@echo off
cd /d "%~dp0"

:: Load port from .env if present
set PORT=8145
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if "%%a"=="PORT" set PORT=%%b
    )
)

:: Check if port is already in use
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo Error: Port %PORT% is already in use.
    echo.
    echo Process using port %PORT%:
    netstat -ano | findstr ":%PORT% " | findstr "LISTENING"
    echo.
    echo Options:
    echo   1. Stop the other process:  stop-windows.bat
    echo   2. Change the port in .env: PORT=9000
    exit /b 1
)

if not exist .venv (
    echo Error: Run install-windows.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat

echo ==> Starting RoboScope...
echo     URL: http://localhost:%PORT%
echo     API: http://localhost:%PORT%/api/v1/docs
echo     Default login: admin@roboscope.local / admin123
echo.

python -m uvicorn src.main:app --host 0.0.0.0 --port %PORT%
BATEOF

  cat > "$DIST/stop-windows.bat" << 'BATEOF'
@echo off
cd /d "%~dp0"

:: Load port from .env if present
set PORT=8145
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if "%%a"=="PORT" set PORT=%%b
    )
)

echo ==> Stopping RoboScope on port %PORT%...

set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo     Stopping PID %%p...
    taskkill /PID %%p /F >nul 2>&1
    set FOUND=1
)

if %FOUND%==0 (
    echo     No process found on port %PORT%.
) else (
    echo     RoboScope stopped.
)
BATEOF
fi

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
if [ "$IS_WINDOWS" = false ]; then
  PLATFORM_DISPLAY="$(echo "$PLATFORM" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
  echo "To deploy on $PLATFORM_DISPLAY:"
  echo "  1. Extract $ZIP_NAME"
  echo "  2. Run ./install-mac-and-linux.sh"
  echo "  3. Run ./start-mac-and-linux.sh"
else
  echo "To deploy on Windows:"
  echo "  1. Extract $ZIP_NAME"
  echo "  2. Run install-windows.bat"
  echo "  3. Run start-windows.bat"
fi
