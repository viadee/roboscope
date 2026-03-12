# Changelog

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
