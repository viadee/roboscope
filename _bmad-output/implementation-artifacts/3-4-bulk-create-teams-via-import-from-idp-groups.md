# Story 3.4: Bulk-create Teams via Import-from-IdP-groups

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-4-bulk-create-teams-via-import-from-idp-groups`

## Context

- Team CRUD + GroupMapping CRUD shipped in 3-1/3-3.
- Story 3-5 will populate a live IdP group cache at login time.
  Until that ships, the only "known groups" we can return are the
  ones already mapped in `IdPGroupMapping`. This story is scoped
  to use that as the authoritative list; Story 3-5 will add the
  login-observed groups into the same endpoint transparently.

## Acceptance Criteria

1. **AC1 — Available-groups endpoint.**
   `GET /api/v1/auth/idp-providers/{id}/available-groups` returns
   the distinct `group_claim_value`s already mapped for the IdP
   (sorted). ADMIN only. Empty list is a valid response. Story
   3-5 extends this to also include login-observed groups; the
   contract is a flat `list[str]`.

2. **AC2 — Bulk import.** `POST /api/v1/teams/import-from-idp-groups`
   with body
   `{idp_id, groups: [{group_name, team_name, role}, ...]}`.
   For each entry:
   - Create Team with name `team_name` (skip if name taken —
     don't fail the whole batch).
   - Create GroupMapping linking `(idp_id, group_name)` to that
     team with `role` (skip if already mapped).
   - Track each row as `created` / `skipped` / `failed`.
   Response: `{created: int, skipped: int, failed: int, team_ids: [int], errors: [str]}`.

3. **AC3 — Atomic per row, not per batch.**
   A failure in one row does NOT roll back earlier successes.
   Verified by a test with one invalid row in a 3-row batch.

4. **AC4 — Audit events.** Each successful row emits both
   `team.created` (reused from 3-1) and `group_mapping.created`
   (reused from 3-3). Already-existing rows do not emit duplicates.

5. **AC5 — ADMIN only.** Both endpoints return 403 for
   non-ADMIN users.

## Tasks / Subtasks

### Task 1: Available-groups endpoint (AC1)

- [x] MOD `backend/src/auth/idp_router.py` — add
  `GET /{id}/available-groups` returning sorted distinct
  `group_claim_value`s from `IdPGroupMapping` filtered by `idp_id`.

### Task 2: Import endpoint (AC2, AC3, AC4)

- [x] NEW schema `TeamImportFromGroupsRequest` +
  `TeamImportRow` + `TeamImportSummary` in
  `backend/src/teams/schemas.py`.
- [x] NEW service
  `import_teams_from_idp_groups(db, idp_id, rows) ->
  TeamImportSummary` in `backend/src/teams/service.py`. Iterate
  `rows`, wrap each in `try/except` + savepoint so per-row
  failures don't roll back the batch.
- [x] MOD `backend/src/teams/router.py` — add
  `POST /import-from-idp-groups` wired to the service + emit
  audit events per successful team / mapping.

### Task 3: Tests (AC1–AC5)

- [x] NEW `backend/tests/teams/test_import_from_groups.py`:
  - `test_available_groups_returns_mapped_groups`
  - `test_available_groups_empty_for_new_idp`
  - `test_import_creates_teams_and_mappings`
  - `test_import_skips_taken_team_names`
  - `test_import_skips_duplicate_mappings`
  - `test_import_reports_failed_row_without_rolling_back_batch`
  - `test_import_emits_audit_events_per_success`
  - `test_editor_forbidden_on_import`
  - `test_editor_forbidden_on_available_groups`

### Task 4: Regression

- [x] `pytest backend/tests/teams/ backend/tests/auth/` all green.

## Non-goals

- Login-observed group cache (Story 3-5).
- Frontend UI for bulk import (Story 3-14).
- Updating existing teams' roles from the import (creates only).
