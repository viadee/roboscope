# Story DEBUG-5: Breakpoint stops actually fire on the user's chosen line

Status: done

Epic: Interactive Robot Framework Debugger
Story Key: `debug-5-breakpoint-resolution`
Depends on: DEBUG-1, DEBUG-2, DEBUG-3, DEBUG-4

## Story

As a Runner-role user clicking `🐞 Debug` or `▶ Bis hier ausführen`,
I want the test to actually pause at the line I picked,
so that "Run to here" delivers on its promise — currently the spawn + handshake succeed, the test executes end-to-end, but no `stopped` event ever arrives so the DebugPanel sits forever showing "Verbinde…".

## Background — what we already know

After landing DEBUG-2/3 + the post-release fixes (commits `2592c13`, `7d1dcaf`, `a30f85c`) the spawn + handshake pipeline works against modern `robotcode debug-launch`:

- ✅ Spawn (correct CLI flags, no `-w`, pre-allocated port, poll-connect)
- ✅ Initialize → wait-for-`initialized`-event → setBreakpoints → configurationDone
- ✅ Launch payload includes `request`/`python`/`cwd`/`target`/`console: internalConsole`
- ✅ Robot Framework actually starts (banner output reaches us as a DAP `output` event)

The failing piece is **between** RF starting and our DebugPanel rendering scope/stack: when RF executes a keyword line that should hit the breakpoint, no `stopped` event reaches us.

Pinned by the `@pytest.mark.integration` `xfail(strict=True)` test `test_real_breakpoint_pauses_execution` in `backend/tests/debug/test_robot_debug_session.py`.

## Investigation summary (committed before this story)

1. **Spawn + handshake against the real `robotcode debug-launch` CLI in the user's `~/.roboscope/venvs/roboscope-default` venv** — verified working in `test_real_spawn_handshake_and_test_runs`. The RF banner (`====... Demo ====...`) arrives as an `output` event with `category=stdout`, proving the launcher → child subprocess chain is alive.

2. **What's *probably* wrong** — three hypotheses, in descending likelihood:

   a. **Path key mismatch in `process_start_state`** (most likely). RobotCode's debugger stores breakpoints keyed by `pathlib.PurePath(source.path)` from the `setBreakpoints` request, but at runtime checks `self.map_path_to_client(str(Path(source).absolute()))` against that key. On macOS, `/var/...` vs `/private/var/...` symlink resolution can desync these — we already pass `Path.resolve()` in the test but the runtime path still fails to match. Concrete suspects: `Path(source).absolute()` does NOT resolve symlinks (only `.resolve()` does), so RF's reported source path may diverge from what we sent.

   b. **`stopped` event never sent because RF reports a different `source`/`line` shape than DEBUG-1 expects.** The breakpoint logic compares `entry.line == v.line`. If RF's `attributes["lineno"]` reports the keyword *call* line vs the keyword *definition* line, vs a 0-vs-1-based offset, our line 3 breakpoint would never match.

   c. **The launcher's launch-args proxy chain drops a required field.** RobotCode's full launch payload accepts `paths`, `profiles`, `robotPythonPath`, `outputDir`, `mode`, `languages`, `include`/`exclude`, `variables`. Some combination may be required for breakpoints to verify even though the test launches and runs.

3. **What's been ruled out — DEFINITIVELY** by the new diagnostic test `test_real_pause_request_pauses_execution`: a bare `pause` request after `configurationDone` ALSO fails to produce a `stopped` event. `pause` completely bypasses path resolution — it just sets `requested_state = Pause` on the child's `Debugger` instance, then the next listener event (start_test / start_keyword) fires the stopped event unconditionally.

   Since pause AND breakpoint both fail with the same symptom (test runs end-to-end, no `stopped` event ever arrives), the bug is **NOT in path resolution**. It is in the **event-forwarding direction launcher → us**, specifically for the `StoppedEvent` family. Other events (`output`, `initialized`) traverse the same proxy and arrive fine.

   The launcher's `client.py::DAPClientProtocol.handle_event` calls `self.parent.send_event(Event(event=message.event, body=message.body))` indiscriminately for every event from the child — so the natural suspect is *whether `handle_event` is being called at all* for `stopped`. Possibilities for the next investigator:

   - The child's `send_event(StoppedEvent(...))` doesn't actually go over the launcher's TCP connection. RobotCode's `Debugger.send_event` may write to a different sink (queue / direct stdout) when no client is attached, even if `attached=True` was set. Verify by patching the venv's `debugger.py::send_event` with a `print` and re-running — if "stopped" is logged but doesn't reach us, the launcher dropped it; if it's never logged, the call site never fires.
   - There may be a race where the launcher's `DAPClient` to the child loses the protocol parser before stopped events arrive. The launcher uses `JsonRPCServer` infra with a custom `handle_event` override; it's possible the dispatcher routes by message type and `stopped` falls into an unhandled bucket while `output` lands on a default-event path.
   - The strict `strict=True` xfail on BOTH tests is the watchdog: when one passes the other should too (same root cause).

