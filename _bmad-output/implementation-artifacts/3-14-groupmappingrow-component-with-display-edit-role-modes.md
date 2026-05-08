# Story 3.14: GroupMappingRow component with Display/Edit-Role modes

Status: done

Epic: 3 — Teams & Role Resolution
Story Key: `3-14-groupmappingrow-component-with-display-edit-role-modes`

## Context

- Story 3-13 renders the mapping list as read-only rows.
- No backend PATCH endpoint for group-mapping role yet — this
  story ships it alongside the frontend component so the round-
  trip is real.

## Acceptance Criteria

1. **AC1 — Backend PATCH endpoint.**
   `PATCH /api/v1/group-mappings/{id}` with `{role}` updates
   the row and writes an audit event
   `group_mapping.updated`. ADMIN-only. 404 for unknown id.

2. **AC2 — `GroupMappingRow` component.** New SFC with two
   modes:
   - Display: shows IdP id, group name, role badge (clickable),
     plus delete link.
   - Edit: shows a `<select>` for role + Save/Cancel.

3. **AC3 — Enter or click enters edit mode.** Pressing Enter on
   the focused role badge OR clicking it opens Edit mode with
   focus on the select.

4. **AC4 — Enter submits; Escape cancels.** In Edit mode:
   - Enter → submit → return to Display.
   - Escape → discard → return to Display.

5. **AC5 — Keyboard-only path.** Tab through row → role badge
   → delete link; Enter to open edit; Arrow Up/Down cycles
   options in the native select; Enter to submit.

6. **AC6 — Integration with `TeamDetailView`.** The mappings
   tab now renders `GroupMappingRow` per mapping (replaces the
   inline read-only loop from 3-13).

7. **AC7 — Tests.** Vitest: display→edit switch on click,
   on Enter, Escape cancels, submit calls store, role badge
   has correct aria-label.

## Tasks / Subtasks

### Task 1: Backend PATCH (AC1)

- [x] MOD `backend/src/teams/schemas.py` — `GroupMappingUpdate
  { role }` schema.
- [x] MOD `backend/src/teams/service.py` —
  `update_group_mapping(db, id, data) -> IdPGroupMapping | None`.
- [x] MOD `backend/src/teams/router.py` — new
  `@group_mappings_router.patch("/{mapping_id}")` endpoint
  with audit event.
- [x] MOD `backend/src/audit/event_types.py` —
  `GROUP_MAPPING_UPDATED = "group_mapping.updated"`.

### Task 2: Frontend API + store (AC1, AC6)

- [x] MOD `frontend/src/api/teams.api.ts` —
  `updateGroupMapping(mappingId, {role})`.
- [x] MOD `frontend/src/stores/teams.store.ts` —
  `updateGroupMappingRole(mappingId, role)` updates the row
  in `groupMappings` ref.

### Task 3: GroupMappingRow.vue (AC2–AC5)

- [x] NEW `frontend/src/components/teams/GroupMappingRow.vue`.

### Task 4: Wire into TeamDetailView (AC6)

- [x] MOD `frontend/src/views/TeamDetailView.vue` — use
  `<GroupMappingRow>` in the mappings list.

### Task 5: Tests (AC7)

- [x] NEW `frontend/src/tests/components/GroupMappingRow.spec.ts`.
- [x] NEW `backend/tests/teams/test_group_mapping_update.py`.

### Task 6: Regression

- [x] `pytest` + `vitest` + `vue-tsc` all green.

## Non-goals

- Batch updates across rows.
- Role-change confirmation modal (single-click save is OK for
  this affordance).
