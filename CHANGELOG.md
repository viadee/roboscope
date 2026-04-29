# Changelog

## [Unreleased]

Work in progress on `feat/recorder-and-bmad` branch. Highlights from
the loop session of 2026-04-28/29 (24 stories shipped on top of the
Phase-4 SSO/Teams + Recorder + BMAD foundation):

### Features
- **REPO save loop for non-Git users** (REPO-1) — `GET /repos/{id}/status`,
  `POST /repos/{id}/commit`, `/push`, `/publish` endpoints; in-app
  Save modal with conflict-recovery state; tree-header `Save N changes`
  badge in Explorer.
- **Auto-Sync actually pulls on schedule** (REPO-2) — APScheduler
  5-minute heartbeat invokes `due_repos(now)`; per-repo
  `sync_interval_minutes` honoured. Was previously a stored-but-unused
  toggle.
- **Pre-run sync** (REPO-3) — opt-in per-repo flag pulls
  `origin/<default_branch>` synchronously before each run, with a
  60 s wall-clock timeout and graceful fall-through on failure.
- **Webhook pre-sync** (REPO-4) — `POST /webhooks/git` now dispatches
  `sync_repo` before `execute_test_run`; the single-worker task
  executor guarantees order.
- **Default-password banner** (SECURITY-1, revised) — non-blocking
  yellow banner shown when an admin still uses the seed password,
  links to a `POST /auth/change-password` endpoint. Server logs a
  WARNING on every flagged login.

### Security
- **Authenticated report assets** (REPORT-1) — `/reports/{id}/assets/`
  was anonymous; now requires Bearer header or `?token=<jwt>`. Closes
  the first item under CLAUDE.md known issues.
- **Asset token replaces JWT in iframe URLs** (SECURITY-3) — new
  HMAC-signed, report-scoped, 1-hour-TTL `?at=<asset_token>` embedded
  in `<base href>` instead of the user's JWT. Iframe URLs leaking out
  no longer expose the user's full access token.
- **Streaming upload size guard** (ROBUSTNESS-1) — `/reports/upload`
  previously read the full body into RAM before the 500 MB check. Now
  streamed in 1 MiB chunks with an early-abort plus a Content-Length
  pre-check.

### Performance
- **Lazy-loaded docs locales** (PERF-1) — DocsView chunk shrunk from
  413 kB → 4 kB (gzipped 124 kB → 1.8 kB). Each locale's content
  streams on demand.

### Robustness / Ops
- **Deep `/health` endpoint** (ROBUSTNESS-1) — runs `SELECT 1`; returns
  503 with `{"status":"unhealthy","reason":"database_unreachable"}`
  on DB outage so kubelet liveness probes can flag the pod.
- **Request-ID correlation in logs** (LOGGING-1) — every log record
  emitted during an HTTP request carries the `X-Request-ID` header
  value via a `ContextVar`, propagated automatically through the
  pythonjsonlogger formatter.

### Refactor / DevEx
- **Single Docker client bootstrap** (REFACTOR-1) — three near-identical
  copies of the `from_env()` + `docker context inspect` recipe
  replaced with `src/docker_client.py:get_docker_client()`.
- **`as any` cleanup** (TYPE-1..TYPE-4) — went 25 → 0 real casts in
  source. New exported unions (`AnalysisStatus`, `PackageInstallStatus`),
  discriminated union for the keyword palette, runtime type-guard
  for drag-drop step-type strings.

### Accessibility
- **A11Y baseline pass** (A11Y-1) — `<html lang>` follows i18n locale,
  icon-only AppHeader buttons get `aria-label`, language switcher
  gets `aria-pressed`, skip-to-main link mounted in DefaultLayout.

### Tests (5 new files, 99 new tests)
- WebSocket `ConnectionManager` (TEST-1, 15)
- DockerRunner (TEST-2, 24)
- AI provider CRUD endpoints (TEST-3, 19)
- AI generate / reverse / analyze / status / accept (TEST-4, 20)
- `execute_test_run` early-exit branches (TEST-5, 3)

### Sibling repos (local-only, pre-publish)
- `roboscope-rfheal/` — heal package, packaged for PyPI; commit
  ready, not pushed.
- `roboscope-examples/` — Apache-2.0 starter examples for the most-used
  Robot Framework libraries (Collections, String/DateTime, Process/OS,
  RequestsLibrary, DatabaseLibrary, JSONLibrary, Browser); 26 tests
  green via `uv run robot examples/`. Initial commit ready, not
  pushed.

## [0.8.1] - 2026-03-26

