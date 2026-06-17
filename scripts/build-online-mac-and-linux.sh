#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# RoboScope — Build script for online distribution
#
# Creates a lightweight directory 'dist/roboscope/' that
# requires internet access during install (pip downloads from PyPI).
# Much smaller than the offline build (~5 MB vs ~100 MB).
#
# Usage:  ./scripts/build-online-mac-and-linux.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/roboscope"

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

# Story HEAL-VENDORED — `robotframework-roboscopeheal>=0.2` is in the
# extracted requirements but is NOT on PyPI yet. The online install
# (which goes straight to PyPI) would 404 on it. Build the wheel from
# the vendored source tree and ship a tiny wheels/ directory alongside
# requirements.txt so the install command can resolve roboscopeheal
# locally via --find-links, while everything else still comes from PyPI.
RFHEAL_VENDOR="$ROOT/backend/vendor/robotframework-roboscopeheal"
if [ -d "$RFHEAL_VENDOR" ]; then
  echo "==> Building robotframework-roboscopeheal wheel from vendor..."
  mkdir -p "$DIST/wheels"
  python3 -m pip install --quiet --upgrade build 2>/dev/null || true
  (cd "$RFHEAL_VENDOR" \
   && python3 -m build --wheel --outdir "$DIST/wheels" 2>&1 \
   | grep -iE "built|error|warn" || true)
  echo "    Wheel: $(ls "$DIST/wheels"/*.whl 2>/dev/null | head -1)"
else
  echo "    WARN: $RFHEAL_VENDOR missing — heal library won't ship with this online bundle." >&2
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

# ── 6. Create install script ─────────────────────────────────
cat > "$DIST/install-mac-and-linux.sh" << 'INSTALLEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing RoboScope..."

# Install uv if not available
if ! command -v uv &>/dev/null; then
  echo "    Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Create virtual environment with uv
uv venv .venv

# Install dependencies. PyPI for everything except the vendored
# robotframework-roboscopeheal wheel that ships in wheels/ — uv resolves
# the local wheel via --find-links and the rest from the public index.
if [ -d wheels ]; then
  uv pip install --python .venv/bin/python --find-links wheels -r requirements.txt
else
  uv pip install --python .venv/bin/python -r requirements.txt
fi

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

:: Install uv if not available
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo     Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

:: Create virtual environment with uv
uv venv .venv

:: Install dependencies. PyPI for everything except the vendored
:: robotframework-roboscopeheal wheel that ships in wheels\ — uv resolves
:: the local wheel via --find-links and the rest from the public index.
:: Without --find-links the install 404s on roboscopeheal (not on PyPI).
if exist wheels\ (
    uv pip install --python .venv\Scripts\python.exe --find-links wheels -r requirements.txt
) else (
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
)

if not exist .env copy .env.example .env

echo.
echo ==> RoboScope installed successfully!
echo     Start with: start-windows.bat
BATEOF

# ── 9. Create Windows start script ───────────────────────────
cat > "$DIST/start-windows.bat" << 'BATEOF'
@echo off
cd /d "%~dp0"

:: Load port + log format from .env if present
set PORT=8145
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if "%%a"=="PORT" set PORT=%%b
        if "%%a"=="LOG_FORMAT" set LOG_FORMAT=%%b
        if "%%a"=="OPEN_BROWSER" set OPEN_BROWSER=%%b
    )
)

:: Default to readable text logs for humans on Windows cmd / PowerShell.
:: Override via .env (LOG_FORMAT=json) for log-shipper integrations.
if not defined LOG_FORMAT set LOG_FORMAT=text

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

python -m uvicorn src.main:app --host 0.0.0.0 --port %PORT% --no-use-colors
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

# ── 9c. Normalise .bat files to CRLF ─────────────────────────
# The heredocs above write LF line endings (this script runs on
# Linux/macOS), but cmd.exe mis-parses LF-only batch files: it loses the
# first token of each line, runs `::` comments as commands, and never
# reaches `uv venv` — so the install silently produces no .venv. Windows
# batch files MUST be CRLF. (The offline build's PowerShell Set-Content
# already emits CRLF; only this bash-generated bundle needed the fix.)
# awk is portable across GNU/BSD; `\r\n` in printf is honoured everywhere.
echo "==> Normalising .bat files to CRLF (cmd.exe requirement)..."
for bat in install-windows.bat start-windows.bat stop-windows.bat; do
  f="$DIST/$bat"
  awk '{ sub(/\r$/, ""); printf "%s\r\n", $0 }' "$f" > "$f.crlf" && mv "$f.crlf" "$f"
done

# ── 10. Create ZIP ───────────────────────────────────────────
echo ""
echo "==> Creating ZIP archive..."
cd "$ROOT/dist"
zip -r "roboscope.zip" roboscope/ -x "roboscope/.venv/*" "roboscope/__pycache__/*"
echo ""
echo "==> Build complete!"
echo "    Distribution: $ROOT/dist/roboscope.zip"
echo "    Directory:    $DIST"
echo ""
echo "To deploy (requires internet access):"
echo "  1. Extract roboscope.zip"
echo "  2. Run install-mac-and-linux.sh (Linux/Mac) or install-windows.bat (Windows)"
echo "  3. Run start-mac-and-linux.sh (Linux/Mac) or start-windows.bat (Windows)"
