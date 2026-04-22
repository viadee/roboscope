# Story 3.5: Login-time group sync (inline transactional)

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-5-login-time-group-sync`

## Context

Story 2-2's `handle_sso_callback` already implements inline
group sync at
`backend/src/auth/oidc_callback_service.py:_sync_team_memberships`.
It runs in the same DB transaction as user-upsert, diffs
`IdPGroupMapping` rows against the claimed `groups` array, and
updates/adds/removes membership rows with `source='idp_group_sync'`.

This story:
1. Locks in the 3-5 AC contract with a dedicated test module
   (independent of the 2-2 callback happy-path tests, so
   regressions to the sync semantic fail loudly).
2. Adds a lightweight **seen-groups cache** so the Story 3-4
   `/available-groups` endpoint also reflects groups observed at
   login time — even if no mapping exists yet.

## Acceptance Criteria

1. **AC1 — Inline transactional sync.** Membership sync happens
   in the SAME DB transaction as the user-upsert and BEFORE JWT
   issuance. Verified by a test that forces a sync failure and
   asserts: `User` row absent, no `TeamMember` rows, no JWT
   token issued (callback returns 3xx → `/sso-error`).

2. **AC2 — Idempotent re-sync.** Calling the callback twice
   with identical claims does not duplicate `TeamMember` rows
   and emits no unnecessary writes on the second pass.

3. **AC3 — Manual grants preserved.** A `TeamMember` row with
   `source='manual'` is NOT removed by the sync even when the
   user is no longer in the corresponding IdP group.

4. **AC4 — Role drift updates.** If a mapping's role changes
   between two logins, the user's existing
   `source='idp_group_sync'` row's role is updated (not a
   delete+insert).

5. **AC5 — DB error rolls back.** If `_sync_team_memberships`
   raises a `SQLAlchemyError`, the callback does not issue a
   JWT, writes an `sso.login.failure` audit with
   `reason='sync.failed'`, and redirects to `/sso-error`.

6. **AC6 — Seen-groups cache.** Every successful login
   persists the claimed `groups` list into a lightweight cache
   keyed by `idp_id`. The `/available-groups` endpoint returns
   the union of (mapped groups, cached seen groups).

## Tasks / Subtasks

### Task 1: Seen-groups cache service (AC6)

- [x] NEW `backend/src/auth/seen_groups.py`:
  - `record_seen_groups(db, idp_id, groups)` — UPSERTs a row
    per `(idp_id, group_claim_value)` into a new
    `idp_seen_groups` table, or just stores JSON under a
    settings key (`sso.seen_groups.<idp_id>`) capped at 200
    entries. Decision: **settings-key approach** — avoids a
    migration for a cache of short strings.
  - `list_seen_groups(db, idp_id) -> list[str]` — returns the
    deduplicated cached list.

- [x] MOD `backend/src/teams/service.py` —
  `list_available_groups_for_idp` unions the mapped set with
  `list_seen_groups(idp_id)`.

- [x] MOD `backend/src/auth/oidc_callback_service.py` —
  after successful sync, call
  `record_seen_groups(db, idp.id, claims.get('groups', []))`.

### Task 2: Tests (AC1–AC6)

- [x] NEW `backend/tests/auth/test_login_group_sync.py`:
  - `test_sync_is_idempotent_on_repeat_login`
  - `test_manual_grants_survive_sync`
  - `test_role_drift_updates_existing_row`
  - `test_db_error_rolls_back_and_returns_sso_error`
    (reuses the test_sso_callback fixture).

- [x] NEW `backend/tests/auth/test_seen_groups.py`:
  - `test_record_seen_groups_persists_distinct_values`
  - `test_list_seen_groups_returns_cached`
  - `test_available_groups_endpoint_includes_seen_groups`

### Task 3: Regression

- [x] `pytest backend/tests/` all green.

## Non-goals

- New table for seen groups (use settings key to avoid migration).
- Rate-limiting or time-decay of the seen-groups cache (out of
  scope; Phase-5 concern if it becomes large).