### Features
- **Browser Library Variant Support** — Support for `robotframework-browser-batteries` (self-contained, no Node.js needed) as alternative to standard `robotframework-browser`. Conflict detection prevents installing both variants simultaneously. Dockerfile generation skips Node.js/rfbrowser init for batteries variant.
- **rfbrowser init Status in Environments** — Browser packages now show initialization status: ✅ "Browser initialized" or ⚠️ "rfbrowser init required" with a manual trigger button. `POST /environments/{id}/rfbrowser-init` endpoint for manual init.
- **Default Environment Auto-Assignment** — Explorer auto-assigns the "default" environment to projects that have none. Environment badge displayed next to the project selector with link to configuration.
- **Keyword Autocomplete from All Installed Libraries** — rf_knowledge now discovers all RF-related packages in the venv (not just explicitly imported ones), providing broader keyword autocomplete coverage.
- **Keyword Cache Invalidation** — `POST /ai/rf-knowledge/keywords/invalidate` endpoint to force re-scan of keywords when environment packages change.
- **Browser-Batteries as Default** — `setup-default` environment now installs `robotframework-browser-batteries` instead of `robotframework-browser`.

### Fixes
- Fix keyword search wildcard `*` not returning any results (preloadKeywords was broken)
- Fix stuck package installations showing perpetual spinner — packages in `pending`/`installing` without an active task are auto-reset to `failed`
- Fix package install retry failing when venv doesn't exist — auto-creates venv before pip install
- Fix E2E test flakiness for explorer run overlay (handle all intermediate dialogs)

### Tests
- 885 backend tests passing (up from 865)
- New tests for browser variant conflict detection, auto-create venv on retry
- E2E test robustness improvements for execution run overlay

## [0.8.0] - 2026-03-23

### Features
- **Visual Flow Editor** — Node-based graphical editor as third tab "Flow" in RobotEditor. Vue Flow with custom nodes: KeywordNode (library calls + arguments), ControlNode (IF/FOR/WHILE/TRY), StartEndNode. MiniMap, Controls, Background Grid, Detail Panel on node click.
- **Flow Editor Keyword Palette** — 5 categories (BuiltIn, Collections, String, Browser, Control), search filter, click-to-add and drag & drop, dynamic loading from rf-mcp libraries and .resource files.
- **Flow Editor UX** — Editable node panel, accordion palette, node reorder & delete, expand/collapse all, select-then-add mode, stable viewport on move.
- **CI/CD Integration (Phase 1)** — API Tokens with SHA256 hash, `rbs_` prefix, role scoping (RUNNER/EDITOR), expiry dates. Auth accepts JWT + API Token. CRUD under `/api/v1/webhooks/tokens`. Frontend: Settings tab "API Tokens".
- **Outbound Webhooks** — HMAC-SHA256 signed (`X-RoboScope-Signature`), 6 events (run.started/passed/failed/error/cancelled/timeout), retry with backoff, test ping, delivery log. Frontend: Settings tab "Webhooks".
- **Git Webhook Trigger** — `POST /api/v1/webhooks/git` accepts GitHub/GitLab push payloads, matches repo via `git_url`, auto-creates ExecutionRun.
- **Audit Log (Phase 2)** — `AuditLog` model with automatic middleware for all POST/PUT/PATCH/DELETE. Admin UI: filterable log, CSV export, manual `audit()` helper.
- **Retention Enforcement** — APScheduler (24h interval) deletes reports/runs older than `report_retention_days`. Dry-run mode, manual trigger via API.
- **Secrets Encryption** — Fernet encryption (derived from SECRET_KEY) for environment variables with `is_secret=True`. Legacy plaintext graceful degradation.
- **Demo Video Recording** — Playwright-based automated demo video generation with overlay text injection, TTS voice-over (OpenAI), EN/DE versions. `DEMO_VIDEO=1 DEMO_LANG=de` env vars.

