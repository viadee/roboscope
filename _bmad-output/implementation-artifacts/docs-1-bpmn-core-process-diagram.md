# Story DOCS-1 — BPMN diagram of RoboScope's core process

**Type:** BMAD quick story (documentation asset)
**Date:** 2026-04-23

## Motivation

New users ask "where do I start?" and maintainers revisit the Phase-4 retrospective asking "what's the happy path end-to-end?". Prose in the in-app docs tells the story but doesn't show it. A single BPMN 2.0 diagram of the core lifecycle — repo → (write / record) → execute → report — answers both questions at a glance.

## Technology

- **BPMN 2.0** XML for the diagram itself — portable, editable in any BPMN tool (Camunda Modeler, Signavio, bpmn.io's own sketchy.io).
- **bpmn-js** (from `bpmn.io`, MIT license) as the in-browser viewer. Read-only `NavigatedViewer` class, not the full modeler — so we get pan + zoom but no editing surface, which matches the "show, don't tell" intent of this view.
- Dynamic import so the ~900 KB bpmn-js bundle does **not** hit the critical path (CLAUDE.md Known-Issues already flags the 270 KB docs bundle; this stays off that hot path by lazy-loading on `/docs/process` only).
- Offline-first: all assets live under `node_modules/bpmn-js` + the hand-authored `.bpmn` XML shipped as a static asset under `public/`. No CDN fetch at runtime.

## Acceptance Criteria

1. **Given** a user navigates to `/docs/process`, **when** the route mounts, **then** a BPMN 2.0 diagram of the RoboScope core process renders inside the viewport, pan + zoom works, and fit-to-viewport fires automatically on load.
2. **Given** the BPMN XML is fetched, **when** anything in it is malformed (corrupt asset, missing DI), **then** the view shows a localised error banner instead of a blank canvas.
3. The process shown depicts the canonical happy path: **Select Repository → Author or Record Test → Trigger Run → (Docker Image Fresh?) → [if no] Build Image → Execute Tests → Parse Report → (Passed?) → [if failed] AI Analysis → End**.
4. The `.bpmn` file ships as a static asset so a maintainer can open it in Camunda Modeler, edit visually, and drop the result back into the repo without touching Vue.
5. The route is linked from the existing Docs view (a "View the process diagram" entry) and from the sidebar Docs section secondary link — no new top-level sidebar entry (keeps the sidebar short).
6. A one-line credits footer names "Powered by bpmn-js (bpmn.io)" with the canonical link (rendered as plain text, not an outbound link, to preserve the offline guarantee).
7. i18n keys ship in EN/DE/FR/ES.

## Non-goals

- No editing / modeler mode. Users cannot change the diagram in the browser.
- No BPMN engine / execution semantics — purely decorative.
- No clickable hotspots jumping into each task's in-app docs page (worthwhile follow-up; skipped to keep this story quick).
- No custom legend component — we rely on BPMN's own standard shapes being self-explanatory.
