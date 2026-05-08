# Story 3.2: Repository-to-Team assignment

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-2-repository-to-team-assignment`

## Context

- `Repository.team_id` FK already exists (Phase-4 migration,
  `ondelete="SET NULL"`). `backend/src/repos/models.py:33-35`.
- Team CRUD shipped in Story 3-1.
- No endpoint to assign or unassign the team yet.

## Acceptance Criteria

1. **AC1 — PUT `/api/v1/repos/{repo_id}/team`.** Body `{team_id: int | null}`.
   ADMIN-only. On non-null `team_id`, validates that the team exists; 404 if
   not. Updates `repositories.team_id`, writes audit
   `repository.team_assigned` (detail `{team_id}`).

2. **AC2 — Unassign via null.** PUT with `{team_id: null}` clears the
   assignment and writes audit `repository.team_unassigned`.

3. **AC3 — GET inheritance.** `GET /api/v1/repos/{repo_id}` continues
   to return `team_id` (schema already exposes it — this AC asserts the
   behavior is preserved after the PUT).

4. **AC4 — Cascade on team delete.** Deleting a team sets
   `repositories.team_id` to NULL (DB-level cascade, already defined;
   asserted once in this story via a service-level test bypassing
   SQLite's FK enforcement by using a direct UPDATE or a guarded
   migration-level test).

5. **AC5 — 404 on unknown team.** PUT with a non-existent `team_id`
   returns 404; no mutation persists.

6. **AC6 — Audit event types.** `REPOSITORY_TEAM_ASSIGNED`,
   `REPOSITORY_TEAM_UNASSIGNED` added to `AuditEventType`.

## Tasks / Subtasks

### Task 1: Audit events (AC6)

- [x] MOD `backend/src/audit/event_types.py` — add 2 enum values.

### Task 2: Schemas + router endpoint (AC1, AC2, AC5)

- [x] NEW schema `RepoTeamAssignRequest` with `team_id: int | None`
  in `backend/src/repos/schemas.py`.
- [x] NEW endpoint `PUT /{repo_id}/team` in `backend/src/repos/router.py`:
  - ADMIN role required.
  - Validate repo exists (404).
  - If `team_id` given: validate team exists (404).
  - Update `repo.team_id`, commit, emit audit
    `repository.team_assigned` / `.team_unassigned`.

### Task 3: Tests (AC1–AC5)

- [x] NEW `backend/tests/repos/test_team_assignment.py`:
  - `test_assign_team_as_admin_updates_team_id_and_emits_audit`
  - `test_unassign_team_emits_unassigned_audit`
  - `test_assign_nonexistent_team_returns_404`
  - `test_editor_cannot_assign_team` (expect 403)
  - `test_repo_not_found_returns_404`

### Task 4: Regression

- [x] `pytest backend/tests/` all green.

## Non-goals

- Effective-role computation (Story 3-6).
- Frontend UI for assignment (Story 3-12 / 3-13).
