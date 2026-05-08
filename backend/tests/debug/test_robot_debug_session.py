"""RobotDebugSession lifecycle tests.

Two layers:

1. **Unit / fake-robotcode** — a tiny Python helper stands in for
   ``robotcode debug-launch``. It parses ``--tcp HOST:PORT`` from
   argv, binds exactly that port, then runs a minimal in-process DAP
   server that replies success to every request. Keeps the test
   runtime tiny (no real RF startup, no Chromium) while exercising
   the actual subprocess-spawn → connect-poll → handshake pipeline.

2. **Integration** (``@pytest.mark.integration``) — spawns the real
   ``robotcode debug-launch`` from the user's default RoboScope venv
   against a tiny ``.robot`` file. Catches breaking changes in the
   robotcode CLI surface (the ``-w`` removal that bit us, future
   option drift, missing ``[debugger]`` extra) BEFORE they hit
   production. Skipped automatically when the venv isn't there.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest

from src.debug.robot_debug_session import (
    Breakpoint,
    DebugSessionStartFailed,
    RobotDebugSession,
    _allocate_free_port,
)

# ---------------------------------------------------------------------------
# Free-port allocator unit test
# ---------------------------------------------------------------------------


class TestAllocateFreePort:
    def test_returns_a_real_local_port(self) -> None:
        p = _allocate_free_port()
        assert 1 <= p <= 65535


# ---------------------------------------------------------------------------
# Spawn / handshake — the real pipeline against a fake DAP server
# ---------------------------------------------------------------------------


# Fake-robotcode helper: parse `--tcp HOST:PORT` from argv, bind that
# exact port, run a DAP server that successes everything we throw at
# it. Modern RobotCode rejects port 0 — we mirror that and always use
# a pre-allocated port.
_FAKE_ROBOTCODE_SCRIPT = '''#!/usr/bin/env python3
"""Fake `robotcode` for RobotDebugSession integration tests."""
import asyncio
import json
import sys


def encode(msg):
    body = json.dumps(msg).encode("utf-8")
    return f"Content-Length: {len(body)}\\r\\n\\r\\n".encode("ascii") + body


async def handle(reader, writer):
    while True:
        try:
            hdr = await reader.readuntil(b"\\r\\n\\r\\n")
        except (asyncio.IncompleteReadError, ConnectionError):
            return
        clen = 0
        for line in hdr[:-4].split(b"\\r\\n"):
            if line.lower().startswith(b"content-length:"):
                clen = int(line.split(b":", 1)[1].strip())
        body_bytes = await reader.readexactly(clen)
        req = json.loads(body_bytes)
        resp = {
            "seq": 0,
            "type": "response",
            "request_seq": req["seq"],
            "success": True,
            "command": req["command"],
            "body": {},
        }
        writer.write(encode(resp))
        await writer.drain()
        # Emit `initialized` right after the initialize response —
        # mirrors what the real RobotCode launcher does so the
        # in-process DAP client can drive setBreakpoints next.
        if req["command"] == "initialize":
            writer.write(encode({"seq": 0, "type": "event", "event": "initialized", "body": {}}))
            await writer.drain()


def parse_tcp_arg(argv):
    """Parse `--tcp HOST:PORT` (or `--tcp PORT`) from argv."""
    for i, a in enumerate(argv):
        if a == "--tcp" and i + 1 < len(argv):
            spec = argv[i + 1]
            if ":" in spec:
                host, port = spec.rsplit(":", 1)
                return host or "127.0.0.1", int(port)
            return "127.0.0.1", int(spec)
    raise SystemExit("--tcp HOST:PORT required")


async def main() -> None:
    host, port = parse_tcp_arg(sys.argv[1:])
    server = await asyncio.start_server(handle, host=host, port=port)
    async with server:
        await server.serve_forever()


asyncio.run(main())
'''


def _make_fake_robotcode(tmp_path: Path) -> Path:
    """Drop the fake script into ``tmp_path/bin/robotcode`` and seed
    the debugger plugin marker so the prereq check (used by callers)
    still passes if exercised. Returns ``env_python_path``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rcode = bin_dir / "robotcode"
    rcode.write_text(_FAKE_ROBOTCODE_SCRIPT, encoding="utf-8")
    rcode.chmod(0o755)
    env_python = bin_dir / "python"
    env_python.write_text("# placeholder\n", encoding="utf-8")
    return env_python


def _make_robot_file(tmp_path: Path) -> Path:
    f = tmp_path / "tests.robot"
    f.write_text(
        "*** Test Cases ***\n"
        "Sample\n"
        "    Log    hello\n",
        encoding="utf-8",
    )
    return f


