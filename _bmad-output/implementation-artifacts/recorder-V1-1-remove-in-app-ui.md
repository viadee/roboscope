# Story V1.1 — Retire the v1 in-app Recorder UI from the Explorer

**Type:** BMAD quick story (cleanup, no user interaction)
**Date:** 2026-04-23

## Background

Phase Recorder v2 has been shipped end-to-end (Epic W / Epic S / Epic D) and is reachable from two entry points since story W.9:

1. Sidebar "Recorder" → v2 launcher.
2. Explorer toolbar "Recorder v2" button → v2 launcher with repo pre-selected.

The v1 in-app recorder (toolbar button "⏺ Record" + `RecorderPanel.vue` + `recorder.store.ts` + the v1 WebSocket event stream) duplicates a subset of this functionality but with a worse UX: no selector picker, no transport choice, no repo-relative save path, no SSE. It exists because v2 was incremental. Now that v2 is full, the v1 Explorer entry point is pure clutter and two buttons with near-identical glyphs confuse users.

## What stays, what goes

**Goes:**

- The v1 "⏺ Record" button in `ExplorerView.vue` (the one driven by `useRecorderStore().startBrowserSession`).
- The `<RecorderPanel />` mount in `ExplorerView.vue`.
- The `RecorderPanel.vue` component file itself.
- The `handleRecord()` handler in `ExplorerView.vue`.
- The `useRecorderStore` import inside `ExplorerView.vue` (no longer consumed there).

**Stays (intentional):**

- Backend `/api/v1/recordings/{id}/*` endpoints — the Chrome Extension at `extension/src/roboscope-client.js` still posts there. CLAUDE.md calls this the arm's-length boundary, HTTP only.
- `recorder.store.ts` + `useWebSocket.ts` `recording_status_changed` / `recording_event` cases — these drive status toasts for Chrome-Extension-originated recordings (admin sees "Recording completed"). Those toasts are the remaining human-visible integration with the v1 pipeline and stay.
- v1 i18n keys (`recorder.record`, `recorder.completed`, `recorder.failed`, etc.) — still referenced by `useWebSocket.ts` toasts.

## Acceptance Criteria

1. **Given** a user (any role) opens `/explorer/:repoId`, **when** the toolbar renders, **then** only the v2 `⏺ Recorder v2` button is present for editor+ (no duplicate v1 `⏺ Record` button).
2. **Given** `ExplorerView.vue` finishes mounting, **then** no `RecorderPanel` component is rendered anywhere in the tree.
3. **Given** the repository is freshly cloned and built, **when** `vue-tsc --noEmit` runs, **then** it reports **the same** error count as before this story (no new TS errors from dangling imports or unused symbols).
4. **Given** a Chrome Extension still pushes events to the backend, **when** the resulting recording transitions to `completed`, **then** the existing toast (`recorder.completed`) still fires — the v1 backend + WebSocket path is untouched.
5. The deleted `RecorderPanel.vue` file must no longer be referenced anywhere in the codebase.
6. **Docs:** the in-app documentation (EN/DE/FR/ES) recorder-overview already mentions "Recorder v2 recommended, legacy in-app, Chrome Extension". Update the "legacy" entry to clarify that the in-app v1 Explorer button has been **removed** in this release and that Chrome Extension users continue to work unchanged.

## Non-goals

- No backend removal.
- No Chrome Extension changes.
- No store removal — `recorder.store.ts` stays for the WebSocket toast path.
- No i18n key pruning (low-value; the keys are still used).