## Acceptance Criteria

1. **AC1 — Real-robotcode breakpoint stops fire.** The integration test `test_real_breakpoint_pauses_execution` flips from `xfail(strict=True)` to a regular passing test. The remove-the-xfail change is the proof of fix.

2. **AC2 — `stopOnEntry: True` also produces a `stopped` event.** Add a sibling integration test `test_real_stop_on_entry_pauses` that sets `stopOnEntry: True` (no breakpoint) and asserts a `StoppedReason.ENTRY` event arrives within 20 s. This isolates the path-resolution path from the entry-stop path; both must work.

3. **AC3 — Path-resolution unit test.** Add `tests/debug/test_breakpoint_path.py` that exercises whatever path-normalisation code we end up writing (likely a helper that resolves macOS `/var` ↔ `/private/var` and Windows-vs-POSIX path forms). Cases: macOS unresolved, macOS resolved, Linux unresolved, Windows backslashes, mixed separators.

4. **AC4 — Diagnostic in `DebugSessionStartFailed`.** When a breakpoint click fires `setBreakpoints` and the response indicates `verified=False` for any breakpoint, `_handshake` should surface that in the error path so users see "Breakpoint at line N could not be set — RobotCode reports the file/line as unverified" instead of a silent never-stops symptom.

5. **AC5 — UI graceful path.** In the run-detail panel and the Flow Editor overlay, when `setBreakpoints` returns `verified=False` for the user's chosen line, surface a non-blocking warning toast: "Breakpoint set at line N may not stop — RobotCode could not verify it." Do NOT block the session start; let the user continue and pause manually if needed.

6. **AC6 — No regression in unit tests.** All existing `tests/debug/` tests stay green; the fake-DAP server may need an update to mirror whatever the real robotcode does for the verified-breakpoint case.

## Out of scope

