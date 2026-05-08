# Story 1.9: Discovery-Cache Refresh APScheduler Job

Status: done

Epic: 1 — Enterprise Identity Foundation
Story Key: `1-9-discovery-cache-refresh-apscheduler-job`

## Story

As a Platform engineer,
I want IdP discovery metadata cached in DB for 24 hours and refreshed via APScheduler,
So that the application boots with zero outbound calls and tolerates transient IdP unreachability.

## Acceptance Criteria

1. **AC1 — Boot invariant.** On startup, no outbound HTTP request is made to any IdP endpoint. The APScheduler discovery job's `next_run_time` is set to `now + 24h` so the first execution is deferred. Validated by a pytest smoke test that patches `httpx.Client.send` to raise and verifies no `httpx` call fires during `create_app()` startup.

2. **AC2 — Scheduled refresh.** An APScheduler job with `IntervalTrigger(hours=24)` refreshes `discovery_cache_json` and `discovery_cached_at` for all **enabled** IdPs whose cache is **stale** (older than 24h or `discovery_cached_at is None`). Disabled IdPs are skipped. Per-IdP failures are caught, logged, and tallied — they do not abort the batch. Returns `{"status": "completed", "refreshed": N, "failed": M, "skipped": K}`.

3. **AC3 — Manual trigger endpoint.** `POST /api/v1/auth/idp-providers/discovery-cache/refresh` (ADMIN-only) triggers `refresh_discovery_cache(force_all=True)` synchronously and returns the same summary dict. Route must be declared before `/{idp_id}` routes in the router.

4. **AC4 — `discovery_cached_at` in API response.** Add `discovery_cached_at: datetime | None` to `IdentityProviderResponse` schema. This exposes cache freshness to the frontend.

5. **AC5 — Stale-cache badge in admin UI.** In `IdpProviderListView.vue`, show an `--color-accent` pill per row when `discovery_cached_at` is `null` or older than 24h. Text: "Cache expired" (or locale equivalent). In `IdpProviderEditView.vue`, show the same badge in the header area. i18n keys `idpProviders.staleCacheBadge` and `idpProviders.neverCached` in all 4 locale files.

6. **AC6 — `get_or_fetch_discovery()` helper.** Add `get_or_fetch_discovery(db, idp) -> dict | None` to `oidc_discovery.py`. Returns cached doc if fresh (< 24h); otherwise calls `probe_idp_discovery(db, idp)`, commits, returns the doc or `None` on failure. Story 2-1 (OIDC login) will call this exclusively — no inline fetching in the login route.

7. **AC7 — Tests.** 4+ pytest tests in `test_discovery_refresh.py` (stale IdP refreshed, fresh skipped, disabled skipped, manual endpoint). 1 boot smoke test in `test_boot_invariant.py`. Existing suite green (975 backend, 133 Vitest, E2E).

## Tasks / Subtasks

- [x] **Task 1: `backend/src/auth/discovery_refresh.py`** [NEW]
  - [ ] `DISCOVERY_CACHE_TTL_HOURS = 24` module-level constant (single source of truth — also imported by `oidc_discovery.py`)
  - [ ] `refresh_discovery_cache(force_all: bool = False) -> dict` job entry point:
    - `with get_sync_session() as session:` (context manager pattern from `retention.py:23`)
    - `import src.auth.models  # noqa: F401` at function top (FK resolution — critical, see `retention.py:25`)
    - Fetch all IdPs: `list_identity_providers(session)`
    - Per IdP: skip if `not idp.is_enabled`; skip if not `force_all` AND cache fresh (`discovery_cached_at` not None AND age < TTL)
    - For stale: call `probe_idp_discovery(session, idp)`, then `session.commit()`
    - Catch `Exception` per IdP: log with `exc_info=True`, increment `failed`, continue
    - Return `{"status": "completed", "refreshed": N, "failed": M, "skipped": K}`
  - [x] `logger = logging.getLogger("roboscope.auth.discovery_refresh")`

