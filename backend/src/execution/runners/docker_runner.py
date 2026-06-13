"""Docker-based test runner for isolated execution."""

import logging
import time
from collections.abc import Callable
from pathlib import Path

from src.config import settings
from src.docker_client import (
    DockerNotAvailableError,  # re-exported for backwards-compat callers
    get_docker_client,
)
from src.execution.runners.base import AbstractRunner, RunResult

logger = logging.getLogger("roboscope.execution.docker")

# Backwards-compat: existing imports
# `from src.execution.runners.docker_runner import DockerNotAvailableError`
# keep working — the symbol lives in `src.docker_client` now (REFACTOR-1).
__all__ = ["DockerNotAvailableError", "DockerImageNotFoundError", "DockerRunner"]


class DockerImageNotFoundError(RuntimeError):
    """Raised when the Docker image does not exist locally or in any registry."""

    def __init__(self, image: str) -> None:
        super().__init__(f"DOCKER_IMAGE_NOT_FOUND:{image}")


class DockerRunner(AbstractRunner):
    """Runs Robot Framework tests inside a Docker container."""

    def __init__(self, image: str | None = None):
        self.image = image or settings.DOCKER_DEFAULT_IMAGE
        self._container = None
        self._client = None
        self._cancelled = False

    def _get_client(self):
        """Lazy-load Docker client. Caches across calls on the same runner instance.

        Story REFACTOR-1: bootstrap logic was moved to `src.docker_client`
        — this is now a thin caching wrapper.
        """
        if self._client is None:
            self._client = get_docker_client()
        return self._client

    def prepare(self, repo_path: str, target_path: str, env_config: dict | None = None) -> None:
        """Pull the Docker image if not available locally."""
        client = self._get_client()

        image = self.image
        if env_config and env_config.get("docker_image"):
            image = env_config["docker_image"]
            self.image = image

        try:
            client.images.get(image)
        except Exception:
            try:
                client.images.pull(image)
            except Exception:
                raise DockerImageNotFoundError(image)

    def execute(
        self,
        repo_path: str,
        target_path: str,
        output_dir: str,
        variables: dict | None = None,
        tags_include: str | None = None,
        tags_exclude: str | None = None,
        timeout: int = 3600,
        on_output: Callable[[str], None] | None = None,
        listeners: list[str] | None = None,
    ) -> RunResult:
        """Execute Robot Framework tests in a Docker container.

        `listeners` is accepted for runner-interface parity with
        SubprocessRunner (Story FLAKY-2) but silently dropped in the
        Docker path: the quarantine-skip listener module lives in the
        host-side `src/execution/runners/` package, which isn't
        reachable from inside the test container. Mounting the listener
        file + propagating it is tracked as follow-up FLAKY-3.
        """
        start_time = time.time()

        # C1: honor a cancel that arrived during prepare()/sync (runner is
        # registered before prepare runs). Do NOT reset `_cancelled` here —
        # resetting it erased the cancel and ran the container anyway.
        if self._cancelled:
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                cancelled=True,
                error_message="Run cancelled before execution started",
                duration_seconds=time.time() - start_time,
            )
        client = self._get_client()

        if listeners:
            logger.warning(
                "DockerRunner ignoring %d listener(s) — quarantine-skip "
                "filtering is not yet wired for the Docker runner "
                "(Story FLAKY-3 follow-up).",
                len(listeners),
            )

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Build robot command
        cmd = self._build_robot_command(
            target_path=target_path,
            variables=variables,
            tags_include=tags_include,
            tags_exclude=tags_exclude,
        )

        # Environment variables
        env_vars = {}
        if variables:
            env_vars.update({f"ROBOT_{k}": str(v) for k, v in variables.items()})

        stdout_lines: list[str] = []
        try:
            # Create and start container
            self._container = client.containers.run(
                image=self.image,
                command=cmd,
                volumes={
                    repo_path: {"bind": "/workspace", "mode": "ro"},
                    output_dir: {"bind": "/output", "mode": "rw"},
                },
                working_dir="/workspace",
                environment=env_vars,
                detach=True,
                mem_limit="2g",
                cpu_period=100000,
                cpu_quota=200000,  # 2 CPUs
            )

            # Stream logs. M3: decode INCREMENTALLY and split on real line
            # boundaries — decoding each raw chunk independently corrupts
            # multibyte UTF-8 (accented DE/FR/ES test names) when a character
            # straddles a chunk boundary, and emits partial lines to on_output.
            import codecs

            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            line_buf = ""
            for log_chunk in self._container.logs(stream=True, follow=True):
                if self._cancelled:
                    break
                text = decoder.decode(log_chunk)
                if not text:
                    continue
                stdout_lines.append(text)
                line_buf += text
                while "\n" in line_buf:
                    complete, line_buf = line_buf.split("\n", 1)
                    if on_output:
                        on_output(complete)
            # Flush any trailing partial line + decoder state at stream end.
            line_buf += decoder.decode(b"", final=True)
            if line_buf and on_output:
                on_output(line_buf)

            # Wait for completion
            result = self._container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)
            duration = time.time() - start_time

            # Check output files
            output_xml = str(Path(output_dir) / "output.xml")
            log_html = str(Path(output_dir) / "log.html")
            report_html = str(Path(output_dir) / "report.html")

            return RunResult(
                success=exit_code == 0,
                exit_code=exit_code,
                output_dir=output_dir,
                output_xml_path=output_xml if Path(output_xml).exists() else "",
                log_html_path=log_html if Path(log_html).exists() else "",
                report_html_path=report_html if Path(report_html).exists() else "",
                stdout="".join(stdout_lines),
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            # H1/H2: docker's wait(timeout=) / log-stream read timeout raises a
            # Timeout-named exception but does NOT stop the container. Detect it
            # by exception type (not message), best-effort stop the container so
            # we don't leak compute, and flag the result as a timeout.
            timed_out = self._is_timeout_error(e)
            if timed_out:
                try:
                    self.cancel()
                except Exception:
                    logger.warning("failed to stop timed-out container", exc_info=True)
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                timed_out=timed_out,
                stdout="".join(stdout_lines),
                error_message=(
                    f"Timeout after {timeout} seconds" if timed_out else str(e)
                ),
                duration_seconds=duration,
            )

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        """True for docker/requests read/connect timeouts. Type-name based
        (not message-sniffing) — docker-py surfaces `requests` Timeout
        subclasses whose class names end in 'Timeout'."""
        return type(exc).__name__ in {"ReadTimeout", "Timeout", "ConnectTimeout"}

    def cancel(self) -> None:
        """Stop the running container."""
        self._cancelled = True
        if self._container:
            try:
                self._container.stop(timeout=10)
            except Exception:
                try:
                    self._container.kill()
                except Exception:
                    pass

    def cleanup(self) -> None:
        """Remove the container."""
        if self._container:
            try:
                self._container.remove(force=True)
            except Exception:
                pass
            self._container = None

    def _build_robot_command(
        self,
        target_path: str,
        variables: dict | None = None,
        tags_include: str | None = None,
        tags_exclude: str | None = None,
    ) -> str:
        """Build the robot command for Docker execution."""
        parts = [
            "python", "-m", "robot",
            "--outputdir", "/output",
            "--loglevel", "INFO",
            "--consolecolors", "off",
        ]

        if tags_include:
            for tag in tags_include.split(","):
                tag = tag.strip()
                if tag:
                    parts.extend(["--include", tag])

        if tags_exclude:
            for tag in tags_exclude.split(","):
                tag = tag.strip()
                if tag:
                    parts.extend(["--exclude", tag])

        if variables:
            for key, value in variables.items():
                parts.extend(["--variable", f"{key}:{value}"])

        parts.append(target_path)
        return " ".join(parts)
