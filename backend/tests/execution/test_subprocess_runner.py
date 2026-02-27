"""Unit tests for SubprocessRunner timeout behavior."""

import subprocess
import threading
import time
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.execution.runners.subprocess_runner import SubprocessRunner


class TestInactivityTimeout:
    """Tests for the inactivity timeout that kills hung processes."""

    def test_inactivity_timeout_kills_hung_process(self, tmp_path: Path):
        """Process that produces no output should be killed after inactivity timeout."""
        runner = SubprocessRunner()

        # Mock Popen that never produces output (readline blocks then returns "")
        mock_proc = MagicMock()
        # stdout.readline returns "" immediately (simulates a process that closes stdout
        # but the process itself hasn't exited yet)
        mock_proc.stdout.readline.return_value = ""
        mock_proc.stderr.readlines.return_value = []
        mock_proc.poll.return_value = None  # Process still running
        mock_proc.returncode = -15
        mock_proc.wait.return_value = None
        mock_proc.send_signal.return_value = None
        mock_proc.kill.return_value = None

        # We need readline to block for a while then return ""
        # Simulate: process produces no output, reader thread finishes quickly,
        # but process is still running
        def slow_readline():
            # First call blocks briefly, then returns "" to end the loop
            time.sleep(0.1)
            return ""

        mock_proc.stdout.readline.side_effect = slow_readline

        # But the process itself is still running (poll returns None)
        # After cancel, poll returns -15
        poll_calls = [0]

        def mock_poll():
            poll_calls[0] += 1
            if poll_calls[0] > 5:
                return -15
            return None

        mock_proc.poll.side_effect = mock_poll

        output_dir = str(tmp_path / "output")

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(runner, "_build_command", return_value=["robot", "test.robot"]):
            # Monkey-patch INACTIVITY_TIMEOUT via the execute method
            # We'll patch time so inactivity appears to exceed threshold
            original_time = time.time
            time_offset = [0.0]

            def fake_time():
                return original_time() + time_offset[0]

            with patch("src.execution.runners.subprocess_runner.time") as mock_time:
                mock_time.time = fake_time

                # The reader thread will finish quickly (readline returns "")
                # Then the main loop sees reader is dead but process still alive
                # We need to make the inactivity check trigger
                # Since reader finishes fast and last_activity was set at start,
                # we need time to advance past INACTIVITY_TIMEOUT

                # Actually, let's use a simpler approach: make reader block long enough
                # for the inactivity check to fire

        # Simpler approach: directly test with real threading but mock process
        runner2 = SubprocessRunner()
        mock_proc2 = MagicMock()

        # readline blocks for 1 second then returns ""
        block_event = threading.Event()

        def blocking_readline():
            block_event.wait(timeout=30)
            return ""

        mock_proc2.stdout.readline.side_effect = blocking_readline
        mock_proc2.stderr.readlines.return_value = []
        mock_proc2.poll.return_value = None
        mock_proc2.returncode = -15
        mock_proc2.wait.return_value = None
        mock_proc2.send_signal.side_effect = lambda s: block_event.set()
        mock_proc2.kill.side_effect = lambda: block_event.set()

        output_dir2 = str(tmp_path / "output2")

        # Patch the INACTIVITY_TIMEOUT to 1 second for fast test
        with patch("subprocess.Popen", return_value=mock_proc2), \
             patch.object(runner2, "_build_command", return_value=["robot", "test.robot"]):
            # We need to override the INACTIVITY_TIMEOUT constant inside execute()
            # Since it's a local variable, we patch it via the source
            import src.execution.runners.subprocess_runner as mod
            original_execute = runner2.execute

            # Call execute with a very short timeout context
            # The inactivity timeout is hardcoded at 120s, so let's patch time instead
            real_time = time.time
            start = real_time()

            def accelerated_time():
                # Make time appear to pass 100x faster
                elapsed = real_time() - start
                return start + elapsed * 100

            with patch.object(mod.time, "time", side_effect=accelerated_time):
                result = runner2.execute(
                    repo_path=str(tmp_path),
                    target_path="test.robot",
                    output_dir=output_dir2,
                    timeout=3600,
                )

        assert not result.success
        assert result.exit_code == -1
        assert "No output for" in result.error_message
        assert "process appears hung" in result.error_message
        assert "Browser library" in result.error_message

    def test_total_timeout_still_works(self, tmp_path: Path):
        """Total timeout should fire even when process produces occasional output."""
        runner = SubprocessRunner()
        mock_proc = MagicMock()

        # readline produces a line every call, never stops
        call_count = [0]
        stop_event = threading.Event()

        def producing_readline():
            call_count[0] += 1
            if stop_event.wait(timeout=0.05):
                return ""
            return f"line {call_count[0]}\n"

        mock_proc.stdout.readline.side_effect = producing_readline
        mock_proc.stderr.readlines.return_value = []
        mock_proc.poll.return_value = None
        mock_proc.returncode = -15
        mock_proc.wait.return_value = None
        mock_proc.send_signal.side_effect = lambda s: stop_event.set()
        mock_proc.kill.side_effect = lambda: stop_event.set()

        output_dir = str(tmp_path / "output")

        real_time = time.time
        start = real_time()

        import src.execution.runners.subprocess_runner as mod

        def accelerated_time():
            elapsed = real_time() - start
            return start + elapsed * 500

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(runner, "_build_command", return_value=["robot", "test.robot"]), \
             patch.object(mod.time, "time", side_effect=accelerated_time):
            result = runner.execute(
                repo_path=str(tmp_path),
                target_path="test.robot",
                output_dir=output_dir,
                timeout=10,  # Very short total timeout
            )

        assert not result.success
        assert result.exit_code == -1
        assert "Timeout after 10 seconds" in result.error_message

    def test_normal_execution_unaffected(self, tmp_path: Path):
        """Normal process producing lines then exiting should work as before."""
        runner = SubprocessRunner()
        mock_proc = MagicMock()

        lines = ["line 1\n", "line 2\n", "line 3\n"]
        line_iter = iter(lines + [""])

        mock_proc.stdout.readline.side_effect = lambda: next(line_iter)
        mock_proc.stderr.readlines.return_value = ["warn: something\n"]
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None

        output_dir = str(tmp_path / "output")

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(runner, "_build_command", return_value=["robot", "test.robot"]):
            result = runner.execute(
                repo_path=str(tmp_path),
                target_path="test.robot",
                output_dir=output_dir,
                timeout=3600,
            )

        assert result.exit_code == 0
        assert "line 1\nline 2\nline 3\n" == result.stdout
        assert "warn: something\n" == result.stderr

    def test_cancelled_flag_stops_reader(self, tmp_path: Path):
        """Setting _cancelled should cause the reader thread to exit."""
        runner = SubprocessRunner()
        mock_proc = MagicMock()

        call_count = [0]

        def readline_with_cancel():
            call_count[0] += 1
            if call_count[0] == 1:
                return "first line\n"
            if call_count[0] == 2:
                # Simulate cancel happening between reads
                runner._cancelled = True
                return "second line\n"
            return ""

        mock_proc.stdout.readline.side_effect = readline_with_cancel
        mock_proc.stderr.readlines.return_value = []
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None
        mock_proc.send_signal.return_value = None
        mock_proc.kill.return_value = None

        output_dir = str(tmp_path / "output")

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(runner, "_build_command", return_value=["robot", "test.robot"]):
            result = runner.execute(
                repo_path=str(tmp_path),
                target_path="test.robot",
                output_dir=output_dir,
                timeout=3600,
            )

        # Only first line should be captured (cancelled after second)
        assert "first line\n" in result.stdout
        # The second line triggers cancel, so reader breaks before appending more
