#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# mateoX — Build script for online distribution
#
# Creates a lightweight directory 'dist/mateox-online/' that
# requires internet access during install (pip downloads from PyPI).
# Much smaller than the offline build (~5 MB vs ~100 MB).
#
# Usage:  ./scripts/build-online.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/mateox-online"

echo "==> mateoX Build (online)"
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
# mateoX Configuration
# Copy this to .env and adjust as needed.

# Database (SQLite default — no setup required)
DATABASE_URL=sqlite+aiosqlite:///./mateox.db

# Secret key for JWT tokens (change in production!)
SECRET_KEY=CHANGE-ME-IN-PRODUCTION

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Logging
LOG_LEVEL=INFO

# Directories (defaults shown — adjust if needed)
# WORKSPACE_DIR=~/.mateox/workspace
# REPORTS_DIR=~/.mateox/reports
# VENVS_DIR=~/.mateox/venvs
ENVEOF

# ── 6. Create install script ─────────────────────────────────
cat > "$DIST/install.sh" << 'INSTALLEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing mateoX..."

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies from PyPI
pip install -r requirements.txt

# Copy default config if not exists
[ -f .env ] || cp .env.example .env

echo ""
echo "==> mateoX installed successfully!"
echo "    Start with: ./start.sh"
INSTALLEOF
chmod +x "$DIST/install.sh"

# ── 7. Create start script ───────────────────────────────────
cat > "$DIST/start.sh" << 'STARTEOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present
if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

# Activate venv
if [ -d ".venv" ]; then
  source .venv/bin/activate
else
  echo "Error: Run ./install.sh first."
  exit 1
fi

echo "==> Starting mateoX..."
echo "    URL: http://localhost:${PORT:-8000}"
echo "    API: http://localhost:${PORT:-8000}/api/v1/docs"
echo "    Default login: admin@mateox.local / admin123"
echo ""

python -m uvicorn src.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
STARTEOF
chmod +x "$DIST/start.sh"

# ── 8. Create Windows install script ─────────────────────────
cat > "$DIST/install.bat" << 'BATEOF'
@echo off
echo ==> Installing mateoX...

cd /d "%~dp0"

python -m venv .venv
call .venv\Scripts\activate.bat

pip install -r requirements.txt

if not exist .env copy .env.example .env

echo.
echo ==> mateoX installed successfully!
echo     Start with: start.bat
BATEOF

# ── 9. Create Windows start script ───────────────────────────
cat > "$DIST/start.bat" << 'BATEOF'
@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Error: Run install.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat

echo ==> Starting mateoX...
echo     URL: http://localhost:8000
echo     API: http://localhost:8000/api/v1/docs
echo     Default login: admin@mateox.local / admin123
echo.

python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
BATEOF

# ── 10. Create ZIP ───────────────────────────────────────────
echo ""
echo "==> Creating ZIP archive..."
cd "$ROOT/dist"
zip -r "mateox-online.zip" mateox-online/ -x "mateox-online/.venv/*" "mateox-online/__pycache__/*"
echo ""
echo "==> Build complete!"
echo "    Distribution: $ROOT/dist/mateox-online.zip"
echo "    Directory:    $DIST"
echo ""
echo "To deploy (requires internet access):"
echo "  1. Extract mateox-online.zip"
echo "  2. Run install.sh (Linux/Mac) or install.bat (Windows)"
echo "  3. Run start.sh (Linux/Mac) or start.bat (Windows)"
