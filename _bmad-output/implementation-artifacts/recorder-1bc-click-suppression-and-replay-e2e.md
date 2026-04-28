# Stories RECORDER-1B + RECORDER-1C: click-caused Go To suppression + multi-page replay e2e

Status: done

Epic: RECORDER — Recorder v2 robustness
Story Keys: `recorder-1b-suppress-click-caused-goto`, `recorder-1c-multipage-replay-e2e`

## Reported

> Wenn ich zum Beispiel über einen Button die URL wechsle, dann darf ich nicht nochmal ein Kommando aufnehmen. Du solltest also einen e2e Test schreiben, der einerseits den Recorder und darüber eine Seite öffnet (vll. ein lokales Fixture?), darin mindestens auf eine weitere Seite wechselt und dann dort Elemente anklickt. Dann solltest du das Recording ausführen und schauen, ob der Test erfolgreich durchläuft.

Two issues bundled into one work-item because the e2e test is what surfaces them.

## RECORDER-1B — suppress redundant Go To after a click that navigates

A click that triggers navigation (link, button → window.location.assign, form submit) was previously recorded as `Click selector` AND `Go To <new-url>`. On replay the Click already navigates; the explicit Go To then re-navigates, wiping any state the click set.

**Fix in `capture_script.py`:**

- Every click handler stamps `sessionStorage[CLICK_NAV_KEY] = Date.now()` (sessionStorage survives same-origin navigations within a tab).
- `maybeEmitNav("load")` checks the stamp; if a click happened within the last 1500 ms, the load emission is suppressed and the stamp consumed.
- pushState / replaceState / popstate are unaffected — those are programmatic SPA nav with no preceding click event we can attribute them to.

## RECORDER-1B follow-up — capture the initial Go To reliably

While building the e2e test we discovered the initial-load Go To often went missing too: `setTimeout(maybeEmitNav, 100ms)` could be cancelled by a fast user click that triggered the next navigation before 100 ms elapsed (Playwright auto-wait is fast). Solution:

- Emit synchronously at script init (the script runs at `document_start` with `location.href` already set to the post-navigation URL).
- Skip placeholder URLs (`about:blank`, `about:srcdoc`, `chrome:`, `data:`) — the about:blank a context's first page boots into would otherwise become a useless "first command" in every recording.
- Keep the 100 ms `setTimeout` as a safety net for races where `location.href` settles after document-start.

## RECORDER-1C — round-trip + replay e2e test

Two new fixtures (`recorder_multipage_a.html`, `recorder_multipage_b.html`) — Page A has a real-href link to Page B, Page B has a click-target button with a marker that toggles on click.

`backend/tests/recording/test_v2_recorder_multipage_e2e.py` adds two `@integration` cases:

1. **`test_recorder_multipage_round_trip`** — drives the recorder through the page-A → click-link → page-B → click-button journey via the existing `test_actions` hook. Asserts:
   - the link click is captured;
   - the page-B button click is captured (proves cross-page capture survives full navigation);
   - **no** `Go To <page-b-url>` follows the link click (RECORDER-1B suppression).

2. **`test_recorded_robot_replays_successfully`** — same recorded flow, but it then renders the `RecordedFlow` to `.robot` via `emit_robot()` and runs `robot` from a venv that has `robotframework-browser` installed (`~/.roboscope/venvs/roboscope-default` by default; overridable with `ROBOSCOPE_REPLAY_VENV`). Asserts exit-code 0. Skips cleanly when the venv isn't usable or rfbrowser's browsers aren't `init`-ed.

## `emit_robot` — generate replayable Browser-library bootstrap

A pure recorder side that emits only `Click`, `Type Text`, `Go To` lines isn't replayable through `robotframework-browser` — the library needs `New Browser` + `New Context` + `New Page` to set up. Updated `robot_emit.py`:

- For web flows, prepend the bootstrap and consume the first `Go To`'s URL as the `New Page` argument.
- Drop that first Go To from the emitted output (the New Page already navigated).
- Subsequent Go Tos (e.g. user typed a URL into the address bar mid-session) are preserved verbatim.

Two existing tests (`test_go_to_does_not_need_selector`, `test_full_login_flow_round_trip`, `test_saves_file_and_audits`) were tightened to assert the new shape.

## Verification

- `pytest tests/recording/` → 325 / 325 (incl. the 2 new e2e cases).
- `test_recorded_robot_replays_successfully` actually runs `robot` against the recorded `.robot` and confirms exit-code 0 with the rfbrowser venv on this machine.

## Out of scope (V1)

- Click-caused navigations that take longer than 1.5 s (slow app servers). The window can be raised but anything > 5 s starts swallowing legitimate user-typed-URL navigations.
- Form submits without a click (Enter in a text field while focus is in the form). The `submit` event isn't currently capture-script-monitored; the resulting Go To would NOT be suppressed. Acceptable for now — the test would still replay because Press Keys (Enter) is recorded separately.
- Recording navigation that occurs via JavaScript without any user input (timers, polling redirects). Out of scope — those should arguably be recorded as Go Tos, since no user gesture caused them.
