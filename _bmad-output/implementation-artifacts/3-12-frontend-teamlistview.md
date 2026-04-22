# Story 3.12: Frontend TeamListView

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-12-frontend-teamlistview`

## Context

- Backend Team CRUD shipped in Story 3-1 (`/api/v1/teams`).
- Bulk import endpoint shipped in Story 3-4
  (`/api/v1/teams/import-from-idp-groups`).
- No frontend API client, store, or view yet.

## Acceptance Criteria

1. **AC1 — Route.** `/admin/teams` renders the view; requires
   ADMIN role (router guard check). New route registered.

2. **AC2 — Empty state.** When no Teams exist, show a centered
   empty-state with heading + description and two equal-weight
   primary CTAs: `[+ New Team]` and `[Import from IdP groups]`.

3. **AC3 — Populated table.** When Teams exist, render a
   `.data-table` with columns: Name, Members, Repositories,
   Created. Each row has action buttons: View/Edit (→
   `/admin/teams/:id`), Delete.

4. **AC4 — Header actions.** Above the table: `[+ New Team]` and
   `[Import from IdP groups]` buttons (same destinations as the
   empty-state CTAs).

5. **AC5 — Search + sort.** A search box filters the table
   client-side (debounce 300 ms). A header click toggles sort
   by Name ↔ Members (ascending/descending). No API round-trips
   for filter/sort.

6. **AC6 — Delete confirmation.** Clicking Delete opens a
   `BaseModal` with the team name, destructive copy, and two
   buttons (Cancel / Delete). Delete calls the API and removes
   the row from the list.

7. **AC7 — i18n.** All copy in EN/DE/FR/ES under `teams.list.*`.
   vue-i18n prod-build passes (escape special chars).

8. **AC8 — Non-ADMIN is redirected.** Existing router guard
   already handles `minRole: 'admin'`. No new guard logic needed.

9. **AC9 — Tests.** Vitest unit tests for:
   - Empty-state renders both CTAs
   - Populated table renders N rows
   - Search filters rows
   - Sort toggle works
   - Delete modal flow
   - API error path shows toast (or error row)

## Tasks / Subtasks

### Task 1: API client (AC1, AC3, AC6)

- [x] NEW `frontend/src/api/teams.api.ts`:
  - `listTeams()` → `Team[]`
  - `getTeam(id)` → `TeamDetail`
  - `createTeam({name, description?})` → `Team`
  - `updateTeam(id, {name?, description?})` → `Team`
  - `deleteTeam(id)` → void

### Task 2: Types + Pinia store (AC1, AC3)

- [x] MOD `frontend/src/types/domain.types.ts` — add `Team`,
  `TeamMember`, `TeamDetail` interfaces.

- [x] NEW `frontend/src/stores/teams.store.ts` — setup store
  exposing `teams`, `loading`, `error`, and actions
  (`load`, `create`, `remove`).

### Task 3: TeamListView.vue (AC1–AC6)

- [x] NEW `frontend/src/views/TeamListView.vue` —
  SFC with script setup; copies the admin-list layout from
  `IdpProviderListView.vue` where applicable.

### Task 4: Router + i18n (AC1, AC7)

- [x] MOD `frontend/src/router/index.ts` — add `/admin/teams`
  route (`minRole: 'admin'`, `requiresAuth: true`).

- [x] MOD all 4 locale files — `teams.list.*` namespace.

### Task 5: Tests (AC9)

- [x] NEW `frontend/src/tests/components/TeamListView.spec.ts`.

### Task 6: Regression

- [x] Run `npx vitest run` — all green.
- [x] `npx vue-tsc --noEmit` clean.

## Non-goals

- The `[Import from IdP groups]` CTA is a stub that navigates to
  a route that Story 3-14 will implement. For 3-12 it navigates
  to `/admin/teams/new` (the "New Team" route). A follow-up
  wires the separate import wizard.
- Team detail/edit view (Story 3-13).
- Group-mapping row component (Story 3-14).
