"""RobotDebugSession lifecycle tests.

We DON'T spawn `robotcode` here. Instead, the session's spawn step
points at a tiny Python helper that prints a fake `Listening on
127.0.0.1:<port>` line and then runs a minimal in-process DAP
server that responds to `initialize` / `setBreakpoints` /
`configurationDone` / `launch` / control / `disconnect`.

That keeps the test runtime tiny (no real RF startup, no Chromium)
while still exercising the actual subprocess-spawn → port-parse →
TCP-connect → handshake pipeline end to end.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.debug.robot_debug_session import (
    Breakpoint,
    DebugSessionStartFailed,
    RobotDebugSession,
    _parse_port,
)

# ---------------------------------------------------------------------------
# Port-line parser unit tests
# ---------------------------------------------------------------------------


class TestParsePort:
    def test_typical_listening_line(self) -> None:
        assert _parse_port("Listening on 127.0.0.1:54321") == 54321

    def test_localhost_alias(self) -> None:
        assert _parse_port("Bound to localhost:8000 (DAP)") == 8000

    def test_ipv6_loopback(self) -> None:
        assert _parse_port("Server [::1]:6612 ready") == 6612

    def test_no_port_returns_none(self) -> None:
        assert _parse_port("No port info here.") is None

    def test_out_of_range_port_returns_none(self) -> None:
        # 99999 is out of the 1..65535 range; reject so we don't
        # accidentally extract a substring of a longer number.
        assert _parse_port("127.0.0.1:99999 weird") is None

    def test_chatter_around_port_doesnt_break(self) -> None:
        line = "[2026-05-08 12:00:00] INFO  Server up at 127.0.0.1:5555 ready"
        assert _parse_port(line) == 5555


# ---------------------------------------------------------------------------
# Spawn / handshake — the real pipeline against a fake server
# ---------------------------------------------------------------------------


# A minimal helper script we'll dump to a temp file and treat as
# the "robotcode" binary. It picks an ephemeral port, prints the
# Listening line, then runs an asyncio DAP server that responds to
# every command we throw at it. Imported here as a string so we
# can write it to disk inside the fixture.
_FAKE_ROBOTCODE_SCRIPT = '''#!/usr/bin/env python3
"""Fake `robotcode` for RobotDebugSession integration tests.

Reads the same argv shape (`debug-launch --tcp 127.0.0.1:0 -w …`),
binds an ephemeral port, prints the announce line, then accepts a
single TCP client and replies success to every DAP request.
"""
import asyncio
import json
import socket
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


async def main() -> None:
    server = await asyncio.start_server(handle, host="127.0.0.1", port=0)
    port = server.sockets[0].getsockname()[1]
    sys.stdout.write(f"Listening on 127.0.0.1:{port}\\n")
    sys.stdout.flush()
    async with server:
        await server.serve_forever()


asyncio.run(main())
'''


def _make_fake_robotcode(tmp_path: Path) -> Path:
    """Drop the fake script into `tmp_path/bin/robotcode` and
    return the env_python_path the session expects (one dir above
    the bin/ folder)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rcode = bin_dir / "robotcode"
    rcode.write_text(_FAKE_ROBOTCODE_SCRIPT, encoding="utf-8")
    rcode.chmod(0o755)
    # Make the file actually executable as a Python script — the
    # session resolves robotcode by `<env_python_path>.parent /
    # robotcode`. We point env_python_path at `<tmp>/bin/python`
    # so `parent == bin/` matches `bin/robotcode`.
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
            # Send a control command — the fake echoes success.
            await session.continue_()
            # Subprocess is alive throughout the context.
            assert session._proc is not None  # noqa: SLF001
            assert session._proc.returncode is None  # noqa: SLF001
        # Context exit cleaned up.
        # NOTE: _proc is reset to None by _cleanup_silently after wait().

    @pytest.mark.asyncio
    async def test_missing_robotcode_binary_raises_friendly(
        self, tmp_path: Path
    ) -> None:
        # bin/ exists but no robotcode inside.
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
    async def test_port_parse_timeout_raises(self, tmp_path: Path) -> None:
        # A robotcode that never prints a port line — we use a
        # tiny script that just sleeps.
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
        with pytest.raises(DebugSessionStartFailed, match="did not announce"):
            async with RobotDebugSession(
                robot_path=robot,
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
                port_parse_timeout=0.2,
            ):
                pass

    @pytest.mark.asyncio
    async def test_timeout_error_includes_captured_boot_output(self, tmp_path: Path) -> None:
        """Regression: users hit a bare 'did not announce' message and
        had no idea what robotcode was actually saying. The error must
        echo the captured stdout tail so they can self-diagnose."""
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
                # 2 s gives Python interpreter cold-start + two writes
                # ample headroom while keeping the test fast.
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
        """If robotcode exits before announcing a port, the error must
        carry the exit code (so the user can spot e.g. an 'invalid
        argument' crash that always exits 2)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        rcode = bin_dir / "robotcode"
        rcode.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stderr.write('FATAL: missing config\\n')\n"
            "sys.exit(2)\n",
            encoding="utf-8",
        )
        rcode.chmod(0o755)
        env_python = bin_dir / "python"
        env_python.write_text("", encoding="utf-8")
        robot = _make_robot_file(tmp_path)
        with pytest.raises(DebugSessionStartFailed, match="exited with code 2"):
            async with RobotDebugSession(
                robot_path=robot,
                breakpoints=[Breakpoint(str(robot), 3)],
                env_python_path=env_python,
                port_parse_timeout=5.0,
            ):
                pass
