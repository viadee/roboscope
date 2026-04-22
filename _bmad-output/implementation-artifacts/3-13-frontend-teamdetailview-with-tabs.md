# Story 3.13: Frontend TeamDetailView with tabs

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-13-frontend-teamdetailview-with-tabs`

## Context

- Backend Team detail endpoint already returns
  `{..., members: [{id, user_id, email, role, source}]}` from Story 3-1.
- Group-mapping CRUD shipped in 3-3; available-groups in 3-4.
- Team-to-repo assignment shipped in 3-2; list of repos via
  `GET /api/v1/repos` already filters to what the user sees.
- TeamListView (3-12) routes `/admin/teams/:id` here.

## Acceptance Criteria

1. **AC1 — Route + view.** `/admin/teams/:id` renders
   `TeamDetailView.vue` with a header (team name + description)
   and three tabs: Members / Group Mappings / Repositories.

2. **AC2 — New Team at `/admin/teams/new`.** Same component
   handles the "new team" path by showing only a minimal form
   (name, optional description) and hiding tabs until saved.

3. **AC3 — Per-tab empty states.** Each tab renders its own
   empty-state with a single CTA when empty (e.g., "No members
   yet. [+ Add member]").

4. **AC4 — Members tab.** Shows the member list, with
   `[+ Add member]` (email text input + role dropdown,
   submit), and per-row delete. Role change handled via
   Story 3-14 inline editing — for this story we just
   render role as read-only text (Story 3-14 adds the
   interactive editing).

5. **AC5 — Group Mappings tab.** Shows the mappings list
   via `GET /api/v1/teams/{id}/group-mappings`. `[+ Add
   mapping]` opens a form: IdP dropdown + group picker
   (calls `/idp-providers/{id}/available-groups`, falls back
   to text input when the list is empty) + role dropdown.
   Per-row delete via `DELETE /group-mappings/{id}`.

6. **AC6 — Repositories tab.** Read-only list of repos where
   `team_id === team.id`, derived from the existing
   `GET /api/v1/repos` response. Empty-state with informational
   copy; actual assign/unassign happens on the repo detail
   page (Story 3-2 already ships the endpoint).

7. **AC7 — Tabs are keyboard-navigable.** Tab key moves focus,
   Arrow Left/Right switches tabs; `role="tablist"` +
   `role="tab"` + `aria-selected` wired.

8. **AC8 — i18n.** All copy in EN/DE/FR/ES under
   `teams.detail.*`. vue-i18n prod-build passes.

9. **AC9 — Tests.** Vitest:
   - Route `/admin/teams/new` renders the form, not the tabs.
   - Tabs render for an existing team.
   - Members tab: add / delete member round-trip.
   - Group Mappings tab: add mapping round-trip.
   - Repositories tab: renders only team-assigned repos.
   - Keyboard: Arrow Right moves to next tab.

## Tasks / Subtasks

### Task 1: Types + API (AC4, AC5, AC6)

- [x] MOD `frontend/src/types/domain.types.ts`:
  - `GroupMapping { id, idp_id, team_id, group_claim_value, role }`
  - `GroupMappingCreate { idp_id, group_name, role }`.

- [x] MOD `frontend/src/api/teams.api.ts`:
  - `addMember(teamId, {user_id, role})`
  - `removeMember(teamId, memberId)`
  - `listGroupMappings(teamId)`
  - `createGroupMapping(teamId, {idp_id, group_name, role})`
  - `deleteGroupMapping(mappingId)` (hits
    `/api/v1/group-mappings/{id}`).
  - `listAvailableGroups(idpId)` — hits
    `/auth/idp-providers/{id}/available-groups`.

### Task 2: Store updates (AC4, AC5)

- [x] MOD `frontend/src/stores/teams.store.ts`:
  - `loadDetail(id)` — loads a single team with members.
  - Inline member add/delete and mapping CRUD.

### Task 3: TeamDetailView.vue (AC1, AC2, AC3, AC7)

- [x] NEW `frontend/src/views/TeamDetailView.vue`:
  - Reads `route.params.id`; if `new`, shows minimal create form.
  - Tabs with `role="tablist"` + arrow-key navigation.
  - Each tab component extracted inline or as sibling SFCs:
    - `TeamMembersTab.vue`
    - `TeamGroupMappingsTab.vue`
    - `TeamRepositoriesTab.vue`
  - Keep all tab components in this story; Story 3-14 adds
    inline role editing to `TeamGroupMappingsTab`.

### Task 4: Router + i18n (AC1, AC2, AC8)

- [x] MOD `frontend/src/router/index.ts`:
  - `/admin/teams/new` → TeamDetailView (with `id=new` marker).
  - `/admin/teams/:id` → TeamDetailView.

- [x] MOD all 4 locale files — `teams.detail.*` namespace.

### Task 5: Tests (AC9)

- [x] NEW `frontend/src/tests/components/TeamDetailView.spec.ts`.

### Task 6: Regression

- [x] `npx vitest run` + `npx vue-tsc --noEmit` all green.

## Non-goals

- Inline role editing on group mappings (Story 3-14).
- `@axe-core/playwright` CI wiring (Story 4-8).
- User-picker autocomplete (takes email, keeps it simple — a
  dropdown would need paginated user API that isn't in scope).
