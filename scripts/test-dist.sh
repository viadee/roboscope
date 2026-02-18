#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# mateoX — Distribution smoke test
#
# Builds the dist (online or offline), starts the server,
# and runs HTTP-based E2E checks to verify everything works.
#
# Usage:
#   ./scripts/test-dist.sh              # test offline dist
#   ./scripts/test-dist.sh online       # test online dist
#   ./scripts/test-dist.sh --skip-build # test existing dist without rebuilding
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="offline"
SKIP_BUILD=false
PORT=8199
PASSED=0
FAILED=0
WARNINGS=0

for arg in "$@"; do
  case "$arg" in
    online) MODE="online" ;;
    --skip-build) SKIP_BUILD=true ;;
  esac
done

if [ "$MODE" = "online" ]; then
  DIST="$ROOT/dist/mateox-online"
  BUILD_SCRIPT="$ROOT/scripts/build-online.sh"
else
  DIST="$ROOT/dist/mateox"
  BUILD_SCRIPT="$ROOT/scripts/build.sh"
fi

BASE_URL="http://127.0.0.1:$PORT"
SERVER_PID=""

# ── Helpers ─────────────────────────────────────────────────

cleanup() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

pass() {
  echo "  ✓ $1"
  PASSED=$((PASSED + 1))
}

fail() {
  echo "  ✗ $1"
  FAILED=$((FAILED + 1))
}

warn() {
  echo "  ⚠ $1"
  WARNINGS=$((WARNINGS + 1))
}

check_http() {
  local desc="$1"
  local url="$2"
  local expect_code="${3:-200}"
  local expect_contains="${4:-}"

  local response
  response=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null) || { fail "$desc — connection refused"; return; }

  local http_code
  http_code=$(echo "$response" | tail -1)
  local body
  body=$(echo "$response" | sed '$d')

  if [ "$http_code" != "$expect_code" ]; then
    fail "$desc — expected HTTP $expect_code, got $http_code"
    return
  fi

  if [ -n "$expect_contains" ]; then
    if echo "$body" | grep -q "$expect_contains"; then
      pass "$desc (HTTP $http_code)"
    else
      fail "$desc — response missing '$expect_contains'"
    fi
  else
    pass "$desc (HTTP $http_code)"
  fi
}

check_http_size() {
  local desc="$1"
  local url="$2"
  local min_bytes="${3:-1}"

  local size
  size=$(curl -s -o /dev/null -w "%{size_download}" "$url" 2>/dev/null) || { fail "$desc — connection refused"; return; }
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)

  if [ "$code" != "200" ]; then
    fail "$desc — HTTP $code"
    return
  fi

  if [ "$size" -ge "$min_bytes" ]; then
    pass "$desc (HTTP 200, ${size} bytes)"
  else
    fail "$desc — only ${size} bytes (expected >= ${min_bytes})"
  fi
}

# ── 1. Build ────────────────────────────────────────────────

echo "==> mateoX Distribution Test ($MODE)"
echo "    Root: $ROOT"
echo "    Dist: $DIST"
echo "    Port: $PORT"
echo ""

if [ "$SKIP_BUILD" = false ]; then
  echo "==> Step 1: Building distribution..."
  bash "$BUILD_SCRIPT"
  echo ""
else
  echo "==> Step 1: Skipping build (--skip-build)"
  echo ""
fi

# ── 2. Verify dist contents ────────────────────────────────

echo "==> Step 2: Checking dist contents..."

[ -d "$DIST" ] && pass "dist directory exists" || { fail "dist directory missing"; echo "ABORT"; exit 1; }
[ -d "$DIST/src" ] && pass "src/ directory" || fail "src/ missing"
[ -f "$DIST/src/main.py" ] && pass "src/main.py" || fail "src/main.py missing"
[ -d "$DIST/frontend_dist" ] && pass "frontend_dist/ directory" || fail "frontend_dist/ missing"
[ -f "$DIST/frontend_dist/index.html" ] && pass "frontend_dist/index.html" || fail "index.html missing"
[ -d "$DIST/frontend_dist/assets" ] && pass "frontend_dist/assets/" || fail "assets/ missing"
[ -f "$DIST/requirements.txt" ] && pass "requirements.txt" || fail "requirements.txt missing"
[ -f "$DIST/install.sh" ] && pass "install.sh" || fail "install.sh missing"
[ -f "$DIST/start.sh" ] && pass "start.sh" || fail "start.sh missing"
[ -f "$DIST/install.bat" ] && pass "install.bat" || fail "install.bat missing"
[ -f "$DIST/start.bat" ] && pass "start.bat" || fail "start.bat missing"
[ -f "$DIST/.env.example" ] && pass ".env.example" || fail ".env.example missing"
[ -f "$DIST/pyproject.toml" ] && pass "pyproject.toml" || fail "pyproject.toml missing"
[ -f "$DIST/README.md" ] && pass "README.md" || fail "README.md missing"

