"""Docker-based test runner for isolated execution."""

import time
from collections.abc import Callable
from pathlib import Path

from src.config import settings
from src.execution.runners.base import AbstractRunner, RunResult


class DockerRunner(AbstractRunner):
    """Runs Robot Framework tests inside a Docker container."""

    def __init__(self, image: str | None = None):
        self.image = image or settings.DOCKER_DEFAULT_IMAGE
        self._container = None
        self._client = None
        self._cancelled = False

    def _get_client(self):
        """Lazy-load Docker client."""
        if self._client is None:
            import docker
            self._client = docker.from_env()
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
            client.images.pull(image)

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
    ) -> RunResult:
        """Execute Robot Framework tests in a Docker container."""
        self._cancelled = False
        start_time = time.time()
        client = self._get_client()

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

            # Stream logs
            stdout_lines: list[str] = []
            for log_chunk in self._container.logs(stream=True, follow=True):
                if self._cancelled:
                    break
                line = log_chunk.decode("utf-8", errors="replace")
                stdout_lines.append(line)
                if on_output:
                    for sub_line in line.splitlines():
                        on_output(sub_line)

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
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                error_message=str(e),
                duration_seconds=duration,
            )

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
