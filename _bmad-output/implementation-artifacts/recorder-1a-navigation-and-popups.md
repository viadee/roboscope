# Story RECORDER-1A: Recorder misses page navigation + popup windows

Status: done

Epic: RECORDER — Recorder v2 robustness
Story Key: `recorder-1a-navigation-and-popups`

## Reported

> Der Recorder bekommt nicht mit, wenn ein neues Browser-Fenster geöffnet wird oder die Seite gewechselt wird.

## Root cause — two compounding bugs

**(1) Capture script swallows the post-navigation `load` emission.**
`backend/src/recording/capture_script.py` opens with:

    let lastNavUrl = location.href;

`add_init_script` runs the capture script on **every** new document, so when the user navigates (link click, address-bar URL, full reload, popup), the script re-initializes inside the new document with `lastNavUrl` already set to the new URL. The `setTimeout(() => maybeEmitNav("load"))` callback then sees `now === lastNavUrl` and skips the emission. Net effect: no `Go To <url>` command is queued for the navigation.

**(2) Popup / new-tab pages emit no `Switch Page` marker.**
Context-level `add_init_script` + `expose_binding` correctly carry over to popup pages, so clicks inside a popup ARE captured — but they land in the same flat command list with no separator. The recorded `.robot` file replays as if the user clicked on selectors that never existed in the original tab.

## Fix

**Patch 1 — `capture_script.py`:** initialise `lastNavUrl = ""` so the first `maybeEmitNav("load")` always wins. The pushState / replaceState / popstate handlers continue to compare against the live `lastNavUrl` after the load emission.

**Patch 2 — `v2_payload_translator.py`:** new payload `{kind: "switch_page", url}` translates to a `Switch Page` keyword with `args = {page: "NEW", url: ...}` (URL omitted for `about:*` placeholders).

**Patch 3 — `v2_recorder_task.py`:** register `context.on("page", _on_new_page)` to fire `on_capture(None, {kind: "switch_page", url: page.url})` whenever the context acquires a new page. The very first page (created explicitly by `context.new_page()`) is skipped via a `seen_first_page` latch — we don't want a `Switch Page    NEW` immediately after the initial `Go To`.

The translator emits `Switch Page    NEW` (RF Browser's idiom for "focus the most recently opened page"). Replay correctness: the next captured commands run against the now-active popup, which matches what the user did.

## Acceptance Criteria

- [x] Full-page navigation emits a `Go To <url>` command in the recorded sidecar.
- [x] Popup / `target=_blank` opens emit a `Switch Page    NEW` command before the popup's own captured events.
- [x] First-page bootstrap does not emit a spurious `Switch Page`.
- [x] `about:blank` URLs are filtered from the Switch Page args.
- [x] All 323 backend recording tests still pass; 3 new translator cases for the `switch_page` payload.

## Out of scope (V1)

- Detecting tab focus switches between EXISTING pages. Playwright doesn't fire a tab-focus event we can hook reliably; replay correctness for "user switches back to original tab" is left for a follow-up.
- Detecting page CLOSE events (closing a popup) — the `Switch Page` model treats sequence-of-opens as the source of truth, which works for the common popup → action → switch-back-implicit pattern.
- Window-management keywords beyond `Switch Page    NEW` (e.g. `Switch Page    PREVIOUS`, `Close Page`).