if [ "$MODE" = "offline" ]; then
  [ -d "$DIST/wheels" ] && pass "wheels/ directory" || fail "wheels/ missing"
  wheel_count=$(ls "$DIST/wheels/"*.whl 2>/dev/null | wc -l | tr -d ' ')
  [ "$wheel_count" -gt 0 ] && pass "wheels: $wheel_count .whl files" || fail "no .whl files in wheels/"
fi

if [ -d "$DIST/examples" ]; then
  pass "examples/ directory"
else
  warn "examples/ directory missing (optional)"
fi

if [ -d "$DIST/migrations" ]; then
  pass "migrations/ directory"
else
  warn "migrations/ missing (optional)"
fi

# Check index.html references assets that exist
js_file=$(grep -o 'src="/assets/[^"]*' "$DIST/frontend_dist/index.html" | head -1 | sed 's|src="/assets/||')
css_file=$(grep -o 'href="/assets/[^"]*' "$DIST/frontend_dist/index.html" | head -1 | sed 's|href="/assets/||')

if [ -n "$js_file" ] && [ -f "$DIST/frontend_dist/assets/$js_file" ]; then
  pass "JS bundle exists: $js_file ($(wc -c < "$DIST/frontend_dist/assets/$js_file" | tr -d ' ') bytes)"
else
  fail "JS bundle missing or not referenced in index.html"
fi

if [ -n "$css_file" ] && [ -f "$DIST/frontend_dist/assets/$css_file" ]; then
  pass "CSS bundle exists: $css_file ($(wc -c < "$DIST/frontend_dist/assets/$css_file" | tr -d ' ') bytes)"
else
  fail "CSS bundle missing or not referenced in index.html"
fi

echo ""

# ── 3. Install (create venv + deps) ────────────────────────

echo "==> Step 3: Installing dependencies..."
cd "$DIST"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  pass "venv created"
else
  pass "venv already exists"
fi

source .venv/bin/activate

if [ "$MODE" = "offline" ]; then
  pip install --no-index --find-links=wheels -r requirements.txt -q 2>&1 | tail -3
else
  pip install -r requirements.txt -q 2>&1 | tail -3
fi
pass "pip install completed"

# Verify key packages are importable
python3 -c "import fastapi; print(f'  ✓ fastapi {fastapi.__version__}')"
python3 -c "import uvicorn; print(f'  ✓ uvicorn {uvicorn.__version__}')"
python3 -c "import sqlalchemy; print(f'  ✓ sqlalchemy {sqlalchemy.__version__}')"
python3 -c "import pydantic; print(f'  ✓ pydantic {pydantic.__version__}')"

# Verify our app imports cleanly
python3 -c "
import sys
sys.path.insert(0, '.')
from src.main import app
print(f'  ✓ src.main:app imported ({len(app.routes)} routes)')
" || fail "app import failed"

echo ""

# ── 4. Start server ────────────────────────────────────────

echo "==> Step 4: Starting server on port $PORT..."

# Remove stale DB so we get a clean seed
rm -f "$DIST/mateox.db"

python3 -m uvicorn src.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!

# Wait for server to be ready (max 15 seconds)
for i in $(seq 1 30); do
  if curl -s -o /dev/null "$BASE_URL/health" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

if curl -s -o /dev/null "$BASE_URL/health" 2>/dev/null; then
  pass "server started (PID $SERVER_PID)"
else
  fail "server failed to start within 15 seconds"
  echo ""
  echo "==> ABORT: Cannot continue without running server."
  echo ""
  exit 1
fi

echo ""

# ── 5. HTTP smoke tests ────────────────────────────────────

echo "==> Step 5: HTTP smoke tests..."

# Health check
check_http "GET /health" "$BASE_URL/health" 200 '"status":"healthy"'

# Frontend: root serves index.html
check_http "GET / (SPA root)" "$BASE_URL/" 200 '<div id="app">'

# Frontend: JS bundle
check_http_size "GET /assets/$js_file (JS bundle)" "$BASE_URL/assets/$js_file" 10000