### Fixes
- Fix Google Fonts CDN links for offline compatibility (#29)
- Fix auth redirect loop in Safari (stale token + HMR reload)
- Fix Flow Editor detail panel stays open on arg add/reorder, viewport stable on move (#28)
- Fix greenlet as explicit dependency for offline package builds
- Fix default environment name and human-readable validation errors
- Fix audit middleware DB writes in daemon thread to avoid event loop blocking

### Security
- Secrets encryption at rest for environment variables (Fernet)
- API Token authentication with SHA256 hashing
- HMAC-SHA256 webhook signatures

### Tests
- 865 backend tests passing (up from 792)
- 267 E2E tests passing
- 113 frontend tests passing
- 34 new tests for API tokens, webhooks, audit log, secrets encryption

### Docs
- In-app documentation updated for API Tokens, Webhooks, Audit Log, Secrets, Flow Editor (EN/DE/FR/ES)
- Demo video scripts and TTS voice-over in EN/DE

## [0.7.0] - 2026-03-12

### Features
- **RobotEditor Visual Improvements** — Section colors, variable highlighting, expand/collapse, lazy keyword loading, vertical args overflow
- **Docker Error Handling** — `DockerNotAvailableError`, `DockerImageNotFoundError` with translated error banners
- **Docker Image Staleness Detection** — `docker_image_built_at`, `packages_changed_at`, computed `docker_image_stale`, amber warnings in Execution + Explorer views
- **Persistent Docker Build Status** — `docker_build_status`/`docker_build_error` on Environment model, server-driven UI
- **Docker Build Terminal Output** — WebSocket-streamed live build logs with terminal component (pulsing dot, auto-scroll, show/hide toggle)
- **Docker Build Robustness** — Playwright base image, pre-build disk space check, large base image hint, dangling image cleanup, enriched Docker error messages
- **Execution View** — Project name column in runs table and detail panel, duration column
- **rfbrowser Init Visibility** — Post-install node_modules verification, pre-run Browser lib check, "initializing" UI status
- **Run Cancellation** — Actually kills spawned subprocess via runner registry pattern; status check after execution prevents overwrite
- **Branch Switching** — `POST /repos/{id}/checkout` endpoint, branch dropdown on project cards
- **Auto-Sync Toggle** — Checkbox on project cards to enable/disable periodic Git sync

### Fixes
- **Report Tree** — Fix `.//tag` XPath finding keyword descendant tags as test tags (now `tags/tag`); fix CSS connector lines (`:first-child` → `:last-child`)
- **Explorer Editor Chain** — Fix v-if/v-else-if chain where no-environment banner blocked RobotEditor from rendering
- **Startup Cleanup** — Reset stuck `docker_build_status=building` → `error` and stuck packages on app start
- **Windows Offline Build** — Fix missing httptools wheels by using separate `requirements-windows.txt` without `uvicorn[standard]` extras (#12)

### Tests
- 136 new backend tests (656 → 792 total) covering previously untested modules:
  - `task_executor.py` (15 tests), `ai/encryption.py` (15 tests), `ai/llm_client.py` (35 tests)
  - `websocket/manager.py` (42 tests), `execution/tasks.py` (21 tests)
  - `repos/service.py` branch functions (8 tests), `repos/router.py` checkout endpoints (13 tests)
- All 267 E2E tests passing

### Docs
- In-app documentation updated for Docker build terminal, image staleness, branch switching, auto-sync, run cancellation, rfbrowser init (EN/DE/FR/ES)

## [0.6.0] - 2026-03-11

### Features
- **RoboView Code Quality KPIs**: 6 new Deep Analysis KPIs integrated from `robotframework-roboview` — keyword reuse rate, unused keywords, keyword duplicates, keyword similarity, documentation coverage, Robocop violations (#11)
- **Private Registry Support**: `index_url` / `extra_index_url` per environment for custom PyPI registries (#6)
- **RF Keyword Library Scan** + SpecEditor help text (#7)
- **Python Version Validation**: normalize patch versions (3.12.5→3.12), reject unsupported versions, warn on pre-release (#5)

### Security
- Remove default SECRET_KEY — require explicit configuration (startup error if unset) (#4)
- Move JWT tokens from URL query params to Authorization headers for report HTML/ZIP endpoints (#4)
- Add optional auth + audit logging on report asset endpoint (#4)
- Add global API rate limiting via slowapi (1000/min default, stricter on expensive endpoints) (#4, #11)
- Add upload size limits: Nginx 500m + FastAPI 500MB check (HTTP 413) (#4)
- Add subprocess resource limits (RLIMIT_AS 2GB) on Linux/macOS (#4)
- Add thread safety to WebSocket manager (lock + copy-iterate pattern) (#4)
- Replace plaintext logging with structured JSON logging (python-json-logger) (#4)
- Add request-ID middleware for log correlation (X-Request-ID header) (#4)
- Add PostgreSQL `pool_recycle` (3600s) to prevent stale connections (#4)

### Fixes
- Hardened private registry: validation, credential masking, migrations (#9)
- Fix interleaved test functions in `environments/test_router.py` from bad merge (#11)
- AI ProviderConfig: curated model dropdowns with current model IDs (#11)
- **Makefile**: `make install` now creates `.venv` automatically; all targets use `.venv/bin/` prefix so the 3-step install works on fresh clones
- CI: set SECRET_KEY for build workflow and dist test scripts

### Tests
- 13 new security E2E tests: API auth, WebSocket auth, request-ID, health check, rate limiting (#11)
- 4 new code quality KPI E2E tests: API + UI for RoboView integration (#11)
- 40 backend tests for RoboView compute functions (#11)

### Docs
- In-app documentation updated for security hardening, code quality KPIs (EN/DE/FR/ES) (#11)
