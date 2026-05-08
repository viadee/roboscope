# Story (quick): Recorder v2 end-to-end capture test

Status: done

Epic: Recorder v2 Web MVP
Story key: `recorder-v2-e2e-capture-fixture`

## Story

As a Recorder maintainer,
I want an integration test that launches the real v2 Playwright recorder against a local HTML fixture and asserts on the captured `RecordedCommand` payloads,
so that a regression in the capture-script wiring, the `__roboscopeCapture` binding, or the selector synthesis cannot land without a red test.

**Why now.** The consolidated retrospective (`retrospective-phase-4-and-recorder-v2.md` → "What went badly") called out exactly this gap: W.1 full committed the Playwright task + the three injected scripts but only unit-tested the pure parts. A real "launch, click, assert commands" pass was deferred with the note "belongs in phase4-gates.yml" — this story closes that.

## Acceptance Criteria

1. **AC1 — Fixture page.** A static HTML document lives under `backend/tests/fixtures/recorder_fixture.html`. It contains at minimum: a heading with a `data-testid`, one button with a `data-testid`, one text input with a `data-testid`, one link that navigates to `#/next`. No external resources (offline-only invariant from CLAUDE.md).

2. **AC2 — Test hook on the recorder task.** `run_v2_recorder_session(session_id, *, target_url, headless=False, test_actions=None)` accepts:
   - `headless` bool that passes through to `pw.chromium.launch()`.
   - `test_actions` optional async callable `(page) -> None` that runs scripted user actions between browser launch and stop. When provided, the task calls it once after the initial navigation, then sets `stop_event` so the loop exits cleanly.

3. **AC3 — End-to-end pytest.** `backend/tests/recording/test_v2_recorder_e2e.py` contains `test_recorder_captures_click_type_navigate`:
   - Marked `@pytest.mark.integration` so the default suite can still skip it on Windows CI until Playwright Chromium is installed.
   - Starts a local `http.server` serving the fixture page on an ephemeral port.
   - Registers the session in the v2 command queue, spawns `run_v2_recorder_session` in a thread with `headless=True`, `target_url=<fixture URL>`, and a `test_actions` that clicks the button, types into the input, then follows the link.
   - Drains the v2 command queue after the loop exits.
   - Asserts: ≥ 1 `Click` command with a `testid` selector candidate on the expected button; ≥ 1 `Type Text` command whose `args["text"]` matches what the action typed; a `navigate` or `Go To` command resulting from the in-page link (acceptable if the emitted kind is `navigate` via the pushState proxy or a full nav → `Go To`).

4. **AC4 — Clean shutdown.** The test finishes within 15 seconds. The recorder thread is joined; the session row (if the test writes one) is cleaned; the queue is torn down; no orphan Chromium process is left running.

5. **AC5 — Playwright-available guard.** If `playwright` or its Chromium binary is missing from the dev environment, the test skips with a clear reason (`pytest.skip("playwright chromium not installed")`). CI matrix enables it after `playwright install chromium`.

## Tasks

### Task 1 — fixture page
- [x] NEW `backend/tests/fixtures/recorder_fixture.html` — offline, self-contained, contains the AC1 elements plus one secondary `#next` section.

### Task 2 — test hook on the task
- [x] MOD `backend/src/recording/v2_recorder_task.py`:
  - Add `headless: bool = False` and `test_actions: Callable | None = None` params to `run_v2_recorder_session` and plumb them into `_recorder_loop`.
  - After `page.goto(target_url)`, if `test_actions` is non-None, `await test_actions(page)`, then set `stop_event` so the usual teardown fires.

### Task 3 — the test
- [x] NEW `backend/tests/recording/test_v2_recorder_e2e.py` — see AC3.
- [x] Use `http.server.ThreadingHTTPServer` bound to `127.0.0.1:0` to serve the fixture page during the test.
- [x] Register the session with the v2 command queue before spawning the task; drain via `iterate_commands` inside an asyncio-bridged collector, or — simpler — poll the queue's pending list after stop.

## Dev notes

- The `test_actions` callable runs on the Playwright event loop. It may call `page.click`, `page.fill`, `page.click` on a link etc. — regular Playwright APIs. It must not import into the capture script; it simulates a user.
- Do not mock the Playwright binding. The whole point of this story is that a real browser exercises a real `__roboscopeCapture` call path.
- Fixture page has zero JS / zero network — the overlay + capture + context-menu scripts injected by the recorder are the only JS that runs.

## Tests

See AC3 + AC4.

## Non-goals

- Cross-browser coverage (Chromium only — matches the PRD non-goal).
- Desktop Windows UIA coverage (separate story, needs Windows host).
- The context-menu right-click keyword path — only the primitives-capture path is exercised; a second integration test can cover the custom-action menu once the first lands green.

## Done when

- `make test-backend` picks up `test_v2_recorder_e2e.py`. Marker `integration` lets CI pipelines opt-in / opt-out per environment (Chromium availability).
- Locally the test takes < 10 s on green path.
- Regression signal — if someone removes a line from `capture_script.py` or breaks the `__roboscopeCapture` binding, the test goes red.
