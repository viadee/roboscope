"""High-level lifecycle for a single Robot Framework debug session.

Wraps subprocess + TCP + DAP handshake + cached state behind an
async context manager. Callers create one, await the handshake by
entering the context, then drive `continue_/next_/step_in/...`.
The exit path always reaches `disconnect`, waits a grace period
for the subprocess to exit cleanly, then escalates to ``kill()``
+ zombie-reap so we don't leak Chromium / rfbrowser-init Node
processes when the user closes their browser tab.

Architecture decisions
----------------------

* **Process per session.** Each session spawns its own
  ``robotcode debug-launch --tcp 127.0.0.1:0 -w`` subprocess.
  ``-w`` makes the launcher block on a TCP client connecting
  before it starts the run, which gives us a safe window to send
  ``setBreakpoints`` before any keyword runs.
* **Ephemeral port.** Port 0 → kernel-assigned, parsed back from
  stdout. Avoids the "two debug sessions race for port 6612"
  failure mode the RobotCode docs warn about.
* **State cache lives on the session.** Every ``stopped`` event
  triggers a refresh of stack-frame / scopes / variables; the
  resulting dict is the source of truth for the WebSocket-pushed
  ``state`` payload (see Story DEBUG-2 router).

Tests for this module mock the subprocess + TCP server entirely;
no real ``robotcode`` invocation. See ``test_robot_debug_session.py``
for the contract.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.debug.dap_client import DapApplicationError, DapClient
from src.debug.dap_protocol import DapProtocolError

logger = logging.getLogger("roboscope.debug.session")


class DebugSessionStartFailed(RuntimeError):  # noqa: N818  # public API name
    """Raised when any step in the spawn → handshake pipeline fails.

    Wraps the original cause; the route layer (DEBUG-2) should
    surface this as a 502 with the operator-readable detail
    string. Failing-step granularity is encoded in the message."""


@dataclass
class Breakpoint:
    """A single line-based breakpoint scoped to a `.robot` file."""

    file: str
    line: int


@dataclass
class DebugState:
    """Cached snapshot of the last-known debug state.

    Updated after every ``stopped`` event by the read pump's
    handler; consumed by the WebSocket-emit code (Story DEBUG-2)
    and by the REST `/state` endpoint."""

    paused: bool = False
    paused_at_file: str | None = None
    paused_at_line: int | None = None
    paused_reason: str | None = None
    stack_frames: list[dict[str, Any]] = field(default_factory=list)
    scopes: list[dict[str, Any]] = field(default_factory=list)
    output_lines: list[str] = field(default_factory=list)
    terminated: bool = False


# ---------------------------------------------------------------------------
# Port-line parser
# ---------------------------------------------------------------------------

# RobotCode's `debug-launch --tcp 127.0.0.1:0 -w` prints the bound
# address on stdout in a form like:
#   `Listening on 127.0.0.1:54321`
# The exact wording is documented at robotcode.io/03_reference/cli;
# we tolerate ipv4/ipv6 and arbitrary surrounding text so a future
# version drift on the message doesn't break us — extract the
# port from the first `:<digits>` after a quoted/lone host token.
_PORT_RE = re.compile(r"(?:127\.0\.0\.1|\blocalhost|\[::1\]):(\d{1,5})\b")


def _parse_port(line: str) -> int | None:
    """Return the port from a RobotCode startup line, or ``None``
    if the line doesn't carry a recognisable address."""
    m = _PORT_RE.search(line)
    if not m:
        return None
    port = int(m.group(1))
    if 1 <= port <= 65535:
        return port
    return None


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class RobotDebugSession:
    """Async context manager driving one robotcode debug subprocess.

    Typical use::

        async with RobotDebugSession(
            robot_path="tests/checkout.robot",
            test_name="Buy Item And Check Receipt",
            breakpoints=[Breakpoint("tests/checkout.robot", 42)],
            env_python_path="/.../env/bin/python",
        ) as session:
            event_q = session.events
            await event_q.get()        # wait for first `stopped`
            await session.continue_()
            ...

    The context's ``__aenter__`` spawns + handshakes; ``__aexit__``
    always reaches ``disconnect`` and reaps the subprocess.
    """

    def __init__(
        self,
        robot_path: str | Path,
        breakpoints: list[Breakpoint],
        env_python_path: str | Path,
        *,
        test_name: str | None = None,
        port_parse_timeout: float | None = None,
        spawn_args: list[str] | None = None,
    ) -> None:
        self.robot_path = str(robot_path)
        self.breakpoints = breakpoints
        self.env_python_path = str(env_python_path)
        self.test_name = test_name
        # Cold robotcode boots can take 20 s+ on slow venvs (Browser
        # library import + language-server bootstrap); 30 s is the
        # default. Operators can override via ROBOSCOPE_DEBUG_PORT_TIMEOUT.
        if port_parse_timeout is None:
            env_override = os.environ.get("ROBOSCOPE_DEBUG_PORT_TIMEOUT", "")
            try:
                port_parse_timeout = float(env_override) if env_override else 30.0
            except ValueError:
                port_parse_timeout = 30.0
        self._port_parse_timeout = port_parse_timeout
        self._extra_args = spawn_args or []

        self._proc: asyncio.subprocess.Process | None = None
        self._client: DapClient | None = None
        self.state = DebugState()
        # Boot-time stdout buffer — surfaced in the error message when
        # the port-announcement times out so the user can see what
        # robotcode actually printed (vs. a generic "did not announce").
        self._boot_log: list[str] = []
        # Bounded queue so a slow consumer (the WebSocket forwarder)
        # never lets the read pump backpressure us into OOM.
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)

    # -- public driving API ------------------------------------------------

    async def continue_(self) -> None:
        await self._control("continue", {"threadId": 1})

    async def next_(self) -> None:
        await self._control("next", {"threadId": 1})

    async def step_in(self) -> None:
        await self._control("stepIn", {"threadId": 1})

    async def step_out(self) -> None:
        await self._control("stepOut", {"threadId": 1})

    async def disconnect(self) -> None:
        """Send the DAP ``disconnect`` request. Idempotent."""
        if self._client is None:
            return
        with suppress(Exception):
            await self._client.request("disconnect", {"terminateDebuggee": True})

    async def _control(self, command: str, args: dict[str, Any]) -> None:
        if self._client is None:
            raise RuntimeError(
                "RobotDebugSession control called before handshake — "
                "use `async with RobotDebugSession(...)`."
            )
        await self._client.request(command, args)

    # -- context manager ---------------------------------------------------

    async def __aenter__(self) -> RobotDebugSession:
        try:
            await self._spawn()
            await self._handshake()
            return self
        except DebugSessionStartFailed:
            await self._cleanup_silently()
            raise
        except Exception as e:  # noqa: BLE001
            await self._cleanup_silently()
            raise DebugSessionStartFailed(f"unexpected start failure: {e}") from e

    async def __aexit__(self, *exc: Any) -> None:
        await self._cleanup_silently()

    # -- spawn + handshake -------------------------------------------------

    async def _spawn(self) -> None:
        """Launch ``robotcode debug-launch --tcp 127.0.0.1:0 -w``
        in the project's env. Parse the bound port from stdout
        within ``port_parse_timeout`` seconds, then connect TCP."""
        env_dir = Path(self.env_python_path).parent
        # On Windows scripts live in `Scripts/`, on POSIX in `bin/`.
        # We're spawning a console-app; resolve once via PATH order.
        rcode = env_dir / "robotcode"
        if not rcode.exists():
            # Try `Scripts/robotcode.exe` for Windows venvs.
            rcode_win = env_dir.parent / "Scripts" / "robotcode.exe"
            if rcode_win.exists():
                rcode = rcode_win
            else:
                raise DebugSessionStartFailed(
                    f"`robotcode` binary not found in environment "
                    f"({env_dir} or its Scripts/). Install "
                    f"`robotcode-debugger` into the project's env."
                )

        argv = [
            str(rcode),
            "debug-launch",
            "--tcp",
            "127.0.0.1:0",
            "-w",
            "--",
        ]
        if self.test_name:
            argv += ["--test", self.test_name]
        argv += self._extra_args
        argv.append(self.robot_path)

        # POSIX: spawn in a fresh process group so cleanup can reap the
        # entire subprocess tree (RobotCode → Robot Framework → Browser
        # library wrapper → Playwright → Chromium) via os.killpg, not
        # just the immediate child. Without this, orphaned grandchildren
        # routinely outlive the session and can block the next port-0
        # bind by holding shared state under ~/.cache/robotcode/.
        spawn_kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.STDOUT,
            "env": {**os.environ, "PYTHONUNBUFFERED": "1"},
        }
        if sys.platform != "win32":
            spawn_kwargs["start_new_session"] = True

        try:
            self._proc = await asyncio.create_subprocess_exec(*argv, **spawn_kwargs)
        except FileNotFoundError as e:
            raise DebugSessionStartFailed(
                f"failed to spawn robotcode: {e}"
            ) from e

        # Wait for the port-binding line on stdout. RobotCode emits
        # other startup chatter; parse line-by-line.
        port = await self._read_port_from_stdout()
        if port is None:
            self._raise_port_failure()

        # Connect the DAP client.
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError as e:
            raise DebugSessionStartFailed(
                f"could not connect to robotcode on port {port}: {e}"
            ) from e
        self._client = DapClient(reader, writer)
        self._wire_event_handlers(self._client)
        self._client.start()

    async def _read_port_from_stdout(self) -> int | None:
        if self._proc is None or self._proc.stdout is None:
            return None
        deadline = asyncio.get_running_loop().time() + self._port_parse_timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return None
            try:
                line_bytes = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=remaining
                )
            except TimeoutError:
                return None
            if not line_bytes:
                # EOF — robotcode exited before announcing a port.
                # `_raise_port_failure` will surface the captured tail.
                return None
            line = line_bytes.decode("utf-8", errors="replace").rstrip()
            if line:
                self._boot_log.append(line)
                # Cap retention so a chatty process can't OOM us.
                if len(self._boot_log) > 200:
                    self._boot_log = self._boot_log[-200:]
            logger.debug("[robotcode] %s", line)
            port = _parse_port(line)
            if port is not None:
                return port

    def _raise_port_failure(self) -> None:
        """Build a diagnostic error including the captured boot output.

        The plain "did not announce" message is useless to a user who
        doesn't know what robotcode normally prints; including the
        last ~20 lines makes it possible to spot common causes (missing
        package, syntax error in the test, hung language server)
        without re-running with backend DEBUG logging.
        """
        rc = self._proc.returncode if self._proc is not None else None
        tail_lines = self._boot_log[-20:]
        tail = "\n".join(tail_lines) if tail_lines else "(no output)"
        if rc is not None:
            raise DebugSessionStartFailed(
                f"robotcode exited with code {rc} during boot. "
                f"Last output:\n{tail}"
            )
        raise DebugSessionStartFailed(
            "robotcode did not announce a TCP port within "
            f"{self._port_parse_timeout} s. Last output from robotcode:\n{tail}"
        )

    async def _handshake(self) -> None:
        if self._client is None:
            raise DebugSessionStartFailed("DAP client not initialized")
        try:
            await self._client.request(
                "initialize",
                {
                    "clientID": "roboscope",
                    "clientName": "RoboScope",
                    "adapterID": "robotcode",
                    "linesStartAt1": True,
                    "columnsStartAt1": True,
                    "supportsVariableType": True,
                    "supportsRunInTerminalRequest": False,
                },
            )
            for bp in _group_by_file(self.breakpoints):
                await self._client.request(
                    "setBreakpoints",
                    {
                        "source": {"path": bp[0]},
                        "breakpoints": [{"line": ln} for ln in bp[1]],
                        "lines": list(bp[1]),
                    },
                )
            await self._client.request("configurationDone", {})
            await self._client.request("launch", self._launch_args())
        except DapApplicationError as e:
            raise DebugSessionStartFailed(
                f"DAP handshake step `{e.command}` failed: {e.message}"
            ) from e
        except (TimeoutError, DapProtocolError, OSError) as e:
            raise DebugSessionStartFailed(
                f"DAP handshake transport error: {e}"
            ) from e

    def _launch_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "target": self.robot_path,
            "noDebug": False,
        }
        if self.test_name:
            args["args"] = ["--test", self.test_name]
        return args

    # -- event wiring ------------------------------------------------------

    def _wire_event_handlers(self, client: DapClient) -> None:
        """Bind DAP event names to internal state-cache updates +
        the public events queue. Handlers run inside the read loop
        so they MUST be cheap and non-blocking — defer real work to
        the consumer side of the queue."""
        client.on_event("stopped", self._on_stopped)
        client.on_event("output", self._on_output)
        client.on_event("terminated", self._on_terminated)
        client.on_event("exited", self._on_terminated)

    def _on_stopped(self, body: dict[str, Any]) -> None:
        self.state.paused = True
        self.state.paused_reason = body.get("reason")
        self._publish_event("stopped", body)
        # Defer stack/scopes refresh to the consumer — touching
        # DapClient from inside the read loop's handler would
        # request → await on the same task.
        self._publish_event("state-stale", {})

    def _on_output(self, body: dict[str, Any]) -> None:
        line = str(body.get("output", "")).rstrip("\n")
        if line:
            self.state.output_lines.append(line)
        self._publish_event("output", body)

    def _on_terminated(self, body: dict[str, Any]) -> None:
        self.state.paused = False
        self.state.terminated = True
        self._publish_event("terminated", body)

    def _publish_event(self, kind: str, body: dict[str, Any]) -> None:
        """Drop oldest if the queue is full — a stalled consumer
        should NEVER backpressure the read loop. Operator visibility
        for a stuck consumer comes from the WARN log."""
        try:
            self.events.put_nowait({"kind": kind, "body": body})
        except asyncio.QueueFull:
            logger.warning(
                "RobotDebugSession event queue full — dropping oldest"
            )
            with suppress(asyncio.QueueEmpty):
                self.events.get_nowait()
            with suppress(asyncio.QueueFull):
                self.events.put_nowait({"kind": kind, "body": body})

    # -- cleanup -----------------------------------------------------------

    async def _cleanup_silently(self) -> None:
        # 1. Send DAP disconnect (best-effort).
        await self.disconnect()
        # 2. Close the DAP client.
        if self._client is not None:
            with suppress(Exception):
                await self._client.stop()
            self._client = None
        # 3. Wait for subprocess exit, escalate via group-kill so any
        #    grandchildren (Robot Framework → Browser library wrapper →
        #    Playwright → Chromium) get reaped along with the parent.
        if self._proc is not None:
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except TimeoutError:
                _kill_process_tree(self._proc)
                with suppress(TimeoutError, ProcessLookupError):
                    await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except ProcessLookupError:
                pass
            self._proc = None


def _group_by_file(bps: list[Breakpoint]) -> list[tuple[str, list[int]]]:
    """Group breakpoints by file path so we can issue one
    ``setBreakpoints`` request per file (DAP requires that)."""
    by_file: dict[str, list[int]] = {}
    for bp in bps:
        by_file.setdefault(bp.file, []).append(bp.line)
    return [(f, sorted(set(lines))) for f, lines in by_file.items()]


def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """SIGKILL the process group on POSIX, SIGKILL the parent on Windows.

    On POSIX we asked the kernel for ``start_new_session=True``, so
    ``proc.pid`` is the process-group leader; SIGKILL'ing the pgid
    reaps every descendant Robot Framework spawned. Without this, a
    Browser-library Playwright Chromium spawn that survives our
    immediate child becomes an orphan and can block the next debug
    session via shared cache directories.
    """
    if sys.platform == "win32":
        with suppress(ProcessLookupError):
            proc.kill()
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGKILL)
