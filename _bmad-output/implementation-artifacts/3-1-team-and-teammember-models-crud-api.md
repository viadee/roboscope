# Story 3.1: Team and TeamMember models + CRUD API

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-1-team-and-teammember-models-crud-api`

## Context

- `Team` and `TeamMember` ORM models already exist at
  `backend/src/teams/models.py` (shipped with Phase-4 migration).
- No service, schemas, or router yet.
- Repository-to-Team FK (`repositories.team_id`) was also added by
  the Phase-4 migration with `ON DELETE SET NULL` — cascade-nullify
  behavior is free on delete.

## Acceptance Criteria

1. **AC1 — Team CRUD for ADMIN.** `POST/GET/PUT/DELETE /teams`
   endpoints; ADMIN role required. `POST` creates a Team with
   `external_id=null`. `DELETE` cascades `team_members` (already
   at DB level via FK ON DELETE CASCADE) and sets
   `repositories.team_id=NULL` (already at DB level via FK ON
   DELETE SET NULL). Every mutating call writes an audit event.

2. **AC2 — Member CRUD.**
   - `POST /teams/{id}/members` with `{user_id, role}` creates a
     row with `source='manual'`; audit `team_member.added`.
   - `PATCH /teams/{id}/members/{mid}` updates role; if the row
     was `source='idp_group_sync'`, flip to `'manual'` to prevent
     the next login-sync from overwriting the admin's change.
   - `DELETE /teams/{id}/members/{mid}` removes membership.
     Audit `team_member.removed`.

3. **AC3 — Listing.** `GET /teams` lists all teams (admin-only
   per AC5). `GET /teams/{id}` returns the team + a member list
   with `{user_id, email, role, source}` tuples.

4. **AC4 — Unique-name constraint surfaces as 400, not 500.**
   Duplicate `POST`/`PUT` on `name` returns `400` with
   `detail="team.name_taken"` (localization key). Verified in
   the tests.

5. **AC5 — 403 for non-ADMIN.** All mutating endpoints require
   ADMIN. `GET` endpoints also require ADMIN in this story (the
   user-is-team-member visibility rule is Story 3.13's concern).

6. **AC6 — Audit events.**
   `team.created`, `team.updated`, `team.deleted`,
   `team_member.added`, `team_member.updated`,
   `team_member.removed` are all added to
   `AuditEventType` and emitted via `log_event`.

7. **AC7 — No regression.** Existing tests still pass.

## Tasks / Subtasks

### Task 1: Audit event types (AC6)

- [x] MOD `backend/src/audit/event_types.py` — append 6 new
  enum values.

### Task 2: Schemas (AC1, AC2, AC3)

- [x] NEW `backend/src/teams/schemas.py` — Pydantic models:
  - `TeamCreate`, `TeamUpdate`, `TeamResponse`
  - `TeamMemberCreate`, `TeamMemberUpdate`, `TeamMemberResponse`
  - `TeamDetailResponse` (team + member list)

### Task 3: Service (AC1, AC2, AC4)

- [x] NEW `backend/src/teams/service.py`:
  - `create_team(db, data)` — IntegrityError on unique name →
    raise `ValueError("team.name_taken")` (router catches).
  - `get_team(db, id)`, `list_teams(db)`, `update_team(db, id, data)`,
    `delete_team(db, id)`.
  - `add_member(db, team_id, data)` — enforces the unique
    (team, user) constraint; same error pattern.
  - `update_member(db, team_id, member_id, data)` — flips
    `source='idp_group_sync'` to `'manual'` on admin edit.
  - `remove_member(db, team_id, member_id)`.
  - `get_team_with_members(db, id)` — joins users for the detail
    response payload.

### Task 4: Router (AC1, AC2, AC3, AC4, AC5, AC6)

- [x] NEW `backend/src/teams/router.py`:
  - 8 endpoints with `require_role(Role.ADMIN)` dep.
  - Each mutating endpoint calls `log_event` with the relevant
    `AuditEventType` and `resource_id = team.id` / `member.id`.
  - Catch `ValueError` from service, translate to `HTTPException
    (400, detail="team.name_taken" | "team.member.already_exists")`.

- [x] MOD `backend/src/api/v1/router.py` — mount:
  `api_router.include_router(teams_router, prefix="/teams", tags=["Teams"])`.

### Task 5: Tests (AC1–AC7)

- [x] NEW `backend/tests/teams/test_service.py` — service-level
  unit tests.
- [x] NEW `backend/tests/teams/test_router.py` — endpoint-level
  tests (auth/role checks, audit event emission, happy paths,
  error paths, source-flip on manual update).

### Task 6: Regression (AC7)

- [x] Run `pytest backend/tests/` — all green.

## Non-goals

- Assigning a repository to a team (Story 3.2).
- Mapping IdP groups to teams (Story 3.3).
- Frontend Team list/detail UI (Story 3.12/3.13).
- Effective-role computation (Story 3.6).