- [x] **Task 2: Register job in `main.py`**
  - [ ] Import `refresh_discovery_cache` from `src.auth.discovery_refresh`
  - [ ] Import `timedelta` from `datetime` (add to the datetime import block near the scheduler section)
  - [ ] Add second `_scheduler.add_job(...)` call in the **same scheduler block** (before `_scheduler.start()`, after the retention job):
    ```python
    _scheduler.add_job(
        refresh_discovery_cache,
        trigger=IntervalTrigger(hours=24),
        id="oidc_discovery_refresh",
        name="OIDC Discovery Cache Refresh (24h)",
        next_run_time=datetime.now(timezone.utc) + timedelta(hours=24),
        replace_existing=True,
    )
    ```
  - [x] The `next_run_time` parameter is **CRITICAL** — without it, APScheduler fires the job immediately at boot, violating AC1.
  - [x] Add needed imports at the top of the scheduler block: `from datetime import datetime, timedelta, timezone`

- [x] **Task 3: Manual trigger endpoint and schema**
  - [x] Add `DiscoveryCacheRefreshResponse(BaseModel)` to `src/auth/schemas.py`
  - [x] In `idp_router.py`, add `POST /discovery-cache/refresh` route before `GET /{idp_id}`

- [x] **Task 4: `get_or_fetch_discovery()` + schema update**
  - [x] `DISCOVERY_CACHE_TTL_HOURS = 24` defined in `oidc_discovery.py`; imported by `discovery_refresh.py`
  - [x] `get_or_fetch_discovery(db, idp) -> dict | None` added to `oidc_discovery.py`
  - [x] `discovery_cached_at: datetime | None = None` added to `IdentityProviderResponse`

- [x] **Task 5: Frontend stale-cache badge**
  - [x] `isDiscoveryCacheStale()` helper added to both views
  - [x] Stale badge with `--color-accent` shown in `IdpProviderListView.vue` per row
  - [x] Stale badge shown in `IdpProviderEditView.vue` header area (edit mode only)
  - [ ] In `IdpProviderListView.vue`: add badge cell/element per row using `isDiscoveryCacheStale(idp.discovery_cached_at)`. Badge style: `background: var(--color-accent)`.
  - [ ] In `IdpProviderEditView.vue`: add badge near the form header when editing (`routeId != null`) and stale.
  - [ ] i18n: add `idpProviders.staleCacheBadge: 'Cache expired'` and `idpProviders.neverCached: 'Never cached'` to all 4 locale files (EN/DE/FR/ES). Escape special chars per vue-i18n rules.

- [x] **Task 6: Tests**
  - [ ] `backend/tests/auth/test_discovery_refresh.py` [NEW]:
    - `test_stale_idp_is_refreshed` — seed enabled IdP with `discovery_cached_at = now - 25h`, call `refresh_discovery_cache()`, assert `discovery_cache_json` updated (mock `probe_idp_discovery` to return a fake response and set cache fields)
    - `test_fresh_idp_is_skipped` — seed enabled IdP with `discovery_cached_at = now - 1h`, assert `probe_idp_discovery` NOT called
    - `test_disabled_idp_is_skipped` — seed disabled IdP with stale cache, assert NOT refreshed
    - `test_manual_trigger_endpoint` — `POST /api/v1/auth/idp-providers/discovery-cache/refresh`, assert 200 + JSON with `status`, `refreshed`, `failed`, `skipped`
  - [x] `backend/tests/test_boot_invariant.py` [NEW]:
    - `test_discovery_job_next_run_time_deferred` — starts BackgroundScheduler, adds job with `next_run_time = now + 24h`, asserts `job.next_run_time` is > 23h in the future

## Dev Notes

### CRITICAL GOTCHAS

1. **`next_run_time` is mandatory — APScheduler fires immediately by default.** `BackgroundScheduler.add_job` with `IntervalTrigger` will fire the job at the next scheduler tick (near-immediately) unless `next_run_time` is explicitly set to a future datetime. Missing this causes `refresh_discovery_cache()` to run at boot → `probe_idp_discovery()` makes HTTP calls to IdPs → AC1 fails.