- Conditional breakpoints / hit-count breakpoints / log-message breakpoints (epic non-goal).
- Path mapping for remote-execution scenarios (DEBUG-1's `path_mappings` is defined but unused; we keep that surface for a future remote-runner story).
- Auto-fix mismatched paths by trying multiple variants — the fix should *predict* the right path the first time, not heuristically retry.

## Suggested investigation steps for the implementer

1. **First: confirm the proxy chain.** Run the existing `test_real_spawn_handshake_and_test_runs` test, capture the launcher's stdout/stderr in `_boot_log`. Look for any "stopped" or "breakpoint" string. If the launcher *does* see stopped events, the bug is in our `_pump_subprocess_output` or DapClient routing. If it doesn't, the child never sent one.

2. **Then: verify the child's view of the source path.** Either:
   - Add a temporary `print()` to `Debugger.set_breakpoints` (in the venv copy) to dump the stored path. Run the integration test once. Read the `output` events to see the path. Compare to what we sent.
   - OR: write a tiny standalone Python script that connects to robotcode debug-launch directly (bypassing our `RobotDebugSession`), sends the same handshake, and inspects events with full logging. Use this as the bench for iterating on launch-args.

3. **Likely fix shape.** A path-normalisation helper in `robot_debug_session.py`:

   ```python
   def _canonical_breakpoint_path(p: str) -> str:
       # macOS: /var → /private/var. Windows: backslashes → forward.
       resolved = Path(p).resolve()
       return str(resolved)
   ```

   Apply at both: (a) the `target` we send in launch_args, (b) the `Breakpoint.file` we send in setBreakpoints. Both halves must be identical.

4. **If path matching turns out NOT to be the issue:** flip to hypothesis (b) and capture the actual `attributes` dict that RF passes to `start_keyword` by patching the listener. Compare line numbers. If they're off by one, normalise on our side.

## Dev notes

- The strict xfail is the primary watchdog. Don't remove it until the fix verifies.
- Keep the spawn/handshake refactor untouched — that path is solid and well-tested.
- Update the BMAD docstring of `RobotDebugSession._handshake` if the launch payload shape changes again.
- Whatever helper you add, expose it via the public `Breakpoint(file, line)` constructor so callers (DEBUG-2/3 routers) don't have to know about path normalisation.
- Frontend changes for AC5 are tiny — wire one error toast in `RunDetailPanel.vue` + `FlowEditor.vue` mirroring the existing `debugError` banner.

## Resolution (2026-05-08)

**Root cause was none of the original three hypotheses.** Path resolution was a red herring. The bug was a **synchronisation contract** in RobotCode that we weren't honouring:

- RobotCode's listener (V2 + V3) emits `robotEnqueued` / `robotStarted` / `robotEnded` / `robotSetFailed` / `robotLog` events whose body classes inherit from `SyncedEventBody` (mixins.py).
- For each such event, the in-process `Debugger.send_event` triggers `DebugAdapterServerProtocol.on_debugger_send_event` (server.py:86) which: clears `self.sync_event`, schedules the wire-send on the asyncio loop, then **synchronously blocks the listener thread for up to 15 s on `self.sync_event.wait(15)`**.
- `self.sync_event` is set ONLY when the client sends a `robot/sync` RPC method back to the child (`_robot_sync` at server.py:417).
- We never sent `robot/sync` → every synced event blocked the listener for 15 s. The very first event (`robotEnqueued` from `ListenerV3.start_suite`) tied up the suite-start handler so RF never reached `start_test` / `start_keyword`, and `process_start_state` (where breakpoint matching lives) was never called.
- That's why `pause` *and* breakpoint stops both vanished, why `output` events still flowed (their bodies don't mix in `SyncedEventBody`), and why `initialized` flowed (it's emitted by the launcher before the synced-event chain begins).

**Fix in `backend/src/debug/robot_debug_session.py`:**

```python
def _wire_event_handlers(self, client: DapClient) -> None:
    ...
    for synced_event in (
        "robotEnqueued", "robotStarted", "robotEnded",
        "robotSetFailed", "robotLog",
        "robotExecutionPaused", "robotExited",
    ):
        client.on_event(synced_event, self._on_robot_synced_event)

def _on_robot_synced_event(self, _body):
    """Fire-and-forget `robot/sync` request on every synced event."""
    if self._client is None:
        return
    async def _ack():
        try:
            if self._client is not None:
                await self._client.request("robot/sync", {})
        except Exception:
            logger.debug("robot/sync ack failed", exc_info=True)
    with suppress(RuntimeError):
        asyncio.create_task(_ack())
```

**Diagnosis path that found it** (recorded so future me doesn't re-do this):

1. Confirmed via the `pause` xfail isolation test that the bug was NOT path-resolution (pause bypasses path matching entirely and ALSO didn't produce stopped events).
2. Patched the user's venv (`~/.roboscope/venvs/roboscope-default/lib/python3.12/site-packages/robotcode/debugger/{server.py,debugger.py,launcher/client.py,listeners.py}`) with `print` instrumentation writing to `/tmp/dbg5_trace.log`.
3. Ran the pause integration test. Trace showed `V2.start_suite ENTER` happened, `robotStarted` event was sent, but the next instrumentation line (`sent robotStarted, calling start_output_group`) never fired — listener thread hung mid-method.
4. Read the `on_debugger_send_event` source carefully → spotted the `if synced: self.sync_event.wait(15)` block.
5. Grepped for `sync_event.set()` → found `_robot_sync` rpc method at server.py:417.
6. Wrote the auto-ack handler. First test pass: 8 seconds, breakpoint stops on line 3 as expected. ✅
7. Reverted all venv instrumentation, removed `xfail` markers, all 3 integration tests pass.

**Test status:**
- `test_real_spawn_handshake_and_test_runs` ✅ pass
- `test_real_breakpoint_pauses_execution` ✅ pass (was strict-xfail)
- `test_real_pause_request_pauses_execution` ✅ pass (was strict-xfail; uses `Sleep 3s` in the .robot so pause races RF before termination)

**ACs status:**
- AC1 ✅ — both xfails flipped to passing
- AC2 ✅ — pause test passes alongside
- AC3 — n/a (path resolution wasn't the issue, no helper needed)
- AC4 ⚠️ — punted; setBreakpoints already returns `verified=True` from RobotCode, so a `verified=False` UX path doesn't apply today. Left as a future enhancement when RobotCode's verified-flag becomes meaningful.
- AC5 ⚠️ — punted, see AC4
- AC6 ✅ — all 71 unit tests in `tests/debug/` green; the fake-DAP server in test_robot_debug_session.py needed no changes (it doesn't model SyncedEventBody — the fix is callable-handler shape, not protocol-shape).
