---
project_name: 'roboscope'
user_name: 'Thomas'
date: '2026-04-14'
sections_completed:
  ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
status: 'complete'
rule_count: 202
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns AI agents must follow when implementing code in this project. Only what's NOT derivable from `pyproject.toml` / `package.json`. Source of truth for deps is always the manifests; this file explains **why** choices were made and **what breaks** when ignored._

---

## Technology Stack — Invariants, Trap Doors, and Idioms

### Do-Not-Upgrade Pins (each one is load-bearing)

- **`fastmcp >=3.2.4,<4`** — security floor + major guard. Pulled in transitively via `rf-mcp` (≥0.31.2, which runs on fastmcp 3.x). `>=3.2.4` closes 3 fastmcp 2.x CVEs and skips the 3.0.0–3.2.3 auth-header-leak window (issue #35); `<4` keeps an untested fastmcp 4.0 out of fresh-resolution builds (CI/Docker/offline bundle install from `pyproject.toml`, not `uv.lock`) while still allowing every 3.x security update. RoboScope never imports `fastmcp` directly — it talks to `rf-mcp` as an out-of-process HTTP server (`src/ai/rf_mcp_manager.py`), so the protocol boundary, not the fastmcp API, is what matters. Do NOT re-pin to `<3` (re-opens the CVEs).
- **`vue-i18n ^10`** — v11 rewrote the message compiler. Reserved chars (`@ | { }`) must be escaped (`admin{'@'}roboscope.local`). Dev build is lenient; **prod bundle fails silently** — component renders blank. Always test prod build for i18n changes.
- **`pinia ^2`, `vue-router ^4`, `vue ^3.5`** — not upgraded to pinia 3 / vue-router 5 / vue 3.6 until explicit decision; treat as pinned.
- **`typescript ~5.5`** — locked on minor; `vue-tsc` + Vite plugin compat. Do not bump to 5.6+.
- **`bcrypt ≥4.2`** — migrated from `passlib`. Agents reflexively add passlib back; don't. Direct `bcrypt.hashpw` / `bcrypt.checkpw` in `src/auth/service.py`.
- **`PyJWT`** — migrated from `python-jose`. Don't reintroduce jose.
- **`minimatch ≥10.2.1`, `editorconfig ≥2.0.0`** (npm overrides) — ReDoS CVE fix. Don't remove.

### Architectural Invariants (not perf knobs)

- **`ThreadPoolExecutor(max_workers=1)` in `backend/src/task_executor.py`** — serializes test runs to prevent workspace/venv contention. **This is correctness, not throughput.** Do not "optimize" to N; distributed execution is a separate roadmap phase.
- **FastAPI + SQLAlchemy 2.0 are used in SYNC mode.** Route handlers are `def`, not `async def`. `Session` is sync. Never introduce `AsyncSession`, `asyncpg`, or `async def` handlers — the session lifecycle + `dispatch_task()` contract both assume sync. Exception: the single `_event_loop` captured in `main.py` lifespan for WebSocket I/O.
- **No Redis, no Celery.** All background work via `task_executor.dispatch_task()`. Always `db.commit()` **before** dispatch — the bg thread uses a separate session and won't see uncommitted rows.
- **WebSocket broadcast from background threads** must use `asyncio.run_coroutine_threadsafe(coro, _event_loop)`. Never `asyncio.run()` — that creates a new loop and fails. Helpers: `_broadcast_run_status()` (execution), `_broadcast_analysis_status()` (stats).
- **FK resolution in every `tasks.py`**: background modules must `import src.auth.models  # noqa: F401`, `import src.repos.models  # noqa: F401`, etc. Missing imports → `NoReferencedTableError` at query time.
- **Fernet key derives from `SECRET_KEY`.** Rotating `SECRET_KEY` orphans all encrypted env variables. Legacy plaintext still decrypts (graceful degradation) — don't remove that fallback.
- **Offline-first.** No CDN, no Google Fonts, no external CSS/JS imports. System font stack only. This applies to frontend AND backend (no remote model downloads, etc.). Every dependency choice must survive an air-gapped install.

### Package Management — uv only

- `uv` is an **external CLI binary**, not a Python package. `pip install uv` is wrong — agents try this.
- All venv/pip operations go through `backend/src/environments/venv_utils.py` (cross-platform `bin/` vs `Scripts/`, uv subprocess wrappers).
- Never call `python -m venv`, `pip install`, `pip list` directly. Never hand-roll venv paths.
- `UV_PATH` env var overrides binary location; fallback is `shutil.which("uv")`.

### Idioms Agents Reach For But Shouldn't

- `requests` / `urllib` / `openai` SDK → use **`httpx`** (the LLM client in `src/ai/llm_client.py` is unified httpx for OpenAI / Anthropic / OpenRouter / Ollama).
- `rate-limit` decorators / custom middleware on login → **slowapi** is already wired; configure it, don't replace it.
- Spinning up a new `create_engine` per module → use `get_sync_session()` from `src/database.py` (consolidated from 7 duplicate engines — don't recreate them).
- Vue Options API, Vuex, multiple Pinia singletons → **Composition API + `<script setup>`**, Pinia stores only.
- `<link rel="stylesheet" href="https://fonts.googleapis.com/...">` or any CDN import → **forbidden** (offline rule).
- Emoji in code, docs, or UI → **forbidden** unless the user explicitly asks.

### Source of Truth for Versions

Read `backend/pyproject.toml` and `frontend/package.json` directly when the exact version matters. Runtime requirements (Python ≥3.11, Node 20+, uv CLI) are in `CLAUDE.md` and `README.md`. Ruff / mypy / Vitest / Playwright configs live next to their code — `make lint` / `make typecheck` / `make test-e2e` enforce them; don't re-document rule lists here.

---

## Critical Implementation Rules

### Language-Specific Rules

**Python (backend)**
- Handlers and service functions are **sync**, not `async def`. The only `async` context is WebSocket I/O via `_event_loop` captured in `main.py` lifespan. Adding `async def` to a route forces rewriting the session + `dispatch_task()` contract.
- Imports: `known-first-party=["src"]` — internal imports use the `src.` prefix (`from src.auth.models import User`). No relative cross-module imports.
- Datetime: `datetime.now(timezone.utc)`. Never `datetime.utcnow()` (deprecated in 3.12).
- Exceptions: no bare `except:`; catch the narrowest class. `TaskDispatchError` is the canonical failure type for background dispatch — catch at the route layer and set `run.status = ERROR` with a user-visible message.
- DB sessions: routes inject via `Depends(get_db)`. Background tasks open a fresh session with `get_sync_session()` in a `with` block. Never share a session across threads. Never `create_engine()` in a module (7 duplicates consolidated — don't recreate).
- Passwords: `bcrypt.hashpw(password.encode(), bcrypt.gensalt())` / `bcrypt.checkpw`. Not passlib.
- JWT: `jwt.encode` / `jwt.decode` from `PyJWT`. Not python-jose.
- Encryption: `src/encryption.py` `encrypt_value()` / `decrypt_value()`. Keep the legacy plaintext fallback on read paths — it's graceful degradation for pre-encryption data.
- Logging: `python-json-logger` structured JSON; `logging.getLogger(__name__)` elsewhere. No `print()`.
- Comments: only when the *why* is non-obvious. Don't explain what well-named code already says. No multi-line docstring blocks on routine functions.

**TypeScript (frontend)**
- `<script setup lang="ts">` Composition API only. No Options API. No `defineComponent()` wrappers.
- State: Pinia stores at `src/stores/<domain>.store.ts`. No Vuex, no module-level singletons.
- API: Axios clients at `src/api/<domain>.api.ts` (JWT interceptor pre-configured). Don't `fetch()` directly.
- Strict TS is on. **Zero new `as any` casts** — 55+ legacy cases are debt, not precedent. Use generics, discriminated unions, or `unknown` + type guards.
- Types split: `src/types/api.types.ts` (wire DTOs) vs `src/types/domain.types.ts` (client-rich models). New endpoints → add both, keep them in sync.
- i18n: every user-visible string needs EN + DE + FR + ES entries in `src/i18n/locales/*.ts` AND matching docs in `src/docs/content/*.ts`. Escape `@ | { }` in message bodies. **Test the prod build** — dev is lenient; prod fails silently.
- Router guards in `src/router/` enforce RBAC. Don't set `meta: { public: true }` unless the route is genuinely public (login, imprint).
- Composables at `src/composables/` for cross-component reactive logic (`useWebSocket`, `useToast`). Prefer composables over ad-hoc `ref()` in components.
- CSS vars centralized in `src/assets/styles/main.css`. Reference `var(--color-…)` — no inline hex in components. No separate variables or transition files.
- Import alias `@/` = `src/`. No deep relative paths, no reaching into `node_modules/`.

_Ruff / mypy / vue-tsc / ESLint enforce the rest (`make lint` / `make typecheck`). Rules are not re-documented here — read the configs._

### Framework-Specific Rules

**FastAPI — ship-or-break rules** (belong at this layer, not just Category 1)

- **`db.commit()` BEFORE `dispatch_task()`.** Background thread uses a fresh sync session and will not see uncommitted rows. Defaulting to "commit at end of request" breaks every queued run.
- **FK-resolution imports in every `tasks.py`**: `import src.auth.models  # noqa: F401`, `import src.repos.models  # noqa: F401`, etc. Agents strip "unused" imports on sight — these are non-removable. Missing import → `NoReferencedTableError` at query time.
- **WebSocket broadcasts from bg threads** use `asyncio.run_coroutine_threadsafe(coro, _event_loop)`. `_event_loop` is captured in `src/main.py` lifespan. Never `asyncio.run()` (creates a new loop, fails). Cite: `execution/tasks.py::_broadcast_run_status`, `stats/analysis.py::_broadcast_analysis_status`.
- **`task_executor._executor = ThreadPoolExecutor(max_workers=1)`** — FIFO run ordering is a correctness invariant, not a perf setting. Distributed execution is a separate roadmap phase. Do not raise the cap.
- **Alembic migration required for every model change.** Add column / rename / drop → generate + commit migration in the same PR (`make db-migrate msg="..."`). Agents skip this and break downstream envs.

**FastAPI — structural boundaries**

- Each domain module (`auth/ repos/ explorer/ execution/ environments/ reports/ stats/ ai/ recording/ webhooks/ audit/ settings/ plugins/`) owns its `models.py`, `schemas.py`, `service.py`, `router.py`, `tasks.py`. Cross-domain access goes through **service functions**, not direct model imports — *except* FK resolution imports above.
- `src/api/v1/router.py` is the **only** router aggregation point. Don't mount routers elsewhere.
- `src/database.py::get_sync_session()` is the **only** way to open a DB session outside a request. Don't `create_engine()` in a module (7 duplicates consolidated — don't recreate).
- Any subprocess touching Python goes through `environments/venv_utils.py`: `get_python_path()`, `get_venv_bin_dir()`, `os.pathsep`. Never hardcode `bin/python` vs `Scripts/python.exe`, never hardcode `:` as pathsep.
- `is_secret=True` environment variables are Fernet-encrypted. Call `decrypt_variable_value()` before passing to the runner. Legacy plaintext still decrypts — keep the fallback on reads.

**FastAPI — auth & audit**

- Auth dependency: `Depends(require_role(Role.EDITOR))` (or `RUNNER` / `ADMIN`). Accepts **both** JWT and API tokens (`rbs_…`, SHA256-hashed). Role enum + hierarchy at `backend/src/auth/constants.py`: `VIEWER(0) < RUNNER(1) < EDITOR(2) < ADMIN(3)`. Never write custom auth.
- API tokens are SHA256 (not bcrypt) — lookup, not password verification. Don't "modernize" to bcrypt.
- `AuditMiddleware` auto-logs all POST/PUT/PATCH/DELETE. For richer semantics inside a handler, call `audit(action, resource_type, resource_id, detail)` — see `src/audit/service.py`.
- `slowapi` rate-limits login (10 attempts / 5 min / IP). Configure; do not remove or replace.
- WebSocket `/ws?token=<jwt>` — bad token → close code `4401`. Don't invent another auth path.

**Pydantic v2**

- `model_config = ConfigDict(from_attributes=True)` for ORM→schema conversion. Required-without-default fields use `Field(...)` rather than class defaults.
- Schemas (`schemas.py`) and models (`models.py`) stay separate. Don't collapse them.

**Vue 3 / Pinia / Vue Router — frontend invariants**

- Views at `src/views/<Name>View.vue` (View suffix). Route definitions in `src/router/index.ts`. Router guards enforce RBAC — don't set `meta: { public: true }` unless the route is genuinely public (login, imprint, docs).
- **One Pinia store per domain**, setup syntax: `defineStore('<name>', () => { … })`. Stores own server state. **Views never call `api/*` directly** — go through the store.
- WebSocket: subscribe **once** via `useWebSocket` composable. Stores expose `handle<Event>()` methods invoked by the central dispatcher. Opening a second WS connection is a bug.
- Notifications: `ui.success|error|warning|info(title, message)` via `useToast` / `ui.store`. **Never `alert()` / `confirm()` / `prompt()`.** Confirmations go through `BaseModal`.
- **BaseModal contract**: focus-trap inside, Escape closes, click-outside closes, focus restored to trigger on close. Don't roll your own modal.
- **Four states, always**: every data-bound surface renders loading (spinner/skeleton), empty (guidance, not blankness), error (actionable with retry), disabled (explain why). Happy-path-only is a regression.
- **Async action buttons disable + show spinner during in-flight requests.** Real side effects (test runs, package installs) — double-submit is a user-trust break.

**vue-i18n v10** — user-facing ship-blocker

- Every user-visible string has EN + DE + FR + ES entries in `src/i18n/locales/*.ts` and matching docs at `src/docs/content/*.ts`.
- Escape `@`, `|`, `{`, `}` in message bodies (e.g., `admin{'@'}roboscope.local`). **Unescaped → production bundle fails silently, component renders blank white screen. Dev mode does not catch this.** Always verify changes in a prod build.
- `te('key')` before `t('key')` when the key's existence is uncertain.

**Visual editors (RobotEditor / SpecEditor)**

- **User-trust contract — no tab switch ever loses user work.** The active tab (Flow / Visual / Code) is the source of truth until save or blur. Flow and Visual share the RobotForm AST; Code tab serializes on blur. See `frontend/src/utils/flowConverter.ts::robotFormToFlow()`.
- **Mounting an editor must never mark a pristine file dirty.** The `ignoreContentUpdates` flag enforces this — editor round-trip normalization on mount doesn't count as a user edit. The dirty badge is a trust contract; regressing it breaks save-before-run prompts and unsaved-change warnings.
- CodeMirror 6 — single Python-highlighted editor reused for `.robot`, `.resource`, `.roboscope` (YAML). Don't introduce Monaco, Ace, or alternate editors.

**Vue Flow (visual flow editor)**

- Custom node types: `KeywordNode`, `ControlNode`, `StartEndNode`. Edges carry control-flow labels (`true`/`false`). Control-flow nodes auto-generate matching END nodes.
- Don't bypass the RobotForm AST — adding a node directly to Vue Flow state without updating the form breaks sync with Visual/Code tabs.

**Charts / KPI visualizations**

- Standard charts: `vue-chartjs` wrapping Chart.js.
- Deep-analysis KPIs use **hand-rolled CSS** for Stacked Bars, Dot Timeline, Heatmap Grid, Treemap. See `frontend/src/views/StatsView.vue` for the precedent. Don't pull in D3, ECharts, or similar.

**AI module (LLM integration)**

- All provider calls go through `backend/src/ai/llm_client.py` — unified httpx client for OpenAI / Anthropic / OpenRouter / Ollama. Never `import openai` or `import anthropic` directly; the unified client intentionally avoids SDK lock-in. Temperature is clamped per-provider inside the client.
- Provider API keys are Fernet-encrypted via `backend/src/ai/encryption.py`. Never log key values, never return them in API responses.
- Long-running LLM calls dispatch via `dispatch_task(run_generate | run_reverse | run_analyze, job_id)`. Poll status via `GET /ai/status/{job_id}`.
- Prompts templated in `backend/src/ai/prompts.py`. Don't inline prompt strings in task functions.

### Testing Rules

**Backend (pytest)**

- Sync tests only. `pytest-asyncio` is installed but not used at the handler level — route tests call `TestClient` synchronously.
- In-memory SQLite per test with transactional rollback. Fixtures in `backend/tests/conftest.py`: `db_session`, `client` (TestClient with `get_db` override), `admin_user`, `editor_user`, `runner_user`, `viewer_user`, `auth_header(user)`.
- Group related behavior in test classes (`class TestAuthLogin:`), not shared state. Use `_make_<thing>(...)` helpers at module top for one-off factories — `@pytest.fixture` only when the setup is reused across multiple tests.
- HTTP auth: `client.get(url, headers=auth_header(runner_user))`. Don't reimplement login; the helper mints a valid JWT.
- Background tasks: monkeypatch `dispatch_task` to run synchronously — `monkeypatch.setattr("src.task_executor.dispatch_task", lambda f, *a, **kw: f(*a, **kw))` — OR assert the dispatch and verify its effect separately.
- DB assertions: query through the test's `db_session` (don't open a new engine). After a mutating request, `db_session.refresh(obj)` before asserting fields the endpoint may have changed.
- File I/O: use the `tmp_path` pytest fixture. Never write into the repo. `WORKSPACE_DIR` / `REPORTS_DIR` / `VENVS_DIR` are overridden in test config.
- Known coverage gaps — new work must add tests: `SubprocessRunner`, `DockerRunner`, `execute_test_run()`, `task_executor.dispatch_task`, AI LLM client + encryption, WebSocket manager.

**Frontend (Vitest + @vue/test-utils)**

- `describe / it / expect` style. Vitest assertions only.
- Pinia: `createPinia()` + `setActivePinia(createPinia())` in `beforeEach`. Don't import stores before activation.
- Component tests use `mount(Component, { global: { plugins: [pinia, i18n, router] } })` when the component needs them; stub otherwise.
- i18n in tests: install the real plugin with a minimal `messages: { en: { … } }` covering the keys the component uses. Missing keys render `''` (empty string, not a fallback) — tests silently pass on empty strings unless you assert explicit text.
- jsdom 25 environment. `window`, `localStorage`, `fetch` available; workers and service workers are not.
- No HTML snapshot tests. Assert on behavior: text content, emitted events, store mutations.

**E2E (Playwright)**

- Specs at `e2e/tests/<feature>.spec.ts`. Page Objects at `e2e/page-objects/*.ts`. Extend existing page objects instead of inlining selectors in specs.
- Auth fixture at `e2e/fixtures/auth.ts` injects a JWT into `localStorage` via `addInitScript`. Use it for non-auth specs; don't drive the login UI every time.
- API mocking via `page.route('**/api/v1/<path>', route => route.fulfill({ … }))` for flaky backend-dependent assertions.
- `take-screenshots.spec.ts` is auto-skipped in CI (`testIgnore` when `CI=true`). Runs locally. Don't add CI-only skips to other specs — fix the flake.
- Selector disambiguation: this project has history of selector ambiguity bugs. Use `.notification-btn:not(.tour-btn)` or `page.getByText(…)` with exact text, not generic CSS classes.
- **Never `page.waitForTimeout(…)`** — wait on conditions (`waitForSelector`, `waitForResponse`, `waitForLoadState`). Arbitrary sleeps mask races.

**Coverage-per-change rule**

- New backend route → pytest covering happy path, 401 (auth missing), 403 (RBAC rejection), 422 (validation).
- New Vue view → E2E spec covering the primary user flow and at least one error-state render.
- Changes to `SubprocessRunner` / `DockerRunner` / `execute_test_run` / AI endpoints require tests in the same PR — these are the high-risk coverage gaps.

### Code Quality & Style Rules

_Ruff, mypy strict, ESLint, vue-tsc enforce the mechanics. `make lint` / `make format` / `make typecheck` is the contract. This section only captures what tools don't catch._

**Organizational**

- Backend module shape: `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`, `tasks.py` (when background work exists), plus domain-specific helpers (`venv_utils.py`, `constants.py`, `encryption.py`). One responsibility per file.
- Frontend per domain: `api/<domain>.api.ts`, `stores/<domain>.store.ts`, `views/<Name>View.vue`, `components/<domain>/*.vue`. Composables under `src/composables/` are cross-cutting, not per-domain.
- Before rolling a new UI primitive, check `src/components/` for `Base*` (BaseButton, BaseBadge, BaseModal, BaseToast, BaseSpinner). Five base components cover ~90% of primitives — extend, don't duplicate.
- Test files mirror source layout: `backend/tests/<domain>/test_<name>.py`. E2E specs grouped by feature.

**Naming**

- Python: `snake_case` modules/functions/variables; `PascalCase` classes + Pydantic models; `UPPER_SNAKE` constants in `constants.py`. SQLAlchemy model classes are singular (`User`, `ExecutionRun`, not plurals).
- TypeScript/Vue: `camelCase` variables/functions/composables; `PascalCase` components/types/interfaces; `kebab-case` template tags + CSS classes. Views named `<Name>View.vue`.
- Pinia: `useFoo` factory, `useFooStore()` at call site, `stores/foo.store.ts` file.
- API clients: single default-exported object with `list()`, `create(...)`, `update(...)`, `remove(id)` per resource.
- i18n keys: `<domain>.<action>` or `<domain>.<subdomain>.<key>`. Flat unless UI hierarchy justifies nesting.

**Comments & documentation**

- Default: no comments. Well-named identifiers carry intent.
- Add a comment only when the *why* is non-obvious: hidden constraint, subtle invariant, specific-bug workaround, surprising behavior. One line.
- Don't reference the current task/PR/issue in comments. That belongs in git history and the PR description — comments rot.
- Don't explain *what* — explain *why it looks unusual*.
- No multi-line docstring blocks on routine functions.

**Forbidden patterns**

- Emoji in code, UI text, or committed docs — unless the user explicitly asks. Applies to log messages, exception strings, everything.
- `as any` in TypeScript — zero new occurrences. 55+ legacy casts are debt, not precedent.
- `print()` in Python — use `logging`. Exception: user-invoked scripts under `scripts/`.
- Hardcoded hex colors in Vue components — reference `var(--color-*)`.
- Inline magic numbers for timeouts / retries / limits — lift to module constants or `src/config.py`.
- `alert()` / `confirm()` / `prompt()` in frontend — always `useToast` / `BaseModal`.
- Backwards-compat shims for removed code (renamed `_unused` vars, re-exported dead types, `# removed` comments). Delete cleanly.
- Half-finished implementations merged behind a flag. Ship cleanly or don't.

**Dependency hygiene**

- Backend dep: add to `backend/pyproject.toml`, `uv pip install -e ".[dev]"`, pin the minimum working version. Prefer fewer deps — check if stdlib or existing `httpx` covers it.
- Frontend dep: `npm install --save <pkg>`, commit updated `package-lock.json`, audit peer-dep conflicts against pinia/vue-router/vue.
- **Never bump a pinned dep** without explicit decision — see Category 1 for the locked list.
- Security overrides in `package.json` (`minimatch >=10.2.1`, `editorconfig >=2.0.0`) are not decorative. Don't strip them in cleanup.

**Feature hygiene**

- No speculative abstractions. Three similar lines beat a premature helper. Abstract on the fourth occurrence, not the second.
- No error handling for impossible cases. Validate at system boundaries; trust internal code.
- No feature flags or compatibility shims when a direct change is possible — single deploy target.

### Development Workflow Rules

**Git / branches**

- `main` is the single long-lived branch on `viadee/roboscope`. Feature branches: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`.
- Release branches: `release-<version>` (e.g. `release-0.8.1`) — created by `release-tasks`, merged back via PR.
- Never push to `main` directly. Never force-push `main`. Force-pushing a feature branch after rebase is fine.
- `origin → https://github.com/viadee/roboscope.git` (public) is the remote of record. The old `viadee-internal` remote was removed — do not re-add.

**Commits**

- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`. Optional scope: `feat(recorder): …`.
- Commit messages explain *why*, not *what*.
- Small, focused commits. One logical change per commit.
- **Never amend** a pushed commit unless the user requests it — create a new commit.
- **Never skip hooks** (`--no-verify`) unless the user requests it. Pre-commit failures are signal.
- `Co-Authored-By: …` trailer on AI-assisted commits is this repo's convention.

**Pull requests**

- Target `main`. Create via `gh pr create` with a HEREDOC body.
- Title ≤ 70 chars. Details in the body.
- Body must have `## Summary` (1–3 bullets) and `## Test plan` (markdown checklist).
- Don't self-merge to `main` without explicit approval — even when operating autonomously.
- Keep `_bmad-output/` artifacts in PRs — they are intentional project knowledge (unlike GSD's `.planning/` which is filtered).

**Database migrations**

- Every model change needs an Alembic migration: `make db-migrate msg="<description>"`. Inspect the autogenerated script before committing — autogenerate sometimes misses index/constraint drops.
- Both SQLite and PostgreSQL must pass the migration. Rewrite Postgres-only syntax to be portable.
- Never edit a migration after it has been applied to any environment. Write a new one.

**Local development**

- `make install` sets up backend venv (uv) + frontend `node_modules`. `make dev` starts both. `make backend` / `make frontend` for one stack.
- Manual backend: `cd backend && .venv/bin/python -m uvicorn src.main:app --reload --port 8000`.
- Default admin on first run: `admin@roboscope.local` / `admin123`. Change it in any shared-dev environment.
- `backend/.env` is gitignored. `backend/.env.example` is the template. Never commit secrets; never put a real `SECRET_KEY` in the example.

**Docker**

- Dockerfiles: backend, frontend, playwright. Compose files: `docker-compose.yml` (prod — PostgreSQL + Nginx), `docker-compose.dev.yml` (SQLite), `docker-compose.test.yml`.
- Use `make docker-up` / `make docker-dev` / `make docker-down` / `make docker-logs` — not raw `docker compose` — so env overrides stay consistent.
- New backend deps that need system libraries → update the backend Dockerfile in the same PR. Verify with `docker compose -f docker-compose.yml build`.

**Release**

- Use `release-tasks` skill to prepare (version bump → Docker build check → release branch → full test suite → changelog + README + in-app docs).
- Use `release-publish` to finalize (merge release branch → tag → GitHub release).
- Never bump version manually — the skill keeps `backend/pyproject.toml` and `frontend/package.json` in sync.
- **Every release produces three offline archives — Linux, macOS, and Windows. A release is not ready to publish until all three exist and pass install/start smoke tests.**

**CI**

- GitHub Actions runs lint, type-check, backend tests, frontend tests, E2E tests on every PR. Green CI is the merge bar.
- `take-screenshots.spec.ts` is intentionally skipped in CI. Don't "fix" the skip.
- uv is installed via `astral-sh/setup-uv@v5`; install step is `uv pip install --system -e ".[dev]"`. Don't switch CI back to pip.
- CI flake that doesn't reproduce locally → investigate the race, don't re-run until green.
- **The Windows offline build job runs on a `windows-latest` GitHub Actions runner. Cross-compiling the Windows archive from Linux or macOS is not supported — Python wheels and uv binaries are platform-specific, and the install/start scripts are `.cmd` / `.ps1` on Windows. A release workflow that publishes only the Mac + Linux archives is incomplete.**

**Offline deployment**

- `scripts/build-mac-and-linux.sh` builds the Linux and macOS archives (frontend build, backend source, Python wheels, `uv` binaries for those platforms, shell install/start scripts).
- **The Windows archive is produced by a separate Windows-runner job** with the same payload contract (frontend build, backend source, Python wheels for `win_amd64`, `uv.exe`, `install.cmd` / `start.cmd`).
- When adding a dependency, verify **all three** platform archives still resolve it. A backend dep that ships only `linux` / `macos` wheels and has no `win_amd64` wheel or buildable sdist on Windows is **not allowed** — it breaks the Windows archive silently. Probe with `pip download --only-binary=:all: --platform win_amd64 --python-version 312 <pkg>` before adding.

### Critical Don't-Miss Rules

_Skim-read this section if nothing else._

**Three highest-blast-radius rules**

1. **`db.commit()` before `dispatch_task()`** (verbatim from Framework Rules). Background thread uses a fresh session. Uncommitted rows do not exist for it. Default "commit at request end" silently breaks every queued run.
2. **vue-i18n: escape `@ | { }` in message bodies.** Unescaped → production bundle fails silently, component renders blank white screen. Dev mode does not catch this. Always test the prod build for i18n changes.
3. **Stripping `# noqa: F401` imports in `tasks.py`** (verbatim from Framework Rules). FK resolution fails at query time (`NoReferencedTableError`). These imports are non-removable.

**Security — hard rules**

Non-negotiable. This app executes Robot Framework tests from arbitrary git repositories, spawns subprocesses, accepts uploads, proxies LLM calls, and exposes a browser-extension endpoint.

- **No secrets in logs or responses.** Not LLM API keys, not passwords, not JWT contents, not Fernet payloads, not API tokens. Not even masked structure. `***` is fine; length hints are not. Log tokens as `rbs_xxx…last4` only.
- **Command injection — no `shell=True`, ever.** Always list-form `subprocess.run([...])`. Never string-concatenate user input into argv. Tag / test-name args flowing into the Robot CLI must pass through an allowlist regex.
- **SSRF via git URL** — `repos` creation resolves arbitrary URLs with GitPython. Scheme allowlist (`https`, `git`, `ssh`). Block RFC1918, link-local, `file://`, and `localhost` unless explicitly enabled. No redirect-following to internal hosts. Same rule for outbound webhook URLs.
- **Path traversal beyond Zip Slip** — every user-supplied path is `Path.resolve()` + `is_relative_to(workspace_root)`-checked. Applies to explorer file ops, report assets, recording downloads, and any endpoint accepting a filename.
- **LLM prompt injection** — treat LLM output as untrusted data. Never execute it. Never auto-write files without diff + user accept. Never let the model choose target file paths.
- **Extension auth boundary** — Chrome extension endpoints require `ApiToken` (not session JWT). CORS locked to the extension origin. No cookie auth on extension routes.
- **Inbound webhook CSRF** — `/webhooks/git` is unauthenticated by design. HMAC signature verification is mandatory (`X-Hub-Signature-256` for GitHub, token for GitLab). Reject unsigned payloads.
- **`SECRET_KEY` rotation** — rotating the key orphans all Fernet-encrypted env variables. Write a re-encryption migration *before* deploying a new key. Legacy plaintext still decrypts — don't remove the fallback.
- **Audit middleware entries are compliance** — don't suppress audit records to "clean up" logs.

**Single-Instance Invariants** (look parallelizable, are not — do not scale horizontally without a redesign)

- **`ThreadPoolExecutor(max_workers=1)`** — FIFO run ordering, prevents workspace / venv contention. Raising the cap is a correctness regression, not a perf win.
- **APScheduler must run in exactly one process** — multiple schedulers = duplicate retention runs = data loss. No "add another worker" without an external scheduler (Redis Queue, Celery Beat, etc.) first.
- **Git workspace is single-writer per repo** — concurrent clone/sync on the same path corrupts `.git`. Per-repo locking is required before any parallel repo-sync story.
- **WebSocket connection manager is in-memory per process** — multi-process deployment silently drops broadcasts to clients attached to other processes. Any multi-worker FastAPI rollout needs a pub/sub layer (Redis) first.
- **rf-mcp subprocess is singleton per provider** — leaked processes accumulate on restart churn; lifecycle is tied to the app-shutdown hook.

**Edge cases agents consistently miss**

- **Empty project** — repo with zero `.robot` files must render the Explorer cleanly. `build_tree` test-count has regression history; don't reintroduce crashes on empty input.
- **Repo with NULL `environment_id`** — Library Check, run defaults, AI generation all assume a venv. Empty-state must be handled explicitly, not assumed-away.
- **`.roboscope` ↔ `.robot` drift mid-edit** — user has unsaved RobotEditor changes while AI regen fires. The active editor tab is the source of truth until save; regen must not overwrite dirty files without confirmation (see save-before-run precedent).
- **Orphaned recording sessions** — Chrome extension disconnects mid-record; backend session is stuck `recording`. A reaper (timeout → `failed`) is required; do not leave sessions indefinitely open.
- **Examples project deletion** — seeded on first start. If admin deletes it, seeding must NOT re-fire and clobber user-modified examples. Seeding is idempotent by name-exists check.
- **Windows path separators in Robot CLI args** — not just venv paths. Robot output paths, log.html links, workspace mounts all need `os.pathsep` / `pathlib.Path` discipline.
- **Fernet key doesn't travel with DB dumps** — cross-environment export/import breaks encrypted env variables. Document key transfer as part of any backup/restore playbook.
- **Two `dispatch_task()` in one request** with only one `commit()` between them — second task sees stale data. Either commit twice or consolidate into one task.
- **Failed venv creation** — surface the error; never silently fall back to system Python.
- **Cancelled runs mid-execution** — subprocess must be killed, DB status set `CANCELLED`, partial `output.xml` must not be parsed.
- **WebSocket reconnect storms** after backend restart — implement exponential backoff in `useWebSocket`, not a tight retry loop.
- **Binary files in Explorer** — null-byte scan, show placeholder + "open anyway". The `force` query param bypasses the check intentionally.
- **Report upload ZIP** — Zip Slip prevention is already implemented; do not bypass during refactors of `reports/router.py`.
- **i18n missing-key renders `''`** — tests silently pass on empty strings. Always assert specific text.
- **Encrypted env vars (`is_secret=True`)** are decrypted at runner-dispatch time, not at API read time.

**Known debt (not active footguns for AI agents)**

Tracked in `CLAUDE.md` under "Known open issues": unauthenticated `/reports/{id}/assets/`, JWT in report-download URLs, missing upload size limits, default-credentials probe on login, 270KB docs eagerly bundled. Don't replicate these patterns in new code, but also don't rabbit-hole into fixing them unless scoped.

**Cross-reference discipline**

- Rules appearing in multiple sections are restated **verbatim** with a back-reference, never paraphrased — paraphrase creates reconciliation work. If a rule in this file contradicts something in the code, flag it to the user before "fixing" either one.
- The configs (`backend/pyproject.toml`, `frontend/package.json`, `backend/alembic.ini`, `e2e/playwright.config.ts`) remain the source of truth for versions, lint rules, and test config. This file captures **why**, not **what**.

---

## Usage Guidelines

**For AI Agents**

- Read this file **before** implementing any code. If the work touches the backend, frontend, extension, or release pipeline, Category 3 (Framework Rules) and Category 7 (Don't-Miss) are the minimum skim.
- When a rule here conflicts with what's in `CLAUDE.md`, this file is more specific — but flag the contradiction to the user before proceeding.
- When a rule here conflicts with the actual code, **don't silently "fix" either** — flag it first. The code may be right and the rule stale, or vice versa. Category 7 closes with this discipline.
- Defer to configs (`pyproject.toml`, `package.json`, Alembic migrations, Playwright config) as source of truth for versions and lint rules. This file captures *why*, not *what*.
- Update this file when a new pattern emerges that would fail the "would a competent agent miss this?" test.

**For Humans**

- Keep this file lean. Remove rules that become obvious over time (e.g., when the ecosystem catches up with a version pin that was load-bearing).
- Review when the technology stack changes (version bumps, new deps, runner types) — the Technology Stack section is the section that rots fastest.
- Re-run party-mode review after any major refactor touching concurrency, auth, or the AI module — those are the three surface areas with the most non-obvious invariants.
- Planning artifacts generated by BMAD workflows (PRDs, architectures, stories) live alongside this file at `_bmad-output/`. They are tracked in git as intentional project knowledge.

_Last Updated: 2026-04-14_