# Frontend: CSS bundle
check_http_size "GET /assets/$css_file (CSS bundle)" "$BASE_URL/assets/$css_file" 1000

# Frontend: favicon
check_http_size "GET /favicon.ico" "$BASE_URL/favicon.ico" 100

# SPA routing: unknown path returns index.html (not 404)
check_http "GET /login (SPA route)" "$BASE_URL/login" 200 '<div id="app">'
check_http "GET /dashboard (SPA route)" "$BASE_URL/dashboard" 200 '<div id="app">'

# API: OpenAPI docs
check_http "GET /api/v1/docs (Swagger)" "$BASE_URL/api/v1/docs" 200 "swagger"

echo ""

# ── 6. API tests ────────────────────────────────────────────

echo "==> Step 6: API tests..."

# Login
login_response=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@mateox.local","password":"admin123"}')

if echo "$login_response" | grep -q "access_token"; then
  pass "POST /api/v1/auth/login (admin login)"
  TOKEN=$(echo "$login_response" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
else
  fail "POST /api/v1/auth/login — no access_token in response"
  TOKEN=""
fi

if [ -n "$TOKEN" ]; then
  AUTH_HEADER="Authorization: Bearer $TOKEN"

  # Get current user (needs auth header)
  me_response=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v1/auth/me")
  if echo "$me_response" | grep -q "admin@mateox.local"; then
    pass "GET /api/v1/auth/me (authenticated)"
  else
    fail "GET /api/v1/auth/me — unexpected response"
  fi

  # List repos (should have seeded "Examples")
  repos_response=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v1/repos")
  if echo "$repos_response" | grep -q "Examples"; then
    pass "GET /api/v1/repos (seeded Examples project found)"
  else
    warn "GET /api/v1/repos — Examples project not found (may not have seeded)"
  fi

  # List environments
  envs_code=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/environments")
  [ "$envs_code" = "200" ] && pass "GET /api/v1/environments (HTTP $envs_code)" || fail "GET /api/v1/environments (HTTP $envs_code)"

  # List runs
  runs_code=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/runs")
  [ "$runs_code" = "200" ] && pass "GET /api/v1/runs (HTTP $runs_code)" || fail "GET /api/v1/runs (HTTP $runs_code)"

  # List reports
  reports_code=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/reports")
  [ "$reports_code" = "200" ] && pass "GET /api/v1/reports (HTTP $reports_code)" || fail "GET /api/v1/reports (HTTP $reports_code)"

  # Stats overview
  stats_code=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/stats/overview")
  [ "$stats_code" = "200" ] && pass "GET /api/v1/stats/overview (HTTP $stats_code)" || fail "GET /api/v1/stats/overview (HTTP $stats_code)"

  # Settings (admin only)
  settings_code=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/settings")
  [ "$settings_code" = "200" ] && pass "GET /api/v1/settings (HTTP $settings_code)" || fail "GET /api/v1/settings (HTTP $settings_code)"

  # WebSocket endpoint exists (upgrade required = 403 without upgrade)
  ws_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/ws/notifications")
  if [ "$ws_code" = "403" ] || [ "$ws_code" = "426" ]; then
    pass "GET /ws/notifications (HTTP $ws_code — expected, needs WebSocket upgrade)"
  else
    warn "GET /ws/notifications (HTTP $ws_code — unexpected)"
  fi

  # Invalid login should fail
  bad_login=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"bad@bad.com","password":"wrongpassword"}')
  [ "$bad_login" = "401" ] && pass "POST /api/v1/auth/login (bad creds → HTTP 401)" || fail "Bad login returned HTTP $bad_login (expected 401)"

  # Unauthenticated access should be rejected
  unauth_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/auth/me")
  [ "$unauth_code" = "401" ] && pass "GET /api/v1/auth/me (no token → HTTP 401)" || fail "Unauthenticated access returned HTTP $unauth_code (expected 401)"

fi

echo ""

# ── 7. Summary ──────────────────────────────────────────────

echo "════════════════════════════════════════════════════════"
echo "  Results: $PASSED passed, $FAILED failed, $WARNINGS warnings"
echo "  Python:  $(python3 --version)"
echo "  Mode:    $MODE"
echo "════════════════════════════════════════════════════════"

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "  SOME TESTS FAILED"
  exit 1
else
  echo ""
  echo "  ALL TESTS PASSED"
  exit 0
fi