2. **`DISCOVERY_CACHE_TTL_HOURS` circular import.** Define the constant in `oidc_discovery.py` (it belongs there since `probe_idp_discovery` and `get_or_fetch_discovery` use it). Import it in `discovery_refresh.py`:
   ```python
   from src.auth.oidc_discovery import DISCOVERY_CACHE_TTL_HOURS, probe_idp_discovery
   ```
   This avoids the inverse circular import (`oidc_discovery → discovery_refresh`).

3. **FK model imports in background jobs.** The background job runs in a new thread with a fresh session. Without model imports, SQLAlchemy FK resolution fails silently. Always add:
   ```python
   import src.auth.models  # noqa: F401
   ```
   at the top of `refresh_discovery_cache()`. Pattern: `retention.py:25-26`.

4. **`get_sync_session()` as context manager.** `database.py:75` returns `SessionLocal()` which supports `with` via SQLAlchemy's context manager protocol. Do NOT close the session manually — the `with` block handles it. Always use `with get_sync_session() as session:`.

5. **`probe_idp_discovery` calls `db.flush()` internally.** After calling it, call `db.commit()` in the job. The flush writes to the session identity map; commit persists to DB.

6. **`discovery_cached_at` timezone in SQLite.** SQLite stores naive datetimes. When computing staleness, use `datetime.now(timezone.utc)` and strip tz for comparison OR compare both as naive. Follow the pattern in `retention.py:39`:
   ```python
   cutoff_naive = cutoff.replace(tzinfo=None)
   ```
   For `get_or_fetch_discovery`, check if `discovery_cached_at` is tz-aware before subtracting.

7. **Route declaration order matters.** `POST /discovery-cache/refresh` MUST be declared before `GET /{idp_id}` in `idp_router.py`. FastAPI matches routes in declaration order. Place it right after the `POST ""` create route (line ~64 in current file).

8. **`IdentityProviderResponse` already missing `discovery_cached_at`.** Verified: the current schema (line 111-125) does NOT include this field. Add it:
   ```python
   discovery_cached_at: datetime | None = None
   ```
   This is needed for the frontend badge. No migration needed — column already exists in DB (added in Story 1-1).

9. **Boot smoke test — `create_app()` does not run lifespan.** `create_app()` in `main.py` constructs the FastAPI app but does NOT run the lifespan context manager (startup). The scheduler is initialized in `lifespan()`. To test boot startup, use `TestClient(app)` context manager which runs lifespan, or directly call the lifespan async generator via `asynccontextmanager` in an async test. Simpler: check that `_scheduler.get_job("oidc_discovery_refresh").next_run_time > datetime.now(timezone.utc)` after scheduler init, as a unit test.

10. **Frontend: `idpProviders.relative` keys already exist.** `en.ts:1281-1287` has `justNow`, `minutesAgo`, `hoursAgo`, `daysAgo`, `never`. Reuse these for the badge's "X ago" display — no new time-formatting keys needed. Only add `staleCacheBadge` and `neverCached`.

### Existing Scheduler Pattern (reference)

`backend/src/main.py:143-156`:
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.audit.retention import enforce_retention

_scheduler = BackgroundScheduler()
_scheduler.add_job(
    enforce_retention,
    trigger=IntervalTrigger(hours=24),
    id="retention_enforcement",
    name="Retention Enforcement (daily)",
    replace_existing=True,
)
_scheduler.start()
logger.info("Retention enforcement scheduler started (every 24h)")
```
Add the discovery job in this same block (before `_scheduler.start()`), with `next_run_time` deferred.

### Background Job Pattern (reference)

`backend/src/audit/retention.py:17-30`:
```python
def enforce_retention(dry_run: bool = False) -> dict:
    with get_sync_session() as session:
        import src.auth.models  # noqa: F401
        import src.repos.models  # noqa: F401
        from src.settings.service import get_setting_value
        ...
        session.commit()
    return {...}