class TestSpawnAndHandshake:
    @pytest.mark.asyncio
    async def test_full_lifecycle_with_fake_robotcode(self, tmp_path: Path) -> None:
        env_python = _make_fake_robotcode(tmp_path)
        robot = _make_robot_file(tmp_path)
        async with RobotDebugSession(
            robot_path=robot,
            test_name="Sample",
            breakpoints=[Breakpoint(str(robot), 3)],
            env_python_path=env_python,
            spawn_args=[],
        ) as session:
            await session.continue_()
            assert session._proc is not None  # noqa: SLF001
            assert session._proc.returncode is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_missing_robotcode_binary_raises_friendly(
        self, tmp_path: Path,
    ) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        env_python = bin_dir / "python"
        env_python.write_text("", encoding="utf-8")
        robot = _make_robot_file(tmp_path)
        with pytest.raises(DebugSessionStartFailed, match="not found"):
            async with RobotDebugSession(
                robot_path=robot,
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
            ):
                pass

    @pytest.mark.asyncio
    async def test_connect_timeout_raises(self, tmp_path: Path) -> None:
        # A robotcode that never opens its TCP listener — just sleeps.
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        rcode = bin_dir / "robotcode"
        rcode.write_text(
            "#!/usr/bin/env python3\n"
            "import time, sys\n"
            "sys.stdout.write('starting up...\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )
        rcode.chmod(0o755)
        env_python = bin_dir / "python"
        env_python.write_text("", encoding="utf-8")
        robot = _make_robot_file(tmp_path)
        with pytest.raises(DebugSessionStartFailed, match="did not start a TCP listener"):
            async with RobotDebugSession(
                robot_path=robot,
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
                port_parse_timeout=0.5,
            ):
                pass

    @pytest.mark.asyncio
    async def test_timeout_error_includes_captured_boot_output(
        self, tmp_path: Path,
    ) -> None:
        """Regression: users hit a bare error and had no idea what
        robotcode was actually saying. The error must echo the
        captured stdout tail so they can self-diagnose."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        rcode = bin_dir / "robotcode"
        rcode.write_text(
            "#!/usr/bin/env python3\n"
            "import time, sys\n"
            "sys.stdout.write('Loading Browser library...\\n')\n"
            "sys.stdout.write('Initializing language server...\\n')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )
        rcode.chmod(0o755)
        env_python = bin_dir / "python"
        env_python.write_text("", encoding="utf-8")
        robot = _make_robot_file(tmp_path)
        with pytest.raises(DebugSessionStartFailed) as exc_info:
            async with RobotDebugSession(
                robot_path=robot,
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
                port_parse_timeout=2.0,
            ):
                pass
        msg = str(exc_info.value)
        assert "Loading Browser library" in msg
        assert "Initializing language server" in msg

    @pytest.mark.asyncio
    async def test_robotcode_crash_during_boot_surfaces_returncode(
        self, tmp_path: Path,
    ) -> None:
        """If robotcode exits before listening, the error must carry
        the exit code AND the stderr/stdout tail. Pinned by the
        actual user-reported failure where ``-w`` was rejected."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        rcode = bin_dir / "robotcode"
        rcode.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdout.write('Error: No such option: -w\\n')\n"
            "sys.stdout.flush()\n"
            "sys.exit(2)\n",
            encoding="utf-8",
        )
        rcode.chmod(0o755)
        env_python = bin_dir / "python"
        env_python.write_text("", encoding="utf-8")
        robot = _make_robot_file(tmp_path)
        with pytest.raises(DebugSessionStartFailed) as exc_info:
            async with RobotDebugSession(
                robot_path=robot,
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
                port_parse_timeout=5.0,
            ):
                pass
        msg = str(exc_info.value)
        assert "exited with code 2" in msg
        assert "No such option: -w" in msg

    @pytest.mark.asyncio
    async def test_argv_does_not_include_legacy_dash_w_or_positional(
        self, tmp_path: Path,
    ) -> None:
        """Regression-pin against the actual production failure: the
        spawn must NOT pass ``-w`` (removed from modern robotcode) or
        a trailing positional ``<robot_path>`` (modern debug-launch
        takes only transport options; the script is sent via DAP
        ``launch`` payload).

        We can't use the full fake-robotcode here because we don't
        want it to actually open a port — we just want to inspect
        the argv. The fake exits with code 99 so the spawn fails
        with the diagnostic message, AFTER recording argv to a
        file we can read back."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        argv_log = tmp_path / "argv.log"
        rcode = bin_dir / "robotcode"
        rcode.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, json\n"
            f"open({str(argv_log)!r}, 'w').write(json.dumps(sys.argv))\n"
            "sys.exit(99)\n",
            encoding="utf-8",
        )
        rcode.chmod(0o755)
        env_python = bin_dir / "python"
        env_python.write_text("# placeholder\n", encoding="utf-8")
        robot = _make_robot_file(tmp_path)
        with pytest.raises(DebugSessionStartFailed, match="exited with code 99"):
            async with RobotDebugSession(
                robot_path=robot,
                test_name="Sample",
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
                port_parse_timeout=5.0,
            ):
                pass

        assert argv_log.is_file(), "fake robotcode never wrote its argv"
        import json
        argv = json.loads(argv_log.read_text())
        # argv[0] is the script path; the rest is the CLI we passed.
        cli_args = argv[1:]
        assert "-w" not in cli_args, (
            f"-w must NOT appear in argv (removed from modern robotcode): {cli_args}"
        )
        assert "--" not in cli_args, (
            f"trailing -- must NOT appear in argv (no positional path): {cli_args}"
        )
        assert str(robot) not in cli_args, (
            f"robot path must NOT be a CLI positional, only via DAP launch: {cli_args}"
        )
        # Sanity: --tcp 127.0.0.1:<port> WAS passed.
        assert "--tcp" in cli_args
        tcp_value = cli_args[cli_args.index("--tcp") + 1]
        assert tcp_value.startswith("127.0.0.1:")
        port_str = tcp_value.split(":", 1)[1]
        assert port_str.isdigit() and 1 <= int(port_str) <= 65535


# ---------------------------------------------------------------------------
# Integration test — real robotcode against a real venv
# ---------------------------------------------------------------------------


_DEFAULT_ROBOSCOPE_VENV = Path.home() / ".roboscope" / "venvs" / "roboscope-default"


@pytest.mark.integration
class TestRealRobotCodeSpawn:
    """End-to-end smoke against the user's installed robotcode CLI.

    Lives behind ``@pytest.mark.integration`` (skipped from default
    CI per ``pyproject.toml``) because it requires a venv with
    ``robotcode[debugger]`` + ``robotframework`` installed and takes
    several seconds.

    Run manually with::

        pytest -m integration tests/debug/test_robot_debug_session.py::TestRealRobotCodeSpawn

    The test creates a tiny ``.robot`` file, sets a breakpoint, and
    asserts the full spawn → handshake → setBreakpoints → launch →
    stopped pipeline completes against the actual CLI. Catches
    breaking changes in robotcode CLI flags (the ``-w`` removal that
    motivated this test) BEFORE they hit users.
    """

    def _venv_python(self) -> Path | None:
        env_python = _DEFAULT_ROBOSCOPE_VENV / "bin" / "python"
        if env_python.is_file():
            return env_python
        return None

    def _check_or_skip(self) -> Path:
        """Skip the test cleanly when the default venv isn't usable."""
        env_python = self._venv_python()
        if env_python is None:
            pytest.skip(
                "RoboScope default venv not found; install via prereq dialog "
                f"or `uv venv {_DEFAULT_ROBOSCOPE_VENV}` + `uv pip install "
                "robotcode[debugger] robotframework` first.",
            )
        if not (env_python.parent / "robotcode").is_file():
            pytest.skip("robotcode binary not in default venv")
        if not list(_DEFAULT_ROBOSCOPE_VENV.glob(
            "lib/python*/site-packages/robotcode/debugger",
        )):
            pytest.skip("robotcode-debugger plugin missing — install [debugger] extra")
        if not list(_DEFAULT_ROBOSCOPE_VENV.glob(
            "lib/python*/site-packages/robot",
        )):
            pytest.skip("robotframework not in default venv")
        return env_python

    def _make_demo_robot(self, tmp_path: Path) -> Path:
        # Line numbers (1-based):
        # 1: *** Test Cases ***
        # 2: Demo
        # 3:     Log    line one
        # 4:     Log    line two
        robot = tmp_path / "demo.robot"
        robot.write_text(
            "*** Test Cases ***\n"
            "Demo\n"
            "    Log    line one\n"
            "    Log    line two\n",
            encoding="utf-8",
        )
        return robot.resolve()  # macOS /var → /private/var

    @pytest.mark.asyncio
    async def test_real_spawn_handshake_and_test_runs(
        self, tmp_path: Path,
    ) -> None:
        """Confirms the spawn → handshake → setBreakpoints →
        configurationDone pipeline against the actual robotcode CLI.
        Asserts that a real test starts running (we see the RF banner
        on stdout) — i.e. all the protocol-level wiring works.

        This is the test that catches the `-w` removal, missing
        ``console: internalConsole``, wrong handshake order, and any
        future option drift in the robotcode debug-launch CLI.
        """
        env_python = self._check_or_skip()
        robot = self._make_demo_robot(tmp_path)

        async with RobotDebugSession(
            robot_path=robot,
            test_name="Demo",
            breakpoints=[Breakpoint(str(robot), 3)],
            env_python_path=env_python,
            port_parse_timeout=15.0,
        ) as session:
            # The RF banner ("====... \nDemo \n====...") proves the
            # child subprocess started, RF imports succeeded, and our
            # configurationDone unstuck it. This is what was broken
            # by the `-w` flag.
            saw_banner = False

            async def wait_for_banner() -> None:
                nonlocal saw_banner
                while not saw_banner:
                    evt = await session.events.get()
                    if evt.get("kind") == "output":
                        body = evt.get("body") or {}
                        out = str(body.get("output", ""))
                        if "Demo" in out and "===" in out:
                            saw_banner = True
                            return
                    if evt.get("kind") == "terminated":
                        return

            await asyncio.wait_for(wait_for_banner(), timeout=20.0)
            assert saw_banner, (
                "Robot Framework never started executing — spawn or "
                "handshake regression. Boot log: "
                f"{session._boot_log[-30:]}"  # noqa: SLF001
            )

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason=(
            "Known regression — DEBUG-5: breakpoint stop is not yet "
            "wired through the launcher → child proxy chain. Test runs "
            "end-to-end but the `stopped` event never arrives. Spec at "
            "_bmad-output/.../debug-5-breakpoint-resolution.md. This "
            "xfail prevents silent regressions when the proxy is fixed."
        ),
        strict=True,
    )
    async def test_real_breakpoint_pauses_execution(
        self, tmp_path: Path,
    ) -> None:
        """Pinned-but-xfail regression test for the actual user-visible
        bug. When this turns green, the launcher → child setBreakpoints
        proxy is finally working and we can flip to a normal assertion.
        """
        env_python = self._check_or_skip()
        robot = self._make_demo_robot(tmp_path)

        async with RobotDebugSession(
            robot_path=robot,
            test_name="Demo",
            breakpoints=[Breakpoint(str(robot), 3)],
            env_python_path=env_python,
            port_parse_timeout=15.0,
        ) as session:
            async def wait_for_stopped() -> dict[str, object]:
                while True:
                    evt = await session.events.get()
                    if evt.get("kind") == "stopped":
                        return evt
                    if evt.get("kind") == "terminated":
                        pytest.fail("Terminated before breakpoint stop")

            evt = await asyncio.wait_for(wait_for_stopped(), timeout=20.0)
            assert evt["kind"] == "stopped"
            await session.continue_()
            with contextlib.suppress(asyncio.TimeoutError):
                while True:
                    e = await asyncio.wait_for(session.events.get(), timeout=10.0)
                    if e.get("kind") == "terminated":
                        break

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason=(
            "Known regression — DEBUG-5 layer-isolation: even an "
            "unconditional `pause` request after configurationDone "
            "never produces a `stopped` event. Strongly suggests the "
            "bug is in the launcher → us event-proxy direction, not "
            "in breakpoint path resolution. When this turns green at "
            "the same time as the breakpoint test, the fix is the "
            "same root cause."
        ),
        strict=True,
    )
    async def test_real_pause_request_pauses_execution(
        self, tmp_path: Path,
    ) -> None:
        """Diagnostic isolation test: forces a stop via the DAP `pause`
        request, completely bypassing breakpoint path-resolution. If
        this xfails alongside the breakpoint test, the issue is in the
        event-forwarding chain (launcher → us); if this passes but
        breakpoint test still xfails, the issue is narrowly in
        breakpoint path resolution. Either signal points the next
        investigator at the right layer.
        """
        env_python = self._check_or_skip()
        robot = self._make_demo_robot(tmp_path)

        async with RobotDebugSession(
            robot_path=robot,
            test_name="Demo",
            breakpoints=[],  # No breakpoints — testing pause path only.
            env_python_path=env_python,
            port_parse_timeout=15.0,
        ) as session:
            # Wait briefly for the run to start, then request pause.
            await asyncio.sleep(1.5)
            assert session._client is not None  # noqa: SLF001
            # The DAP `pause` request takes a thread_id; RobotCode uses
            # a single main thread and accepts any plausible ID.
            with contextlib.suppress(Exception):
                await session._client.request("pause", {"threadId": 1})  # noqa: SLF001

            async def wait_for_stopped() -> dict[str, object]:
                while True:
                    evt = await session.events.get()
                    if evt.get("kind") == "stopped":
                        return evt
                    if evt.get("kind") == "terminated":
                        pytest.fail("Terminated before pause stop")

            evt = await asyncio.wait_for(wait_for_stopped(), timeout=15.0)
            assert evt["kind"] == "stopped"


