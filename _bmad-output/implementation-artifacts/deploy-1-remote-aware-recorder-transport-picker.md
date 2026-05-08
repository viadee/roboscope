# Story DEPLOY-1 — remote-aware recorder transport picker

**Type:** BMAD quick story (UX + ops honesty)
**Date:** 2026-04-23

## Background

Both legacy v1 and v2 Web Recorder launch Chromium *on the backend*
(`v2_recorder_task.py:135` → `pw.chromium.launch(headless=False)`).
When RoboScope is deployed on a remote server (typical for team
deployments), the user's browser sees the SSE command stream but the
actual Chromium window is on the server — either it fails to boot on
a headless VM, or it opens on a desktop the user cannot see.

The Launcher view today does not tell the user this. It shows three
radio buttons (Web / Desktop Windows / Desktop macOS) with the
desktop options hardcoded to disabled. A non-obvious trap for anyone
whose backend is not on the same machine.

The escape hatch already exists — the Chrome Extension posts to the
same `/api/v1/recordings/*` endpoints from the user's own browser.
We just have to say so.

## Acceptance Criteria

1. **Given** the backend is headless (Linux without `$DISPLAY` or `$WAYLAND_DISPLAY` and no explicit override), **when** the user opens `/recordings/new`, **then** the "Web (Playwright)" radio is **disabled** and a yellow info box explains that recording needs a viewable browser on the server plus a one-line pointer to the Chrome Extension as the remote-friendly alternative.
2. **Given** the backend has a display OR the admin sets `ROBOSCOPE_HEADED_BROWSER=true`, **when** the user opens `/recordings/new`, **then** the "Web (Playwright)" radio is enabled and functions exactly as today.
3. **Given** the backend is on macOS or Windows (local-dev case), **when** the capability endpoint is queried, **then** `web_playwright_viable` is `true` by default unless the admin explicitly sets `ROBOSCOPE_HEADED_BROWSER=false`.
4. **Given** the capability endpoint is called on any platform, **then** `desktop_windows_viable` is `true` only when `sys.platform.startswith("win")` and `desktop_macos_viable` is always `false` (DM.1 NO-GO lock). This replaces the hardcoded `disabled: true` in the launcher's transport array.
5. **Given** the capability endpoint is unreachable (e.g. bad network), **when** the launcher mounts, **then** it falls back to "everything enabled" rather than locking the user out — the 501 guards on the start-browser endpoint still catch real misconfiguration.
6. The new endpoint `GET /api/v1/recordings/capabilities` is authenticated (same as the existing session endpoints) and cheap — no filesystem / subprocess probes.
7. **Tests:** three backend pytest cases — headless Linux returns `web_playwright_viable=false`, Linux with `DISPLAY` set returns `true`, explicit `ROBOSCOPE_HEADED_BROWSER=false` override beats heuristic.
8. **i18n:** new keys in EN/DE/FR/ES for the info box + extension pointer.
9. **CLAUDE.md:** add a "Critical patterns" note so future Recorder work does not reintroduce the silent-window trap (e.g. a future dev spinning up a pooled browser service should still respect the capability flag).

## Out of scope

- Auto-detecting headless-server SKUs on Windows / macOS (no cheap heuristic; the env-var override covers the real cases).
- Deep-linking into the extension install page (the extension is distributed via offline ZIP, not a chrome-web-store URL).
- Exposing a richer "deployment info" surface (host name, build, uptime). Separate ops story.
- Changing the Chrome-Extension UX itself. The extension-side work is deferred unless this story surfaces a connection failure that needs the extension to show a more specific hint.
