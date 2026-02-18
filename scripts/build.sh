#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# mateoX — Build script for standalone distribution
#
# Creates a self-contained directory 'dist/mateox/' that can be
# zipped and deployed on any machine with Python 3.12+.
#
# Usage:  ./scripts/build.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/mateox"

echo "==> mateoX Build"
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

# ── 4. Download Python wheels for offline install ─────────────
echo "==> Downloading Python wheels..."
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

# Download platform-specific binary wheels for all targets
for plat in manylinux2014_x86_64 macosx_11_0_arm64 macosx_10_9_x86_64 win_amd64; do
  echo "    Downloading wheels for $plat..."
  python3 -m pip download \
    -r "$DEPS_FILE" \
    -d "$DIST/wheels" \
    --platform "$plat" \
    --python-version 3.12 \
    --implementation cp \
    --abi cp312 \
    --only-binary :all: \
    2>/dev/null || echo "    (some packages skipped for $plat)"
done

# Final pass: download remaining pure-python wheels and any missed deps
echo "    Downloading pure-python wheels..."
python3 -m pip download \
  -r "$DEPS_FILE" \
  -d "$DIST/wheels" \
  2>/dev/null || true

rm -f "$DEPS_FILE"
echo "    Wheels: $(ls "$DIST/wheels" | wc -l | tr -d ' ') packages"

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

# Install wheels offline
pip install --no-index --find-links=wheels wheels/*.whl 2>/dev/null || \
  pip install --no-index --find-links=wheels wheels/*

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

pip install --no-index --find-links=wheels wheels\*

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
zip -r "mateox.zip" mateox/ -x "mateox/.venv/*" "mateox/__pycache__/*"
echo ""
echo "==> Build complete!"
echo "    Distribution: $ROOT/dist/mateox.zip"
echo "    Directory:    $DIST"
echo ""
echo "To deploy:"
echo "  1. Extract mateox.zip"
echo "  2. Run install.sh (Linux/Mac) or install.bat (Windows)"
echo "  3. Run start.sh (Linux/Mac) or start.bat (Windows)"
