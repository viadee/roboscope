"""Story TEST-2 — `DockerRunner` unit coverage.

CLAUDE.md flagged DockerRunner as a high-risk gap. The runner
spawns a Docker container per test execution, streams logs, handles
cancel + cleanup, and translates docker-py exceptions into typed
errors. Until this story none of that was covered.

Strategy: mock the docker-py client and container objects. The
runner's surface against docker-py is tiny (`images.get`,
`images.pull`, `containers.run`, `container.logs`, `wait`, `stop`,
`kill`, `remove`) — easy to stub.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.execution.runners.docker_runner import (
    DockerImageNotFoundError,
    DockerRunner,
)


# ---------------------------------------------------------------------------
# _build_robot_command — pure string-building, no docker involved
# ---------------------------------------------------------------------------


class TestBuildRobotCommand:
    def setup_method(self):
        self.runner = DockerRunner()

    def test_minimal(self):
        cmd = self.runner._build_robot_command(target_path="suite.robot")
        # The command must point robot at /output and the target.
        assert "python -m robot" in cmd
        assert "--outputdir /output" in cmd
        assert cmd.endswith(" suite.robot")

    def test_loglevel_and_color_off(self):
        cmd = self.runner._build_robot_command(target_path="x")
        assert "--loglevel INFO" in cmd
        assert "--consolecolors off" in cmd

    def test_tags_include_single(self):
        cmd = self.runner._build_robot_command(
            target_path="x", tags_include="smoke",
        )
        assert "--include smoke" in cmd

    def test_tags_include_multiple_csv(self):
        cmd = self.runner._build_robot_command(
            target_path="x", tags_include="smoke, regression , api",
        )
        # Whitespace is stripped, each tag becomes its own --include.
        for tag in ("smoke", "regression", "api"):
            assert f"--include {tag}" in cmd

    def test_tags_exclude(self):
        cmd = self.runner._build_robot_command(
            target_path="x", tags_exclude="slow,flaky",
        )
        assert "--exclude slow" in cmd
        assert "--exclude flaky" in cmd

    def test_variables(self):
        cmd = self.runner._build_robot_command(
            target_path="x", variables={"BROWSER": "chromium", "URL": "http://app"},
        )
        assert "--variable BROWSER:chromium" in cmd
        assert "--variable URL:http://app" in cmd

    def test_combination(self):
        cmd = self.runner._build_robot_command(
            target_path="suite/folder/",
            tags_include="smoke",
            tags_exclude="slow",
            variables={"X": "1"},
        )
        assert "--include smoke" in cmd
        assert "--exclude slow" in cmd
        assert "--variable X:1" in cmd
        assert cmd.endswith(" suite/folder/")


# ---------------------------------------------------------------------------
# prepare — image-resolution path
# ---------------------------------------------------------------------------


class TestPrepare:
    def _make_runner_with_client(self, client):
        runner = DockerRunner(image="custom/image:tag")
        runner._client = client
        return runner

    def test_image_already_local_skips_pull(self):
        client = MagicMock()
        # `images.get` succeeds → no pull needed.
        runner = self._make_runner_with_client(client)
        runner.prepare("/repo", "suite.robot")
        client.images.get.assert_called_once_with("custom/image:tag")
        client.images.pull.assert_not_called()

    def test_image_missing_triggers_pull(self):
        client = MagicMock()
        client.images.get.side_effect = Exception("ImageNotFound")
        runner = self._make_runner_with_client(client)
        runner.prepare("/repo", "suite.robot")
        client.images.pull.assert_called_once_with("custom/image:tag")

    def test_pull_failure_raises_typed_error(self):
        client = MagicMock()
        client.images.get.side_effect = Exception("ImageNotFound")
        client.images.pull.side_effect = Exception("registry unreachable")
        runner = self._make_runner_with_client(client)
        with pytest.raises(DockerImageNotFoundError) as exc_info:
            runner.prepare("/repo", "suite.robot")
        assert "custom/image:tag" in str(exc_info.value)

    def test_env_config_overrides_image(self):
        client = MagicMock()
        runner = self._make_runner_with_client(client)
        runner.prepare(
            "/repo", "suite.robot",
            env_config={"docker_image": "other/img:1.0"},
        )
        # The override is sticky: subsequent runs use the overridden image.
        assert runner.image == "other/img:1.0"
        client.images.get.assert_called_once_with("other/img:1.0")


# ---------------------------------------------------------------------------
# execute — control-flow paths around the docker container
# ---------------------------------------------------------------------------


class TestExecute:
    def _make_container(self, *, exit_code: int = 0, log_chunks=None):
        container = MagicMock()
        container.logs.return_value = iter(log_chunks or [b"line one\n", b"line two\n"])
        container.wait.return_value = {"StatusCode": exit_code}
        return container

    def _make_client(self, container):
        client = MagicMock()
        client.containers.run.return_value = container
        return client

    def test_success_path_returns_runresult(self, tmp_path):
        container = self._make_container(exit_code=0)
        client = self._make_client(container)
        # Pre-create the expected output files so RunResult fields populate.
        out = tmp_path / "out"
        out.mkdir()
        (out / "output.xml").write_text("<robot/>", encoding="utf-8")
        (out / "log.html").write_text("<html>", encoding="utf-8")
        (out / "report.html").write_text("<html>", encoding="utf-8")

        runner = DockerRunner(image="img:1")
        runner._client = client

        result = runner.execute(
            repo_path="/repo", target_path="suite.robot", output_dir=str(out),
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.output_xml_path.endswith("output.xml")
        assert result.log_html_path.endswith("log.html")
        assert result.report_html_path.endswith("report.html")
        assert "line one" in result.stdout

    def test_nonzero_exit_marks_failure(self, tmp_path):
        container = self._make_container(exit_code=42)
        client = self._make_client(container)
        out = tmp_path / "out"
        runner = DockerRunner(image="img:1")
        runner._client = client

        result = runner.execute(
            repo_path="/repo", target_path="suite.robot", output_dir=str(out),
        )
        assert result.success is False
        assert result.exit_code == 42

    def test_container_run_failure_returns_failure_runresult(self, tmp_path):
        client = MagicMock()
        client.containers.run.side_effect = Exception("daemon refused")
        runner = DockerRunner(image="img:1")
        runner._client = client

        result = runner.execute(
            repo_path="/repo", target_path="x", output_dir=str(tmp_path / "out"),
        )
        assert result.success is False
        assert result.exit_code == -1
        assert "daemon refused" in result.error_message

    def test_on_output_callback_receives_lines(self, tmp_path):
        container = self._make_container(
            exit_code=0,
            log_chunks=[b"first line\nsecond line\n", b"third line\n"],
        )
        client = self._make_client(container)
        runner = DockerRunner(image="img:1")
        runner._client = client

        captured: list[str] = []
        runner.execute(
            repo_path="/repo", target_path="x", output_dir=str(tmp_path / "out"),
            on_output=captured.append,
        )
        assert captured == ["first line", "second line", "third line"]

    def test_listeners_param_logs_warning_but_does_not_break(self, tmp_path, caplog):
        import logging

        container = self._make_container(exit_code=0)
        client = self._make_client(container)
        runner = DockerRunner(image="img:1")
        runner._client = client

        with caplog.at_level(logging.WARNING, logger="roboscope.execution.docker"):
            runner.execute(
                repo_path="/repo", target_path="x",
                output_dir=str(tmp_path / "out"),
                listeners=["my.listener.A", "my.listener.B"],
            )
        # The runner ignores listeners but logs a warning naming the count.
        assert any(
            "ignoring 2 listener" in rec.getMessage()
            for rec in caplog.records
        )

    def test_cancel_breaks_log_loop(self, tmp_path):
        # Container yields many log chunks; we set _cancelled mid-loop
        # (by patching the iterator's __next__ side-effect).
        container = MagicMock()

        # Generator that flips _cancelled after the first yield.
        def gen():
            yield b"first\n"
            runner._cancelled = True   # noqa: F821 — closure binds below
            yield b"never-seen\n"
        container.logs.return_value = gen()
        container.wait.return_value = {"StatusCode": 0}
        client = MagicMock()
        client.containers.run.return_value = container

        runner = DockerRunner(image="img:1")
        runner._client = client

        result = runner.execute(
            repo_path="/repo", target_path="x", output_dir=str(tmp_path / "out"),
        )
        # `wait` still ran; runner exited the streaming loop early.
        assert "first" in result.stdout
        assert "never-seen" not in result.stdout


# ---------------------------------------------------------------------------
# cancel + cleanup — defensive paths
# ---------------------------------------------------------------------------


class TestCancelAndCleanup:
    def test_cancel_no_container_just_sets_flag(self):
        runner = DockerRunner(image="img:1")
        runner.cancel()
        assert runner._cancelled is True

    def test_cancel_with_container_stops_first(self):
        runner = DockerRunner(image="img:1")
        c = MagicMock()
        runner._container = c
        runner.cancel()
        c.stop.assert_called_once_with(timeout=10)
        c.kill.assert_not_called()

    def test_cancel_falls_back_to_kill_when_stop_fails(self):
        runner = DockerRunner(image="img:1")
        c = MagicMock()
        c.stop.side_effect = Exception("docker daemon hung")
        runner._container = c
        runner.cancel()
        c.kill.assert_called_once()

    def test_cancel_swallows_kill_failure(self):
        runner = DockerRunner(image="img:1")
        c = MagicMock()
        c.stop.side_effect = Exception("hung")
        c.kill.side_effect = Exception("also hung")
        runner._container = c
        runner.cancel()  # must not raise

    def test_cleanup_removes_container_force_true(self):
        runner = DockerRunner(image="img:1")
        c = MagicMock()
        runner._container = c
        runner.cleanup()
        c.remove.assert_called_once_with(force=True)
        assert runner._container is None

    def test_cleanup_idempotent_no_container(self):
        runner = DockerRunner(image="img:1")
        runner.cleanup()  # must not raise
        assert runner._container is None

    def test_cleanup_swallows_remove_failure(self):
        runner = DockerRunner(image="img:1")
        c = MagicMock()
        c.remove.side_effect = Exception("container already gone")
        runner._container = c
        runner.cleanup()  # must not raise
        assert runner._container is None
