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
import signal
import socket
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
# Port helpers
# ---------------------------------------------------------------------------


def _allocate_free_port() -> int:
    """Bind 127.0.0.1:0 to get a kernel-assigned free port, then close.

    The TOCTOU window between us closing the socket and robotcode
    binding the same port is acceptable for a local single-user dev
    tool. Modern RobotCode rejects ``--tcp 127.0.0.1:0`` (validates
    1<=port<=65535), so we have to allocate ahead of time.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


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
        # Backgrounded launch request — see ``_handshake`` for why we
        # fire-and-don't-await it.
        self._launch_fut: asyncio.Task[Any] | None = None
        self.state = DebugState()
        # Stdout/stderr drainage — robotcode communicates over the DAP
        # TCP socket once we connect, but its boot output and any RF
        # ``Log``/``print`` keyword writes still go to the merged
        # stdout pipe. We pump them into a 200-line ring buffer so:
        # (a) the pipe never fills and blocks robotcode mid-test,
        # (b) we have the last 20 lines on hand for a meaningful error
        # message if the spawn fails before listening.
        self._boot_log: list[str] = []
        self._output_pump_task: asyncio.Task[None] | None = None
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
        """Launch ``robotcode debug-launch --tcp 127.0.0.1:<port>`` in
        the project's env, then poll-connect TCP until the DAP server
        is accepting. The target ``.robot`` file + test name go to the
        DAP server via the ``launch`` request payload (``_launch_args``),
        not as CLI args — modern RobotCode's debug-launch CLI takes only
        transport/mode options.
        """
        env_dir = Path(self.env_python_path).parent
        # On Windows scripts live in `Scripts/`, on POSIX in `bin/`.
        rcode = env_dir / "robotcode"
        if not rcode.exists():
            rcode_win = env_dir.parent / "Scripts" / "robotcode.exe"
            if rcode_win.exists():
                rcode = rcode_win
            else:
                raise DebugSessionStartFailed(
                    f"`robotcode` binary not found in environment "
                    f"({env_dir} or its Scripts/). Install "
                    f"`robotcode[debugger]` into the project's env."
                )

        # Pre-allocate a free port — modern RobotCode rejects port 0.
        port = _allocate_free_port()
        argv = [str(rcode), "debug-launch", "--tcp", f"127.0.0.1:{port}"]
        argv += self._extra_args

        # POSIX: spawn in a fresh process group so cleanup can reap the
        # entire subprocess tree (RobotCode → Robot Framework → Browser
        # library wrapper → Playwright → Chromium) via os.killpg, not
        # just the immediate child.
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

        # Drain stdout in the background — both for diagnostics on
        # connect-failure AND so the pipe doesn't fill once the test
        # starts emitting Log keyword output.
        self._output_pump_task = asyncio.create_task(
            self._pump_subprocess_output(),
            name=f"debug-stdout-pump-{port}",
        )

        # Poll-connect to the DAP server. RobotCode prints nothing when
        # ready (verified empirically against robotcode>=0.x), so we
        # can't wait on stdout — we have to retry-connect until the
        # socket accepts.
        try:
            reader, writer = await self._connect_with_retry(port)
        except DebugSessionStartFailed:
            raise

        self._client = DapClient(reader, writer)
        self._wire_event_handlers(self._client)
        self._client.start()

    async def _pump_subprocess_output(self) -> None:
        """Background task that drains the merged stdout/stderr pipe
        line-by-line into the ring buffer. Runs for the life of the
        session; cancelled in cleanup."""
        if self._proc is None or self._proc.stdout is None:
            return
        try:
            while True:
                line_bytes = await self._proc.stdout.readline()
                if not line_bytes:
                    return  # EOF — process exited
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._boot_log.append(line)
                    if len(self._boot_log) > 200:
                        self._boot_log = self._boot_log[-200:]
                logger.debug("[robotcode] %s", line)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("subprocess output pump crashed")

    async def _connect_with_retry(
        self, port: int,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Repeatedly try to connect to the DAP server until it accepts
        or the timeout fires. Surfaces a diagnostic failure that
        includes the last 20 lines of robotcode stdout.
        """
        deadline = asyncio.get_running_loop().time() + self._port_parse_timeout
        last_err: OSError | None = None
        while asyncio.get_running_loop().time() < deadline:
            if self._proc is not None and self._proc.returncode is not None:
                # Process exited — give the output pump a beat to drain
                # final bytes before raising.
                await asyncio.sleep(0.05)
                self._raise_port_failure()
            try:
                return await asyncio.open_connection("127.0.0.1", port)
            except (ConnectionRefusedError, OSError) as e:
                last_err = e
                await asyncio.sleep(0.1)
        # Timeout — still not accepting. Drain a final beat then raise.
        await asyncio.sleep(0.05)
        if last_err is not None:
            logger.debug("last connect error before timeout: %s", last_err)
        self._raise_port_failure()
        raise AssertionError("unreachable")  # for type-checker

    def _raise_port_failure(self) -> None:
        """Build a diagnostic error including the captured boot output.

        The plain "did not announce" / "could not connect" message is
        useless to a user who doesn't know what robotcode normally
        prints. Including the last ~20 lines lets users spot the
        common causes (wrong CLI flag, missing package, missing test
        name, broken venv) without re-running with backend DEBUG.
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
            "robotcode did not start a TCP listener within "
            f"{self._port_parse_timeout} s. Last output from robotcode:\n{tail}"
        )

    async def _handshake(self) -> None:
        """Drive the DAP launch sequence per spec order.

        Per DAP (microsoft.github.io/debug-adapter-protocol):

        1. Send ``initialize`` request, await capabilities response.
        2. Send ``launch`` request — fire-and-DON'T-await. DAP servers
           commonly defer the launch response until after
           ``configurationDone``; awaiting here deadlocks.
        3. Wait for the ``initialized`` event. The server emits this
           when ready to accept configuration requests.
        4. Send ``setBreakpoints`` for each file.
        5. Send ``configurationDone`` — test execution begins.

        Sending ``setBreakpoints`` BEFORE ``initialized`` arrives is
        what the integration test exists to catch — modern RobotCode
        rejects it with ``Unknown Command 'setBreakpoints'``.
        """
        if self._client is None:
            raise DebugSessionStartFailed("DAP client not initialized")

        initialized_event = asyncio.Event()

        def _on_initialized(_body: dict[str, Any]) -> None:
            initialized_event.set()

        self._client.on_event("initialized", _on_initialized)

        try:
            # 1. Initialize.
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

            # 2. Fire launch — fire-and-don't-await. Cancelled in
            # ``_cleanup_silently``; failures surface via the event
            # stream / pending future error.
            self._launch_fut = asyncio.ensure_future(
                self._client.request("launch", self._launch_args())
            )

            # 3. Wait for `initialized` event before any breakpoints.
            try:
                await asyncio.wait_for(initialized_event.wait(), timeout=15.0)
            except TimeoutError as e:
                # Surface launch_fut state if it errored — common cause
                # of "no initialized event" is a malformed launch
                # payload that the launcher rejected synchronously.
                launch_err = ""
                if self._launch_fut is not None and self._launch_fut.done():
                    fut_exc = self._launch_fut.exception()
                    if fut_exc is not None:
                        launch_err = f" (launch request failed: {fut_exc})"
                tail = "\n".join(self._boot_log[-20:]) or "(no output)"
                raise DebugSessionStartFailed(
                    f"DAP server did not emit `initialized` event within 15 s"
                    f"{launch_err}. Last output from robotcode:\n{tail}"
                ) from e

            # 4. Set breakpoints.
            for bp_file, bp_lines in _group_by_file(self.breakpoints):
                await self._client.request(
                    "setBreakpoints",
                    {
                        "source": {"path": bp_file},
                        "breakpoints": [{"line": ln} for ln in bp_lines],
                        "lines": list(bp_lines),
                    },
                )

            # 5. Configuration done — test execution begins.
            await self._client.request("configurationDone", {})
        except DapApplicationError as e:
            raise DebugSessionStartFailed(
                f"DAP handshake step `{e.command}` failed: {e.message}"
            ) from e
        except (TimeoutError, DapProtocolError, OSError) as e:
            raise DebugSessionStartFailed(
                f"DAP handshake transport error: {e}"
            ) from e

    def _launch_args(self) -> dict[str, Any]:
        """Build the DAP ``launch`` payload for RobotCode's launcher.

        RobotCode's ``debug-launch`` is a *launcher* — on receiving
        ``launch`` it spawns a child ``robotcode debug`` process that
        actually runs the test, then proxies DAP traffic. The minimum
        set of fields the launcher needs:

        * ``request`` — discriminator, always "launch".
        * ``python`` — interpreter path the launcher uses for the
          child run (must be the project's env Python so RF imports
          resolve).
        * ``cwd`` — working directory; we pass the robot file's
          parent so relative ``Resource`` imports work.
        * ``target`` — the ``.robot`` file to run.
        * ``console: "internalConsole"`` — without this RobotCode
          tries to dispatch a ``runInTerminal`` request to us, which
          we don't handle. Internal console makes the launcher spawn
          the child itself.
        * ``args: ["--test", "<name>"]`` — filter to one test case.
        """
        args: dict[str, Any] = {
            "request": "launch",
            "python": self.env_python_path,
            "cwd": str(Path(self.robot_path).parent),
            "target": self.robot_path,
            "console": "internalConsole",
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
        # 3. Cancel the launch future + stdout pump so they don't keep
        #    closed-pipe handles open while the subprocess tears down.
        if self._launch_fut is not None and not self._launch_fut.done():
            self._launch_fut.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._launch_fut
            self._launch_fut = None
        if self._output_pump_task is not None and not self._output_pump_task.done():
            self._output_pump_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._output_pump_task
            self._output_pump_task = None
        # 4. Wait for subprocess exit, escalate via group-kill so any
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
