# Changelog

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
