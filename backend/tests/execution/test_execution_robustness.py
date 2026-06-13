"""Regression tests for the execution-robustness fixes (demo-readiness Pass 3).

Covers the QA edge-case audit findings:
  - C1: a cancel that lands during prepare()/sync must NOT be erased by
        execute() (it used to reset `_cancelled = False` and run anyway).
  - C2: stderr is drained concurrently so a stderr-heavy process can't
        deadlock on a full OS pipe and be mis-reported as a hang.
  - H1: timeouts are flagged explicitly (`RunResult.timed_out`) instead of
        being sniffed out of the human-readable error message.
  - H2: a docker timeout is detected by exception type and stops the
        container.

Each test would fail against the pre-fix code.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from src.execution.runners.base import RunResult
from src.execution.runners.docker_runner import DockerRunner
from src.execution.runners.subprocess_runner import SubprocessRunner


def test_runresult_terminal_flags_default_false() -> None:
    rr = RunResult(success=True)
    assert rr.timed_out is False
    assert rr.cancelled is False


# ----- C1: cancel before execute short-circuits (both runners) -----


def test_subprocess_cancel_before_execute_does_not_launch(tmp_path) -> None:
    runner = SubprocessRunner(venv_path=None)
    runner.cancel()  # cancel lands during prepare(); _process is still None

    with patch(
        "src.execution.runners.subprocess_runner.subprocess.Popen"
    ) as popen:
        result = runner.execute(
            repo_path=str(tmp_path),
            target_path="suite.robot",
            output_dir=str(tmp_path / "out"),
        )

    popen.assert_not_called()  # the suite must NOT run
    assert result.cancelled is True
    assert result.success is False


def test_docker_cancel_before_execute_does_not_launch(tmp_path) -> None:
    runner = DockerRunner(image="example:latest")
    runner._cancelled = True

    with patch.object(runner, "_get_client") as get_client:
        result = runner.execute(
            repo_path=str(tmp_path),
            target_path="suite.robot",
            output_dir=str(tmp_path / "out"),
        )

    get_client.assert_not_called()  # never even touch docker
    assert result.cancelled is True
    assert result.success is False


# ----- C2: stderr-heavy process must not deadlock -----


def test_subprocess_drains_stderr_without_deadlock(tmp_path, monkeypatch) -> None:
    """Write far more than the OS pipe buffer (~64 KB) to stderr. Before the
    fix (stderr read only after wait()) the child blocked on the full pipe
    and the poll loop reported a false hang; now stderr is drained
    concurrently so the process exits cleanly."""
    runner = SubprocessRunner(venv_path=None)
    script = (
        "import sys; sys.stderr.write('E' * 200000); sys.stderr.flush(); "
        "sys.stdout.write('done\\n'); sys.stdout.flush(); sys.exit(0)"
    )
    monkeypatch.setattr(
        runner, "_build_command", lambda **kwargs: [sys.executable, "-c", script]
    )

    result = runner.execute(
        repo_path=str(tmp_path),
        target_path="suite.robot",
        output_dir=str(tmp_path / "out"),
        timeout=30,
    )

    assert result.exit_code == 0
    assert result.success is True
    assert result.timed_out is False
    assert len(result.stderr) >= 200000  # full stderr captured, not truncated


# ----- H1 / H2: timeout detection -----


def test_docker_is_timeout_error_detects_by_type() -> None:
    class ReadTimeout(Exception):  # noqa: N818 (mirror requests' real class name)
        pass

    class ConnectTimeout(Exception):  # noqa: N818 (mirror requests' real class name)
        pass

    assert DockerRunner._is_timeout_error(ReadTimeout()) is True
    assert DockerRunner._is_timeout_error(ConnectTimeout()) is True
    assert DockerRunner._is_timeout_error(ValueError("nope")) is False


def test_docker_timeout_flags_result_and_stops_container(tmp_path) -> None:
    """A read-timeout from the docker client must be flagged timed_out AND
    trigger a best-effort container stop (H2: wait(timeout=) doesn't stop it)."""

    class ReadTimeout(Exception):  # noqa: N818 (mirror requests' real class name)
        pass

    runner = DockerRunner(image="example:latest")

    class _FakeContainer:
        def __init__(self):
            self.stopped = False

        def logs(self, **kwargs):
            return iter(())  # no output, then wait() times out

        def wait(self, **kwargs):
            raise ReadTimeout("read timed out")

        def stop(self, **kwargs):
            self.stopped = True

        def remove(self, **kwargs):
            pass

    fake_container = _FakeContainer()

    class _FakeClient:
        class containers:  # noqa: N801 (mirror docker-py client.containers API)
            @staticmethod
            def run(**kwargs):
                return fake_container

    with patch.object(runner, "_get_client", return_value=_FakeClient()):
        result = runner.execute(
            repo_path=str(tmp_path),
            target_path="suite.robot",
            output_dir=str(tmp_path / "out"),
            timeout=5,
        )

    assert result.timed_out is True
    assert result.success is False
    assert "Timeout" in result.error_message
    assert fake_container.stopped is True  # container was stopped, not leaked
