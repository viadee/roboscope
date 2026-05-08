"""Story DEBUG-1 — interactive Robot Framework debugger driver.

Architecture
------------

When a user clicks "Run up to here" in the FlowEditor, or "Re-run
to terminating error" in the run-detail panel, RoboScope:

1. Resolves the project's Python environment (existing
   `environments` service).
2. Spawns ``<env>/bin/robotcode debug-launch --tcp 127.0.0.1:0 -w
   -- <robot_file>`` as a subprocess. ``-w`` makes the launcher
   wait for our DAP client before starting the run; the ephemeral
   port is parsed from stdout.
3. Connects a TCP DAP client to that port (`dap_client.DapClient`).
4. Sends the standard DAP handshake — ``initialize`` →
   ``setBreakpoints`` (one entry for the user-selected line) →
   ``configurationDone`` → ``launch`` — and starts pumping events.
5. On every ``stopped`` event, queries ``stackTrace`` / ``scopes``
   / ``variables`` and forwards a snapshot to the frontend over
   the existing WebSocket. Frontend toolbar buttons map back to
   ``continue`` / ``next`` / ``stepIn`` / ``disconnect``.

This module wraps the wire format + the lifecycle (spawn / handshake
/ tear-down) so callers get a clean async API
(:class:`robot_debug_session.RobotDebugSession`). The actual REST /
WebSocket plumbing lives in ``debug/router.py`` (Story DEBUG-2).

Why DAP and not a hand-rolled listener
--------------------------------------
RobotCode (https://github.com/robotcodedev/robotcode, Apache-2.0,
last release 2026-04) ships a production-grade DAP server for
Robot Framework that we'd otherwise have to re-implement. Speaking
the standard Microsoft DAP wire protocol means we get a lot for
free — breakpoint resolution, scope/variable hierarchies, evaluate
expressions, abort semantics — and we can reuse the same client
for any other DAP-capable target later (vendored test runners,
remote-agent K8s execution, etc.).

The fallback (a custom Listener V3 built on
``threading.Event``-gated pause + ``BuiltIn().get_variables()``)
stays in our pocket if a RobotCode pin ever bites us; see the
research note in CLAUDE.md ``release-publish`` checklist.
"""

from src.debug.dap_protocol import (  # noqa: F401 — re-export
    DapMessage,
    DapProtocolError,
    read_message,
    write_message,
)