```

### `idpProviders.relative` (reusable for badge)

`frontend/src/i18n/locales/en.ts:1281-1287` — already defined:
```ts
relative: {
  justNow: 'just now',
  minutesAgo: '{n}m ago',
  hoursAgo: '{n}h ago',
  daysAgo: '{n}d ago',
  never: '—',
},
```
Use these for the "last fetched X ago" part of the badge. Only add `staleCacheBadge` and `neverCached` as new keys.

### File Layout

```
backend/
├── src/
│   └── auth/
│       ├── oidc_discovery.py         [MOD — DISCOVERY_CACHE_TTL_HOURS, get_or_fetch_discovery()]
│       ├── discovery_refresh.py      [NEW — refresh_discovery_cache() job]
│       ├── idp_router.py             [MOD — POST /discovery-cache/refresh]
│       └── schemas.py                [MOD — DiscoveryCacheRefreshResponse, discovery_cached_at in response]
├── main.py                           [MOD — register discovery job, import timedelta/timezone]
└── tests/
    ├── auth/test_discovery_refresh.py  [NEW — 4 tests]
    └── test_boot_invariant.py          [NEW — 1 smoke test]
frontend/
└── src/
    ├── views/
    │   ├── IdpProviderListView.vue    [MOD — stale badge per row]
    │   └── IdpProviderEditView.vue    [MOD — stale badge in header]
    └── i18n/locales/{en,de,fr,es}.ts  [MOD — staleCacheBadge, neverCached]
