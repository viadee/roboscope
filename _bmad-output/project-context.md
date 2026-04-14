---
project_name: 'roboscope'
user_name: 'Thomas'
date: '2026-04-14'
sections_completed: ['technology_stack']
existing_patterns_found: 0
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

_Populated during discovery. Full rules follow in step 2._

### Backend (Python ≥3.11, target py312)
- FastAPI ≥0.115 · Uvicorn[standard] ≥0.32
- SQLAlchemy 2.0 (sync) ≥2.0.36 · greenlet ≥3.1 · Alembic ≥1.14
- Pydantic ≥2.10 · pydantic-settings ≥2.6
- PyJWT ≥2.9 · bcrypt ≥4.2 · cryptography ≥43 (Fernet)
- GitPython ≥3.1.43 · robotframework ≥7.1 · rf-mcp ≥0.30 · fastmcp <3
- APScheduler ≥3.10.4 · websockets ≥14.1 · httpx ≥0.28 · slowapi ≥0.1.9
- python-json-logger ≥3.0 · playwright ≥1.49 · robotframework-roboview ≥0.0.4
- Optional: psycopg2-binary (postgres), docker (Docker runner)
- Dev: pytest ≥8.3 · pytest-asyncio ≥0.24 · pytest-cov ≥6 · factory-boy ≥3.3 · ruff ≥0.8 · mypy ≥1.13 · pre-commit ≥4
- Ruff: line-length 100, py312, rules E/W/F/I/N/UP/B/C4/SIM
- mypy: strict, py312
- Package mgmt: **uv** (external CLI) — never pip/venv directly

### Frontend (Vue 3.5 · TS strict · Vite 7)
- vue ^3.5 · pinia ^2.2 · vue-router ^4.4 · vue-i18n ^10.0.8
- axios ^1.7 · chart.js ^4.4 · vue-chartjs ^5.3
- @vue-flow/core ^1.48 + background/controls/minimap (visual flow editor)
- codemirror 6 family (@codemirror/state/view/language + @codemirror/lang-python) · @lezer/highlight ^1.2
- js-yaml ^4.1.1 · driver.js ^1.4 (guided tour)
- vitest ^4.0.18 · @vue/test-utils ^2.4 · jsdom ^25
- typescript ~5.5 · vue-tsc ^2.1
- npm overrides: minimatch ≥10.2.1, editorconfig ≥2.0.0 (ReDoS fix)

### E2E (Playwright ^1.48)
- `e2e/` workspace with page objects, auth fixture (JWT injection), API mocking via `page.route()`
- 13 specs, 217 tests; `take-screenshots.spec.ts` skipped in CI

### Tooling / Runtime
- Python 3.12+ · Node 20+ · uv CLI (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- SQLite (dev default) or PostgreSQL (prod) via `DATABASE_URL`
- Docker optional (runner + compose for dev/prod/test)
- No Redis, no Celery — all background work via in-process `ThreadPoolExecutor(max_workers=1)`

---

## Critical Implementation Rules

_Populated in step 2._
