#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# RoboScope — Build script for online distribution
#
# Creates a lightweight directory 'dist/roboscope-online/' that
# requires internet access during install (pip downloads from PyPI).
# Much smaller than the offline build (~5 MB vs ~100 MB).
#
# Usage:  ./scripts/build-online-mac-and-linux.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/roboscope-online"

echo "==> RoboScope Build (online)"
echo "    Root: $ROOT"
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

# ── 4. Extract requirements ───────────────────────────────────
echo "==> Extracting requirements..."
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
" > "$DIST/requirements.txt"
echo "    Requirements: $(wc -l < "$DIST/requirements.txt" | tr -d ' ') packages"

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

# ── 6. Create install script ─────────────────────────────────
cat > "$DIST/install-mac-and-linux.sh" << 'INSTALLEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing RoboScope..."

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies from PyPI
pip install -r requirements.txt

# Copy default config if not exists
[ -f .env ] || cp .env.example .env

echo ""
echo "==> RoboScope installed successfully!"
echo "    Start with: ./start-mac-and-linux.sh"
INSTALLEOF
chmod +x "$DIST/install-mac-and-linux.sh"

# ── 7. Create start script ───────────────────────────────────
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

# ── 7b. Create stop script ───────────────────────────────────
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

# ── 8. Create Windows install script ─────────────────────────
cat > "$DIST/install-windows.bat" << 'BATEOF'
@echo off
echo ==> Installing RoboScope...

cd /d "%~dp0"

python -m venv .venv
call .venv\Scripts\activate.bat

pip install -r requirements.txt

if not exist .env copy .env.example .env

echo.
echo ==> RoboScope installed successfully!
echo     Start with: start-windows.bat
BATEOF

# ── 9. Create Windows start script ───────────────────────────
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

# ── 9b. Create Windows stop script ──────────────────────────
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

# ── 10. Create ZIP ───────────────────────────────────────────
echo ""
echo "==> Creating ZIP archive..."
cd "$ROOT/dist"
zip -r "roboscope-online.zip" roboscope-online/ -x "roboscope-online/.venv/*" "roboscope-online/__pycache__/*"
echo ""
echo "==> Build complete!"
echo "    Distribution: $ROOT/dist/roboscope-online.zip"
echo "    Directory:    $DIST"
echo ""
echo "To deploy (requires internet access):"
echo "  1. Extract roboscope-online.zip"
echo "  2. Run install-mac-and-linux.sh (Linux/Mac) or install-windows.bat (Windows)"
echo "  3. Run start-mac-and-linux.sh (Linux/Mac) or start-windows.bat (Windows)"
