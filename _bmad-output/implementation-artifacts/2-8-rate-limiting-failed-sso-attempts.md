# Story 2.8: Rate-limiting failed SSO attempts (DB counter)

Status: done

Epic: 2 — SSO User Access
Story Key: `2-8-rate-limiting-failed-sso-attempts`

## Story

As a Security engineer,
I want failed SSO attempts rate-limited per source IP via a DB counter,
so that credential-stuffing or state-enumeration attacks are mitigated
without adding a Redis dependency.

## Context

- `RateLimitCounter` model and `rate_limit_counters` table are already
  shipped (`backend/src/rate_limit.py`, migration
  `b4d2e1a9c3f7_phase4_sso_and_teams.py`).
- APScheduler is already wired in `backend/src/main.py` (retention +
  discovery refresh jobs); adding a cleanup job follows the same
  pattern.
- No existing rate-limiting service — this story introduces
  `src/auth/sso_rate_limit.py`.

## Acceptance Criteria

1. **AC1 — Failure increments per-IP counter.** On every SSO
   failure (init-time `return_to.invalid`, init-time IdP not found,
   any callback failure), the source-IP's counter is incremented
   inside the current 5-min window. Verified by pytest.

2. **AC2 — 429 after threshold.** When a source IP has
   `count ≥ 20` failures in the current 5-min window, subsequent
   SSO init and callback requests return HTTP 429 with
   `Retry-After` header (seconds until window reset). An
   `sso.login.rate_limited` audit event is written. Verified by
   pytest.

3. **AC3 — Success resets counter.** When an SSO callback
   completes successfully, the source IP's counter rows are
   deleted. Verified by pytest.

4. **AC4 — Cleanup job deletes stale counters.** APScheduler job
   (interval 1h, configurable via `RATE_LIMIT_CLEANUP_HOURS`)
   deletes counter rows with `window_start` older than 1 hour.
   Verified by unit test on the cleanup function.

5. **AC5 — Config knob for threshold.** Threshold (20 failures)
   and window (5 min) are defined as module-level constants in
   `sso_rate_limit.py` and documented for future tuning.

6. **AC6 — No regression.** All existing tests continue to pass.

## Tasks / Subtasks

### Task 1: Rate-limit service (AC1, AC3, AC5)

- [x] NEW `backend/src/auth/sso_rate_limit.py`:
  - Module constants: `_WINDOW_SECONDS = 300`, `_THRESHOLD = 20`,
    `_BUCKET_PREFIX = "sso:login:"`.
  - `_window_start(now: datetime) -> datetime`: returns the
    current 5-min bucket start (floor to `_WINDOW_SECONDS`).
  - `record_failure(db, ip: str) -> int`: UPSERT the
    `(bucket_key, window_start)` row and increment its count.
    Returns the new count. Uses `INSERT ... ON CONFLICT` on
    Postgres; falls back to SELECT+UPDATE or SELECT+INSERT on
    SQLite (`dialect.name == "sqlite"`). The module-level
    helper commits the db.
  - `is_rate_limited(db, ip: str) -> tuple[bool, int]`:
    returns (`count >= _THRESHOLD`, `retry_after_seconds`).
  - `reset_failures(db, ip: str) -> None`: deletes all counter
    rows for the bucket (any window). Used on successful login.
  - `cleanup_stale_counters(now: datetime | None = None) -> int`:
    deletes rows with `window_start < now - 1h`. Returns the
    deletion count for logging. Called by APScheduler.

### Task 2: SSO router integration (AC1, AC2, AC3)

- [x] MOD `backend/src/auth/sso_router.py`:
  - `sso_login_initiate`: before any other check, call
    `is_rate_limited(db, client_ip)`. If true, `log_event`
    `sso.login.rate_limited` and return a 429 JSON response with
    `Retry-After` header.
  - Wrap the `return_to.invalid` and "IdP not found" branches to
    also call `record_failure(db, client_ip)` before raising.
  - `sso_callback`: check `is_rate_limited` at the top too (same
    429 path). On failure, add `record_failure`. On success, add
    `reset_failures`.
  - Add `AuditEventType.SSO_LOGIN_RATE_LIMITED` to
    `src/audit/event_types.py`.

### Task 3: Cleanup scheduler (AC4)

- [x] MOD `backend/src/main.py`:
  - Import `cleanup_stale_counters` from the new module.
  - Add `_scheduler.add_job(cleanup_stale_counters,
    trigger=IntervalTrigger(hours=int(os.environ.get(
    "RATE_LIMIT_CLEANUP_HOURS", "1"))), id="sso_rate_limit_cleanup",
    name="SSO rate-limit counter cleanup", replace_existing=True)`.

### Task 4: Tests (AC1–AC4)

- [x] NEW `backend/tests/auth/test_sso_rate_limit.py`:
  - `test_record_failure_increments_counter`
  - `test_record_failure_uses_5_minute_windows`
    — two failures in the same window → count=2;
      rewinding the clock by 6 min → new window, count=1.
  - `test_is_rate_limited_false_below_threshold`
  - `test_is_rate_limited_true_at_threshold` — exactly 20 fails.
  - `test_reset_failures_clears_all_windows`
  - `test_cleanup_stale_counters_removes_old_rows`
  - `test_cleanup_keeps_current_window`

- [x] NEW `backend/tests/auth/test_sso_rate_limit_router.py`:
  - `test_init_returns_429_after_threshold`
  - `test_callback_returns_429_after_threshold`
  - `test_429_includes_retry_after_header`
  - `test_429_writes_audit_event`
  - `test_return_to_invalid_increments_counter`
  - `test_successful_callback_resets_counter`

### Task 5: Regression (AC6)

- [x] Run `pytest backend/tests/ --tb=short` — all green.

## Non-goals

- Global rate limiting (the existing `slowapi` limiter already
  handles that at 1000/min/IP).
- Adaptive thresholds based on user-agent signals.
- Cross-instance sharing (we accept per-instance DB counters for
  single-node deployments; Redis is out of scope).
- CAPTCHA or interactive challenge — out of scope.

## Dev Notes

- Threshold 20/5-min is deliberately loose: a legitimate user
  fat-fingering a corporate email a dozen times in a row should
  not be locked out. Tune down for sensitive deployments.
- Counter rows are per-window — multiple windows may exist per IP
  simultaneously. `reset_failures` deletes ALL windows for the
  bucket, not just the current one, so a user who legitimately
  signs in after some failures is cleared completely.
- Window alignment to wall-clock (floor to 5-min boundaries) is
  simpler than sliding windows and has acceptable cliff behavior
  at this threshold.
