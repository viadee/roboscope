# Stories 3.7–3.11: Effective-role migration across domain routers

Status: done

Epic: 3 — Teams & Role Resolution
Story Keys:
  - `3-7-migrate-repos-endpoints-to-require-effective-role`
  - `3-8-migrate-runs-endpoints-to-require-effective-role`
  - `3-9-migrate-reports-endpoints-to-require-effective-role`
  - `3-10-migrate-explorer-endpoints-to-require-effective-role`
  - `3-11-migrate-stats-endpoints-to-require-effective-role`

Shipped bundled because the migration pattern is mechanical once
per-resource dependency helpers exist; the test coverage is what
localizes regression risk (Story 3-6's effective-role invariants
are already locked in).

## Scope decisions (grenzfall exceptions)

The spec said "migrate repo-scoped endpoints". We interpret that as:
- Endpoints with a **repo_id path parameter** → use
  `require_effective_role(min_role)`.
- Endpoints with a **run_id path parameter** → use
  `require_effective_role_for_run(min_role)` which resolves the
  repo via `run.repository_id`.
- Endpoints with a **report_id path parameter** → use
  `require_effective_role_for_report(min_role)` which resolves the
  repo via `report → run → repo`.
- Endpoints **without a resource scope** (e.g., `DELETE /reports/all`,
  `POST /stats/aggregate`, schedules not tied to a repo) stay on
  `require_role` — they are global operations by design.
- `GET` list endpoints that already filter by user (e.g.,
  `GET /repos` already returns visibility-filtered results) are
  left untouched; they return what the caller can see.

## Acceptance Criteria (shared)

1. Existing test suite continues to pass (repos/runs/reports/stats
   endpoint tests) — the migration is a pure refinement; admin
   global still passes.
2. A new smoke test per domain asserts that a VIEWER-global user
   who is an editor via Team membership on the repo is permitted
   by the migrated endpoint (proving elevation flows through).
3. `require_effective_role_for_run` and
   `require_effective_role_for_report` helpers ship with unit
   tests covering missing-resource (404) paths.

## Tasks

### Task 1: Dependency helpers

- [x] MOD `backend/src/auth/dependencies.py`:
  - `require_effective_role_for_run(min_role)` — reads `run_id`,
    resolves `run.repository_id` → calls existing logic.
  - `require_effective_role_for_report(min_role)` — reads
    `report_id`, joins report → run → repo, reuses logic.

### Task 2: Migrate `/repos/*` (Story 3.7)

- [x] MOD `backend/src/repos/router.py`:
  - `/{repo_id}/sync`, `/{repo_id}/checkout`, patch/delete on repo,
    `/{repo_id}/members/*`, `/{repo_id}/team` all take `repo_id`
    in path — switch to `require_effective_role`.

### Task 3: Migrate `/runs/*` (Story 3.8)

- [x] MOD `backend/src/execution/router.py`:
  - `/runs/{run_id}/cancel`, `/runs/{run_id}/retry` — use
    `require_effective_role_for_run(RUNNER)`.

### Task 4: Migrate `/reports/*` (Story 3.9)

- [x] MOD `backend/src/reports/router.py`:
  - `/reports/{report_id}/missing-libraries` and any mutating
    per-report endpoint — use
    `require_effective_role_for_report`. GET endpoints on
    reports stay readable (no current role-gating on most GETs).

### Task 5: Migrate `/explorer/*` (Story 3.10)

- [x] Explorer router has zero `require_role` usages — already
  uses the user object alone. No-op migration; document the
  pass-through.

### Task 6: Migrate `/stats/*` (Story 3.11)

- [x] `/stats/analysis` (POST, RUNNER) is the only gated one —
  stays on `require_role(RUNNER)` because it's a global admin
  operation not scoped to a single repo. Document as grenzfall.

### Task 7: Tests

- [x] NEW `backend/tests/auth/test_effective_role_endpoints.py`
  — smoke tests for each domain proving team-grant elevation.

- [x] MOD dependency tests from 3-6 if needed to cover the two
  new helpers.

## Tests

Per shared AC2, each domain gets a smoke test of the form:
  - Create a viewer user.
  - Create a team and add the viewer as editor.
  - Create a repo assigned to the team.
  - Attempt a gated endpoint on that repo.
  - Assert: 2xx (elevation succeeded).

## Non-goals

- Refactoring global-scope endpoints to invent a repo scope.
- Rewriting explorer router (no role guards today).
- Frontend rendering changes (Epic 3 frontend stories 3-12 → 3-14).
