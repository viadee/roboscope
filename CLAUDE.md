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
- **JS `new Date(naiveIso)` parses as LOCAL time, not UTC**: SQLAlchemy on SQLite drops `tzinfo` on round-trip, so the API ships `2026-04-29T07:58:04` (no `Z`, no offset). `new Date(thatString)` then reads it as local time, putting a sync that just happened ~UTC-offset hours in the past — manifests as "vor 2 Std." right after a sync. Two layers protect against this: (1) backend `src/utc_response.py::UtcJSONResponse` is wired as `default_response_class` and post-processes outgoing JSON to append `Z` to naive ISO datetimes; (2) frontend `src/utils/formatDate.ts::parseBackendDate(s)` normalises any naive ISO it sees back to UTC before constructing a `Date`. Always use `parseBackendDate` (not `new Date`) when computing `now − apiField`. The integration test in `backend/tests/repos/test_router.py::test_get_existing_datetimes_carry_z_suffix` fires if anything route-level bypasses the response class.
- **FlowEditor node `step` arrays MUST be deep-cloned from form**: `flowConverter.ts::stepsToFlow` does `step: cloneStep(step)` (NOT `{ ...step }`). The detail-panel inputs use `v-model="selectedNodeData.step.args[i]"`; if `args` were a shared reference with `props.form`, every keystroke would fire RobotEditor's `watch(() => form.testCases, … { deep: true })` and reset `selectedNode = null`, tearing down the panel mid-edit. The form is updated only on blur via `updateStepFromNode`'s `Object.assign`. Pinned by `FlowEditorStepIsolation.spec.ts`. If you add a new array field to `RobotStep`, extend `cloneStep()` or you reopen the bug.
- **Recorded `New Page` MUST emit `wait_until=domcontentloaded`**: Playwright's default `wait_until="load"` waits for every ad/tracker subresource. On real-world pages (`heise.de` etc.) the `load` event routinely never fires within the Browser-library 10s context timeout, even though the page is visually loaded and interactive. `domcontentloaded` is the right level for recorded flows — the page is parsed, any subsequent Click / Type Text / Scroll To Element finds its target. Both emitters (`recording/generator.py`, `recording/robot_emit.py`) write the explicit `wait_until=` and the regression assertions in `test_generator.py` / `test_robot_emit.py` pin it. Run 32 reproduced exactly this bug.
- **Recorded `${HEADLESS}` reference REQUIRES the `*** Variables ***` definition**: `robot_emit.py` writes `New Browser    chromium    headless=${HEADLESS}` so users can flip head/headless without editing the test body. It MUST also emit a `*** Variables ***` block with `${HEADLESS}    false` (default `false` — recorded tests come from clicking through a real page, so headed-by-default matches user intent). Without the definition, RF refuses to start with `Variable '${HEADLESS}' not found.`. If you add another `${VAR}` reference to the bootstrap, add the corresponding definition in the same place.
- **Bool checkbox in FlowEditor MUST preserve the `name=` prefix**: `selectedNodeData.step.args[i]` may be `force=True` (named-arg form). A naive `args[i] = writeBoolValue(checked)` overwrites with bare `True`, which on re-render makes `specForSlot` fall back to a different positional spec — the checkbox vanishes mid-edit and a text input takes its place. `_NAMED_ARG_RE` strips the prefix in both `isBoolChecked` and `onBoolToggle`; signature defaults are consulted via `specForSlot(...).spec.defaultValue` for empty value-half slots like `force=`. The user-facing `{}` toggle in the detail panel is the escape hatch from the typed control to a free-text input (e.g. for `${HEADLESS}` on a bool slot).
- **Setting-meta side-note inputs use a draft buffer, never v-model into the form**: same root cause as the cloneStep bullet above. The `[Documentation]` / `[Tags]` / `[Setup]` etc. side notes (`flow/flowConverter.ts::appendSettingMetaNodes`, type `setting-meta`) open a kind-aware detail panel whose textarea / input v-models into a local `settingDraft` ref in `FlowEditor.vue`, NOT into `props.form.testCases[i].documentation` directly. A dependency-keyed watcher reseeds the draft when the user clicks a different side note; `commitSettingDraft()` writes the buffered value back on blur, going through `rebuildAndReselect()` which sets `suppressFitView` so the deep watcher doesn't tear `selectedNode` down across the rebuild. Pinned by `FlowEditorSectionSwitch.spec.ts` + 2 e2e specs in `flow-editor-settings.spec.ts`. If you add another setting kind, add it to the `SettingKind` union, `TC_KINDS` / `KW_KINDS`, `KIND_LABELS`, plus the `settingTarget` / `settingDraft` get/commit branches AND the i18n `flowEditor.settingMeta.<kind>.{label,placeholder,hint,addTitle,removeTitle}` keys in EN/DE/FR/ES.
- **Setting-meta side notes need ≥96px stacking pitch + height-clamped CSS**: `appendSettingMetaNodes` stacks side notes vertically at `META_PITCH = 96`. The CSS on `.flow-node-doc-meta` enforces `width: 240px`, `max-height: 76px`, `overflow: hidden`, plus `-webkit-line-clamp: 2` on `__text` (and 1 for non-doc kinds). If you bump `META_PITCH` lower without also tightening the line-clamp, a long [Documentation] preview can overflow into the [Tags] node below. The 96/76/2 numbers are tuned together — keep them in sync.
- **Recorder capture script MUST use `composedPath()[0]`, not `ev.target`**: events fired inside an open shadow root surface with `ev.target` retargeted to the *host* in the light DOM. `recording/capture_script.py::realTarget(ev)` returns `ev.composedPath()[0]` (falling back to `ev.target` for closed roots). Every event handler (click, dblclick, change, keydown, dragstart, drop) goes through `realTarget`. The ancestor walk also crosses shadow boundaries via `crossShadow(el)`: when `parentElement` is null, jump to `getRootNode().host` if the root is a `ShadowRoot`. Each ancestor carries an `is_shadow_host` flag that the synthesis layer reads to emit a `host >> inner` chained Playwright locator (selector_synthesis.py::`_shadow_chain`). Pinned by `test_capture_script.py::TestShadowDomAwareness` + `test_selector_synthesis.py::TestShadowDom`. If you add a new event listener, route it through `realTarget` or shadow-DOM clicks fire on the wrong element.
- **Recorder selector synthesis MUST emit a parent-context CSS variant**: `selector_synthesis.py::_css` emits not only `tag.classes` but also `<ancestor#id|testid> tag.classes` whenever a stable ancestor exists. A bare `button.submit-btn` matching every submit on the page is the most common Playwright strict-mode failure source at replay; pinning the nearest stable-id ancestor (quality_score `+10` over the bare class chain) cuts those misfires by orders of magnitude. The `_with_nth_match` rewrite in `selector_verification.py` is the *last-resort* fallback (penalty `-15`) when no parent context exists. Pinned by `test_selector_synthesis.py::TestParentContextCss`.

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

Known open issues: a11y gaps (broad — keyboard nav, ARIA labels, focus traps in modals); long-tail of ~15 `: any` annotations remain (down from ~65), all on data-shaping paths — WebSocket message bodies (2), YAML output builders in `SpecEditor.vue` (8), inline arrow params in chart-data expressions in `StatsView.vue` (4), and one `events: any[]` on a legacy recorder API surface. Zero `as any` casts. The previous ~50 `catch (e: any)` idioms were eliminated by the shared `extractErrorDetail` / `extractErrorStatus` helpers in `frontend/src/utils/errors.ts` — every catch binding is now `: unknown` or uses inline `e instanceof Error` narrowing.

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

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
