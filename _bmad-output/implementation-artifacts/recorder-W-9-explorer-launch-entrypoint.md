# Story W.9 — Launch Recorder v2 from the Explorer view

**Type:** BMAD quick story (no user interaction)
**Epic:** recorder-v2-web
**Date:** 2026-04-23

## Background

Story W.7 shipped the sidebar "Recorder" entry and the dedicated `/recordings/new` launcher view. A user sitting inside the Explorer (inspecting / editing a repo's `.robot` tree) currently has to:

1. Leave the Explorer.
2. Click "Recorder" in the sidebar.
3. **Re-pick** the repo they were already standing in.

The `RecordingLauncherView` defaults to the first repo in the list, not the one the user was just looking at. For a user with five or more repos this is a non-trivial speed bump, and it's the first thing anyone asks for after a round-trip.

The Explorer toolbar already has a v1 `⏺ Record` button that drives the legacy per-file `RecorderPanel` flow. The v1 flow is preserved per PRD N-11. The v2 flow is a different session model (browser + SSE + selector picker + repo-relative save), so the v2 entry needs its own button, not a silent replacement of the v1 one.

## Acceptance Criteria

1. **Given** a user (editor+) is viewing a repo in `/explorer/:repoId`, **when** they click a new "Recorder v2" button in the editor toolbar, **then** they are routed to `/recordings/new?repoId=<currentRepoId>`.
2. **Given** the launcher view opens with `?repoId=<N>` in the URL, **when** it mounts, **then** the repo dropdown is pre-selected to repo `N` (assuming the user can see that repo).
3. **Given** the launcher view opens **without** a `repoId` query param, **when** it mounts, **then** it falls back to the existing behaviour (first repo in the list) — no regression for users reaching the launcher via the sidebar.
4. **Given** the `?repoId=<N>` param points at a repo the user can't see (deleted, revoked), **when** the launcher mounts, **then** it silently falls back to the first available repo — no error surface.
5. The v1 `⏺ Record` button continues to exist and behave exactly as before. PRD N-11 remains intact.
6. **i18n:** the new button's label + tooltip ship in EN/DE/FR/ES.
7. **Docs:** the in-app Recorder documentation (`frontend/src/docs/content/*.ts`) mentions the new Explorer entry point. The root `README.md` mentions the v2 recorder + the two entry points (sidebar and Explorer).
8. **Non-goal:** no e2e browser test for this story. Type-check + manual-sanity is sufficient — the wiring is two lines plus a query-param read.

## Files touched

- `frontend/src/views/RecordingLauncherView.vue` — read `repoId` from `route.query`; clamp to `reposStore.repos`.
- `frontend/src/views/ExplorerView.vue` — add `⏺ Recorder v2` button next to existing `⏺ Record` button.
- `frontend/src/i18n/locales/{en,de,fr,es}.ts` — `explorer.recorderV2` + `explorer.recorderV2Title` keys.
- `frontend/src/docs/content/{en,de,fr,es}.ts` — recorder section mentions the Explorer entry point.
- `README.md` — one-line update to the recorder section.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — new story entry under `epic-recorder-v2-web`.

## Non-goals

- Pre-populating the "save path" with the currently-selected file path. Out of scope — the v2 live view already prompts for a path and has its own default. Adding a `?path=` passthrough is a follow-up.
- Replacing or removing the v1 record button. PRD N-11 lock.
- Frontend unit test — the change is a query-param read + a `router.push`. Keeping the test budget for higher-value stories.
