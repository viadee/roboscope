# Story FLAKY-1 — Flaky-test quarantine

**Type:** BMAD quick story (CI hygiene)
**Date:** 2026-04-24

## Background

RoboScope already **detects** flaky tests (`/stats/flaky` + the existing `FlakyTest` table in the Stats view). What's missing is the follow-up every CI team needs once they see that data: the ability to **quarantine** a flaky test — mark it as known-unreliable so it doesn't keep breaking the pipeline while the root cause is investigated.

FLAKY-1 adds the persistence + UI layer for quarantine. The runner-side "actually skip quarantined tests at execution time" is a follow-up story (FLAKY-2) — this one ships the data model, the mark/unmark workflow, and the "is quarantined" surface so teams can start using it immediately as an informational signal while the skip-on-execute lands next.

## Acceptance Criteria

1. **Given** the Stats view's Flaky-Tests table is rendered, **when** an admin/editor clicks the new "Quarantine" action next to a test row, **then** that test's `(repository_id, suite_name, test_name)` tuple is persisted in a new `flaky_quarantine` table with the caller's user id, timestamp, and an optional reason string.
2. **Given** a test is already quarantined, **when** the same table is rendered, **then** its row shows a distinct "quarantined" badge and the action flips from "Quarantine" to "Unquarantine".
3. **Given** the admin clicks "Unquarantine", **then** the row is removed from the quarantine table and the badge disappears.
4. **Only editor+ users** see the Quarantine / Unquarantine button. Viewers + runners see the badge but no action.
5. **Endpoint** `GET /api/v1/stats/quarantine` returns all current quarantine entries, optionally filtered by `repository_id`.
6. **Endpoint** `POST /api/v1/stats/quarantine` accepts `{repository_id, suite_name, test_name, reason?}` and creates the entry. Idempotent — re-marking the same tuple returns 200 without duplicating.
7. **Endpoint** `DELETE /api/v1/stats/quarantine/{id}` removes a quarantine entry. 404 if missing, 403 if caller isn't editor+.
8. **`/stats/flaky` response** gains an `is_quarantined: bool` field on each `FlakyTest` so the table can render badge + button state in a single fetch.
9. **Migration** adds `flaky_quarantine` table with composite unique index `(repository_id, suite_name, test_name)` to enforce idempotency at the DB level.
10. **Audit** — quarantine + unquarantine emit `AuditEventType` entries so admins can reconstruct who silenced what.
11. **i18n** keys in EN/DE/FR/ES.
12. **Tests** — create + idempotent re-create + unquarantine + 404 + 403 (viewer) + `/stats/flaky` returns `is_quarantined` correctly.

## Out of scope (deferred to FLAKY-2)

- Actually skipping quarantined tests at execution time. Requires either a pre-filter in `execute_test_run` or a `--skip-pattern` forwarded to `robot`. Worth a dedicated story because the runner integration needs its own tests.
- Auto-unquarantining after N stable runs — useful, but adds scheduler + policy surface.
- Expiry / TTL on quarantine entries — simpler to keep them permanent until an admin removes them explicitly.
- Team-scoped vs repo-scoped quarantine differences.
