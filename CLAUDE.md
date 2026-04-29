# RoboScope — Claude Code Project Guide

Web-based Robot Framework test management tool: Git integration, GUI execution, report analysis, environments, container runtime, AI-assisted spec/test generation, Chrome recorder.

## Architecture (high level)

```
backend/   FastAPI (Python 3.12+) — ~5800 LOC, domain-driven modules
frontend/  Vue 3 + TS + Vite + Pinia — ~5500 LOC, 12 views, 10 stores
e2e/       Playwright — ~1400 LOC, 13 specs, 217 tests green
extension/ Chrome Recorder (Apache-2.0 since RECORDER-LICENSE; HTTP only)
docker/    Dockerfiles (backend, frontend, playwright)
_bmad/     BMAD Method v6 install (bmm + core)
```

Backend modules under `backend/src/`: `auth`, `repos`, `explorer`, `execution`, `environments`, `reports`, `stats`, `ai`, `recording`, `settings`, `plugins`, `websocket`, `api/v1`, plus `task_executor.py`, `encryption.py`, `database.py`, `main.py`.

## Tech stack

- **Backend**: FastAPI · SQLAlchemy 2.0 sync · Pydantic v2 · GitPython · Docker SDK · APScheduler (retention) · PyJWT · bcrypt · Fernet
- **Package mgmt**: [uv](https://docs.astral.sh/uv/) for all venv/pip ops (see `environments/venv_utils.py`). Never call `pip`/`python -m venv` directly.
- **Frontend**: Vue 3.5 · Pinia · Vue Router 4 · Axios · Chart.js · CodeMirror 6 · Vue Flow · js-yaml · vue-i18n v10
- **DB**: SQLite (dev) / PostgreSQL (prod) via `DATABASE_URL`
- **Tests**: pytest (~555) · Vitest · Playwright (217, take-screenshots skipped in CI)
- **No Redis/Celery**: background tasks run via in-process `ThreadPoolExecutor(max_workers=1)` — `task_executor.dispatch_task()`

## Commands

```bash
make install           # deps
make dev               # backend :8000 + frontend :5173
make backend | frontend
make test              # backend + frontend
make test-backend[-cov] | test-frontend[-cov] | test-e2e
make lint | format | typecheck
make docker-dev | docker-up | docker-down | docker-logs
make db-migrate msg="..." | db-upgrade | db-downgrade
```

Manual backend: `cd backend && .venv/bin/python -m uvicorn src.main:app --reload --port 8000`
Single E2E spec: `cd e2e && npx playwright test tests/<name>.spec.ts`

Swagger: `http://localhost:8000/api/v1/docs`

## RBAC

`VIEWER (0) < RUNNER (1) < EDITOR (2) < ADMIN (3)` — `backend/src/auth/constants.py`. API tokens (`rbs_…`, SHA256-hashed) are accepted alongside JWT. Seed admin: `admin@roboscope.local` / `admin123`.

## Critical patterns & gotchas

- **Offline-only**: no CDN/Google Fonts/external imports. All assets bundled locally. Applies to backend AND frontend.
- **`db.commit()` before `dispatch_task()`**: background thread uses a separate sync session and won't see uncommitted data.
- **FK model imports in `tasks.py`**: every task module must `import src.auth.models  # noqa: F401` etc., or FK resolution fails.
- **WebSocket broadcast from bg thread**: never `asyncio.run()`. Use `asyncio.run_coroutine_threadsafe(coro, _event_loop)` where `_event_loop` is captured in `main.py` lifespan. Helpers: `_broadcast_run_status()` (execution), `_broadcast_analysis_status()` (stats).
- **uv, not pip/venv**: all venv ops go through `environments/venv_utils.py` (cross-platform, handles `bin/` vs `Scripts/`). uv is a CLI binary, invoked via subprocess — `UV_PATH` env var or `shutil.which("uv")`.
- **vue-i18n reserved chars**: escape `@ | { }` in translation strings (`admin{'@'}roboscope.local`). Dev mode is lenient; **production build breaks with SyntaxError**. Always test prod build.
- **Secrets encryption**: `src/encryption.py` (Fernet from `SECRET_KEY`). Env variables with `is_secret=True` are encrypted at rest; legacy plaintext still decrypts (graceful).
- **Audit middleware**: all POST/PUT/PATCH/DELETE are auto-logged to `AuditLog` with user/IP/detail.
- **Retention scheduler**: APScheduler (24h) runs `enforce_retention()`. Reports/runs older than `report_retention_days` deleted; manual trigger `POST /audit/retention/run` (ADMIN).
- **Singleton composables + authenticated endpoints = redirect loop risk**: any global-layout composable (e.g. `useBypassStatus`, `useUserSettings`) that polls an authenticated endpoint MUST early-return when `localStorage.getItem('access_token')` is null. Otherwise: Vue momentarily renders DefaultLayout + AppHeader during initial route resolution even on `/login`, the composable fires its fetch, gets 401, the axios interceptor does `window.location.href = '/login'`, and you loop. The interceptor also checks `window.location.pathname === '/login'` and skips the reload when already there — both guards are required; dropping either one brings the flicker back. Regression seen during Phase 4 Story 5-2 dev; fix committed 2026-04-22.
- **Axios 401 interceptor** (`frontend/src/api/client.ts`): never call `window.location.href = '/login'` unconditionally — always gate on `window.location.pathname !== '/login'` to avoid the loop above.
- **SSE connection state must flip on `open`, not on first message**: `RecordingLiveView` initially only transitioned `streamState` from `connecting → live` inside the `command` handler. Sessions where the user didn't interact with the recorded page kept the UI on "Verbinde…" indefinitely even though the stream was healthy, which also kept the Stop-and-Save button disabled (it was gated on `commands.length`). Fix: add an `open` listener that sets `streamState = 'live'`, and gate the Stop-and-Save button on `saving` only (never require captured commands — the user must always be able to abort). Regression caught during live recorder-v2 testing 2026-04-22.
- **Auto-fixing test code requires the SH-2 opt-in contract**: the runtime self-healing library `src/recording/heal/` lives behind explicit keyword opt-in — users write `Heal Click` to consent, `Click` is untouched. Three invariants any future "auto-fix test code" feature must honour: (1) **explicit per-keyword opt-in** (no monkey-patching the Browser library globally), (2) **never mutate `.robot` on disk at runtime** (heals are suggestions, the diff surfaces in the run panel for manual review + accept), (3) **suspect-heal classification** — a heal whose test ultimately failed must not offer a "Copy patch" affordance. The `no-heal` Robot tag is the per-test escape hatch; budgets + confidence thresholds gate every swap. Breaking any of these invariants reopens the silent-wrong-click failure mode.
- **Backend-launched Playwright is not remote-friendly**: `v2_recorder_task.py` opens Chromium *on the backend host* with `headless=False`. On a headless Linux server (typical team deployment) that fails or opens a window on the server's desktop — the user's browser sees the SSE stream but no viewable session. Any new "backend opens a browser" feature (Story W.* successors, a future pooled-browser service, anything using Playwright headed mode) MUST consult `GET /api/v1/recordings/sessions/capabilities` and hide / disable itself when `web_playwright_viable=false`. The launcher already does this since Story DEPLOY-1. The viability check reads `ROBOSCOPE_HEADED_BROWSER` (override) and then `$DISPLAY` / `$WAYLAND_DISPLAY` on Linux. Chrome Extension path is the remote-friendly alternative — it posts from the user's browser to the backend endpoints in `/api/v1/recordings/{id}/*`.

## Key API prefixes (`/api/v1/…`)

`/auth` · `/repos` · `/explorer/{repo_id}` · `/runs` + `/schedules` · `/environments` · `/reports` · `/stats` (+ `/stats/analysis`) · `/settings` · `/ai` · `/recordings` · `/webhooks` (tokens, hooks, inbound git) · `/audit`

## Config (essentials)

| Env | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | `sqlite:///./roboscope.db` | DB |
| `SECRET_KEY` | dev-key (warns at startup) | JWT + Fernet |
| `RUNNER_TYPE` | `auto` | subprocess/docker/auto |
| `DOCKER_AVAILABLE` | `false` | enable docker runner |
| `DEFAULT_TIMEOUT_SECONDS` | `3600` | per run |
| `WORKSPACE_DIR` / `REPORTS_DIR` / `VENVS_DIR` | `~/.roboscope/…` | storage |
| `UV_PATH` | `""` | override uv binary |

## Coding conventions

- Python 3.12+, Ruff line-length 100, mypy strict, sync SQLAlchemy.
- TypeScript strict, Vue 3 `<script setup>`, Pinia stores.
- CSS vars centralized in `frontend/src/assets/styles/main.css`. Brand: `--color-primary:#3B7DD8`, `--color-accent:#D4883E`, `--color-navy:#1A2D50`.
- i18n complete in EN/DE/FR/ES (app + in-app docs). Every user-facing string must have 4 locale entries.
- Conventional commits; PR-based.

## Milestone: Enterprise-Readiness (current)

Done: Phase 1 CI/CD (API tokens, webhooks, git-trigger) · Phase 2 Audit/Compliance (audit log, retention, secrets encryption) · Phase 3 Visual Flow Editor (Vue Flow).

Open:
- **Phase 4 — Auth**: OAuth2/SSO (Azure AD, Google, GitHub); SAML 2.0; Team/Org model with inherited roles.
- **Phase 5 — Scale/Reporting**: CSV/JSON/PDF export; distributed execution (N workers, remote agents, K8s runner plugin); Prometheus `/metrics`.
- **Phase 6 — Quality**: saved run templates; Jira plugin; Helm chart.
- **Polish**: general UI refinements (loaders, error/empty states).

Known open issues: a11y gaps (broad — keyboard nav, ARIA labels, focus traps in modals); long-tail of 65 `: any` annotations remain (mostly `catch (e: any)` idioms; zero `as any` casts).

Already addressed (kept for history so future audits don't re-discover them): `/reports/{id}/assets/` requires `?at=<HMAC token>` OR JWT (REPORT-1 + SECURITY-3); upload-size limits stream-checked at 500MB with Content-Length pre-check (ROBUSTNESS-1); JWT-in-URL replaced by short-lived asset tokens (SECURITY-3); docs lazy-loaded per locale + lazy route (PERF-1); JSON logging via `pythonjsonlogger.JsonFormatter` in `main.py`; deep `/health` check (DB SELECT 1 + 503 on outage, regression-tested); backend datetime UTC normalization (`UtcJSONResponse` + frontend `parseBackendDate`); XXE hardening on `output.xml` parsing (`defusedxml`); Windows shell-injection in Open-In-Editor (`os.startfile` instead of `cmd /c start` with shell=True); Docker client consolidation (REFACTOR-1 — single `src/docker_client.py`); default-credentials probe is banner-only (force-change walked back per user feedback).

Test gaps (highest risk): SubprocessRunner / DockerRunner, `execute_test_run()`, AI LLM client + encryption, WebSocket manager, TaskExecutor, several AI + Report router endpoints.

## BMAD integration

BMAD Method v6 (`bmm` + `core`) installed at `_bmad/`. 41 skills registered in `.claude/skills/bmad-*`. Output folder: `_bmad-output/`.

Recommended agents for RoboScope work:

| Agent / Skill | When to invoke |
|---|---|
| **bmad-agent-architect** (Winston) | Phase 4 (SSO/SAML/Teams) and Phase 5 (distributed exec, K8s) solution design |
| **bmad-agent-pm** (John) | Turning open roadmap items into PRDs (`bmad-create-prd`, `bmad-edit-prd`) |
| **bmad-agent-dev** (Amelia) / `bmad-dev-story` | Implementing a story spec file end-to-end |
| **bmad-quick-dev** | Small fixes from the "known open issues" list |
| **bmad-agent-analyst** (Mary) | Requirements discovery for Team/Multi-tenancy and Jira integration |
| **bmad-agent-ux-designer** (Sally) / `bmad-create-ux-design` | UI polish phase, empty/error states, mobile responsiveness |
| **bmad-agent-tech-writer** (Paige) | Keeping in-app docs (EN/DE/FR/ES) and README aligned with new features |
| **bmad-create-architecture** | Before Phase 4/5 kickoff |
| **bmad-create-epics-and-stories** | Decomposing Phase 4/5/6 into sprint-ready stories |
| **bmad-create-story** / **bmad-sprint-planning** / **bmad-sprint-status** | Per-story and per-sprint workflow |
| **bmad-check-implementation-readiness** | Gate before starting a phase |
| **bmad-code-review** / **bmad-review-adversarial-general** / **bmad-review-edge-case-hunter** | Pre-merge review; adversarial pass on security items (asset auth, upload limits) |
| **bmad-qa-generate-e2e-tests** | Close test gaps (SubprocessRunner, WebSocket, AI endpoints) |
| **bmad-retrospective** | After each phase ships |
| **bmad-document-project** | Refresh brownfield context once Phase 4 lands |
| **bmad-help** | When unsure which skill fits |

Typical flow for a new phase: `bmad-agent-pm` → `bmad-create-prd` → `bmad-agent-architect` → `bmad-create-architecture` → `bmad-create-epics-and-stories` → `bmad-check-implementation-readiness` → `bmad-create-story` → `bmad-dev-story` → `bmad-qa-generate-e2e-tests` → `bmad-code-review` → `bmad-retrospective`.
