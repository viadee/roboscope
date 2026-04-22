# Story 3.6: `effective_role()` function + require_effective_role dependency

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-6-effective-role-function-and-dependency`

## Context

- Role hierarchy: `VIEWER (0) < RUNNER (1) < EDITOR (2) < ADMIN (3)`
  (`backend/src/auth/constants.py:14-30`).
- `ProjectMember` (repo-level) exists with `role` column.
- `Team` + `TeamMember` (team-level) from 3-1.
- `Repository.team_id` (team assignment) from 3-2.
- No unified resolution function yet — existing endpoints call
  `require_role(Role.ADMIN/EDITOR/...)` which only looks at
  `user.role` (global).

## Acceptance Criteria

1. **AC1 — Pure additive resolution.**
   `effective_role(db, user, repo) -> Role` returns
   `max(user.role, team_role_for(user, repo),
   project_member_role(user, repo))` via `ROLE_HIERARCHY` values.
   No deny semantics — always additive.

2. **AC2 — Table-driven unit coverage.** A parametrized test
   covers every meaningful combination of
   `(global_role, team_role, project_role)` producing a distinct
   result. Includes cases where one or more contributors are
   absent (None).

3. **AC3 — Zero-team repo is regression-safe.** When
   `repo.team_id` is NULL, `effective_role` reduces to
   `max(global, project)` — identical to pre-Phase-4 behavior.

4. **AC4 — FastAPI dependency `require_effective_role(min_role)`.**
   Works on routes with a `repo_id` path parameter. Resolves the
   repo, computes effective role, returns 403 if below threshold.
   Returns 404 if the repo is missing.

5. **AC5 — Side-by-side with `require_role`.** The new dependency
   is additive — no existing routes touched in this story
   (migrations are Stories 3.7–3.11).

6. **AC6 — No regression.** All existing tests pass.

## Tasks / Subtasks

### Task 1: Resolution helpers (AC1, AC2, AC3)

- [x] NEW `backend/src/auth/permissions.py`:
  - `team_role_for_repo(db, user, repo) -> Role | None` —
    returns the team-level role if the user is a member of the
    team assigned to the repo; None otherwise. Uses a single
    join via SQLAlchemy.
  - `project_member_role(db, user, repo) -> Role | None` —
    returns the `ProjectMember.role` if one exists.
  - `effective_role(db, user, repo) -> Role` — additive MAX over
    the three contributors, coerced to `Role`. Cached on the
    request via `functools.cache` is NOT appropriate (DB state
    can change); just recompute.

### Task 2: FastAPI dependency (AC4, AC5)

- [x] MOD `backend/src/auth/dependencies.py` — add
  `require_effective_role(min_role: Role)` factory that returns
  a dependency reading `repo_id` from path + `current_user` +
  `db`, resolving and enforcing.

### Task 3: Tests (AC1–AC4)

- [x] NEW `backend/tests/auth/test_effective_role.py` —
  table-driven with pytest.parametrize covering ~20 combinations
  of (global, team, project), plus:
  - `test_team_only_membership`
  - `test_project_only_membership`
  - `test_both_memberships_takes_max`
  - `test_no_team_no_project_reduces_to_global`
  - `test_user_not_member_of_team_ignores_team_role`
  - `test_repo_with_null_team_id_regression_safe`

- [x] NEW `backend/tests/auth/test_require_effective_role.py` —
  integration tests that mount a trivial endpoint using the new
  dependency and assert the 403/404/200 branches.

### Task 4: Regression

- [x] `pytest backend/tests/` all green.

## Non-goals

- Migrating any existing endpoints — covered in Stories 3.7–3.11.
- Caching / memoization of resolution results.
- API-token role-cap (Story 3.15).