```

### References

- Scheduler setup: `backend/src/main.py:143-156`
- Background job pattern: `backend/src/audit/retention.py:17-30`
- `get_sync_session()`: `backend/src/database.py:75-81`
- `probe_idp_discovery()`: `backend/src/auth/oidc_discovery.py:76-261`
- `list_identity_providers()`: `backend/src/auth/idp_service.py:17-19`
- `IdentityProvider` cache fields: `backend/src/auth/models.py:43-44`
- `IdentityProviderResponse` (missing `discovery_cached_at`): `backend/src/auth/schemas.py:111-125`
- ADMIN route guard pattern: `backend/src/auth/idp_router.py:36-41`
- i18n relative keys: `frontend/src/i18n/locales/en.ts:1281-1287`
- AR16 (APScheduler piggyback): `_bmad-output/planning-artifacts/epics.md`

### Previous Story Learnings (1-8)

- vue-i18n prod-build: `•`, `—`, `{`, `@` must be escaped in locale strings
- `StreamingResponse(iter([bytes]))` is the correct FastAPI download pattern
- `uv add` only — never `pip install`
- Test baseline: 975 backend, 133 Vitest, 4 E2E (all green required)
- `sanitizeDetail()` in frontend strips `{`, `}`, `@`, `|` from server error strings

## Review Findings

- [x] [Review][Decision] AC1 boot invariant test — added `test_discovery_job_does_not_probe_at_boot`: starts real scheduler, patches `probe_idp_discovery`, waits 0.5s for 5 scheduler ticks, asserts probe never called. Behavioral verification of the boot invariant.
- [x] [Review][Patch] Missing `session.rollback()` on probe exception in `refresh_discovery_cache()` [backend/src/auth/discovery_refresh.py]
- [x] [Review][Patch] Dead import `from datetime import timedelta` in `get_or_fetch_discovery()` — removed [backend/src/auth/oidc_discovery.py]
- [x] [Review][Patch] `DiscoveryCacheRefreshResponse.status` changed to `Literal["completed"]` [backend/src/auth/schemas.py]
- [x] [Review][Defer] Concurrent refresh race condition (manual endpoint + scheduled job) [backend/src/auth/idp_router.py] — deferred, acceptable for admin-only tooling with few IdPs
- [x] [Review][Defer] Cache JSON schema validation missing in `get_or_fetch_discovery()` — deferred, Story 2-1 scope (caller validates)
- [x] [Review][Defer] APScheduler non-retry on unhandled exception — deferred, pre-existing APScheduler behavior

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- Module-level imports required in `discovery_refresh.py` (moved `list_identity_providers`, `probe_idp_discovery` to top) so `unittest.mock.patch` can target `src.auth.discovery_refresh.*` in tests.
- Boot invariant test: `scheduler.shutdown(wait=False)` raises `SchedulerNotRunningError` if scheduler was never started. Fixed by calling `scheduler.start()` before adding jobs and wrapping in `try/finally`.
- `get_or_fetch_discovery()` uses naive datetime comparison for SQLite compatibility (same pattern as `retention.py`).

### Completion Notes List

- All 7 ACs satisfied.
- `oidc_discovery.py`: `DISCOVERY_CACHE_TTL_HOURS = 24` constant + `get_or_fetch_discovery()` lazy helper for Story 2-1 login flow.
- `discovery_refresh.py`: `refresh_discovery_cache(force_all)` job — skips disabled and fresh IdPs, per-IdP exception handling, returns summary dict.
- `main.py`: second scheduler job registered with `next_run_time = now + 24h` — boot invariant preserved.
- `idp_router.py`: `POST /discovery-cache/refresh` (ADMIN-only) manual trigger.
- `schemas.py`: `DiscoveryCacheRefreshResponse` added; `discovery_cached_at` added to `IdentityProviderResponse`.
- Frontend: `isDiscoveryCacheStale()` helper + `--color-accent` badge in `IdpProviderListView.vue` and `IdpProviderEditView.vue`.
- i18n: `staleCacheBadge` and `neverCached` in EN/DE/FR/ES.
- Tests: 981 backend (up from 975), 133 Vitest, vue-tsc clean, prod build clean.

### Change Log

- `backend/src/auth/oidc_discovery.py` — Added `DISCOVERY_CACHE_TTL_HOURS`, `get_or_fetch_discovery()`
- `backend/src/auth/discovery_refresh.py` — NEW: `refresh_discovery_cache()` APScheduler job
- `backend/src/auth/idp_router.py` — Added `POST /discovery-cache/refresh` + `DiscoveryCacheRefreshResponse` import
- `backend/src/auth/schemas.py` — Added `DiscoveryCacheRefreshResponse`; added `discovery_cached_at` to `IdentityProviderResponse`
- `backend/src/main.py` — Registered OIDC discovery refresh scheduler job with `next_run_time` deferred
- `backend/tests/auth/test_discovery_refresh.py` — NEW: 5 tests
- `backend/tests/test_boot_invariant.py` — NEW: 1 boot invariant test
- `frontend/src/types/domain.types.ts` — Added `discovery_cached_at: string | null` to `IdpProvider`
- `frontend/src/views/IdpProviderListView.vue` — Added stale cache badge per row
- `frontend/src/views/IdpProviderEditView.vue` — Added stale cache badge in header, `loadedDiscoveryCachedAt` ref
- `frontend/src/i18n/locales/en.ts` — Added `staleCacheBadge`, `neverCached`
- `frontend/src/i18n/locales/de.ts` — Added `staleCacheBadge`, `neverCached`
- `frontend/src/i18n/locales/fr.ts` — Added `staleCacheBadge`, `neverCached`
- `frontend/src/i18n/locales/es.ts` — Added `staleCacheBadge`, `neverCached`

### File List

- `backend/src/auth/oidc_discovery.py`
- `backend/src/auth/discovery_refresh.py`
- `backend/src/auth/idp_router.py`
- `backend/src/auth/schemas.py`
- `backend/src/main.py`
- `backend/tests/auth/test_discovery_refresh.py`
- `backend/tests/test_boot_invariant.py`
- `frontend/src/types/domain.types.ts`
- `frontend/src/views/IdpProviderListView.vue`
- `frontend/src/views/IdpProviderEditView.vue`
- `frontend/src/i18n/locales/en.ts`
- `frontend/src/i18n/locales/de.ts`
- `frontend/src/i18n/locales/fr.ts`
- `frontend/src/i18n/locales/es.ts`
