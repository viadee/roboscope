# Story 3.3: IdP group-to-Team mapping

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-3-idp-group-to-team-mapping`

## Context

- `IdPGroupMapping` ORM model + unique constraint
  `(idp_id, group_claim_value)` exist
  (`backend/src/auth/models.py:51-69`).
- No CRUD endpoints yet.
- The login-time group sync (Story 3.5) will consume these
  rows — this story only provides the admin surface.

## Acceptance Criteria

1. **AC1 — Create mapping under a team.**
   `POST /api/v1/teams/{team_id}/group-mappings` with
   `{idp_id, group_name, role}`. ADMIN only. Returns 201
   with the created row. Writes audit `group_mapping.created`.

2. **AC2 — Duplicate (idp_id, group_claim_value) returns 409.**
   Second create with the same `(idp_id, group_name)` returns
   HTTP 409 Conflict with `detail="group_mapping.duplicate"`.

3. **AC3 — List mappings for a team.**
   `GET /api/v1/teams/{team_id}/group-mappings` returns the
   list for that team. ADMIN only.

4. **AC4 — Delete.**
   `DELETE /api/v1/group-mappings/{id}` removes the row; 204.
   Writes audit `group_mapping.deleted`. 404 if not found.

5. **AC5 — Foreign key validation.** `POST` with a missing
   `idp_id` or `team_id` returns 404.

6. **AC6 — Non-ADMIN → 403** on all endpoints.

7. **AC7 — Audit event types.**
   `GROUP_MAPPING_CREATED`, `GROUP_MAPPING_DELETED` added
   to `AuditEventType`.

## Tasks / Subtasks

### Task 1: Audit events (AC7)

- [x] MOD `backend/src/audit/event_types.py` — 2 new entries.

### Task 2: Schemas + service (AC1–AC5)

- [x] NEW schemas in `backend/src/teams/schemas.py`:
  `GroupMappingCreate`, `GroupMappingResponse`.
- [x] NEW service in `backend/src/teams/service.py`:
  `create_group_mapping`, `list_group_mappings_for_team`,
  `delete_group_mapping`. Duplicate → `ValueError(
  "group_mapping.duplicate")`.

### Task 3: Router (AC1, AC2, AC3, AC4, AC6)

- [x] MOD `backend/src/teams/router.py`:
  - `POST /{team_id}/group-mappings` (201, catches ValueError → 409).
  - `GET /{team_id}/group-mappings`.
  - A second router for `DELETE /group-mappings/{id}` —
    mounted under `/api/v1` alongside teams.
- [x] MOD `backend/src/api/v1/router.py` — add the delete
  router under `/group-mappings` prefix, tag=`Teams`.

### Task 4: Tests (AC1–AC6)

- [x] NEW `backend/tests/teams/test_group_mappings.py`
  with: create/duplicate/list/delete + FK-404 + editor-403.

### Task 5: Regression

- [x] `pytest backend/tests/teams/ backend/tests/auth/` all green.

## Non-goals

- Login-time group sync (Story 3.5 consumes these rows).
- Bulk import from live IdP group lists (Story 3.4).
- Frontend UI for mappings (Story 3-14).
