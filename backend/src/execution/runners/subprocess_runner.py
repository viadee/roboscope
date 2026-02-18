"""Subprocess-based test runner using virtualenv."""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from src.config import settings
from src.execution.runners.base import AbstractRunner, RunResult


class SubprocessRunner(AbstractRunner):
    """Runs Robot Framework tests in a local subprocess with optional virtualenv."""

    def __init__(self, venv_path: str | None = None):
        self.venv_path = venv_path
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def prepare(self, repo_path: str, target_path: str, env_config: dict | None = None) -> None:
        """Prepare virtualenv if specified."""
        if self.venv_path and not Path(self.venv_path).exists():
            python = env_config.get("python_version", "python3") if env_config else "python3"
            subprocess.run(
                [sys.executable, "-m", "venv", self.venv_path],
                check=True,
                capture_output=True,
            )

            # Install packages if specified
            if env_config and env_config.get("packages"):
                pip_path = self._get_pip_path()
                for package in env_config["packages"]:
                    subprocess.run(
                        [pip_path, "install", package],
                        check=True,
                        capture_output=True,
                    )

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
        """Execute Robot Framework tests via subprocess."""
        self._cancelled = False
        start_time = time.time()

        # Build robot command
        cmd = self._build_command(
            repo_path=repo_path,
            target_path=target_path,
            output_dir=output_dir,
            variables=variables,
            tags_include=tags_include,
            tags_exclude=tags_exclude,
        )

        # Prepare environment
        env = os.environ.copy()
        if self.venv_path:
            venv_bin = str(Path(self.venv_path) / "bin")
            env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = self.venv_path

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=repo_path,
                env=env,
                text=True,
                bufsize=1,
            )

            # Stream stdout
            if self._process.stdout:
                for line in iter(self._process.stdout.readline, ""):
                    if self._cancelled:
                        break
                    stdout_lines.append(line)
                    if on_output:
                        on_output(line.rstrip("\n"))

            self._process.wait(timeout=timeout)

            # Capture stderr
            if self._process.stderr:
                stderr_lines = self._process.stderr.readlines()

            exit_code = self._process.returncode
            duration = time.time() - start_time

            # Determine paths
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
                stderr="".join(stderr_lines),
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            self.cancel()
            duration = time.time() - start_time
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                error_message=f"Timeout after {timeout} seconds",
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                error_message=str(e),
                duration_seconds=duration,
            )

    def cancel(self) -> None:
        """Cancel the running process."""
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.send_signal(signal.SIGTERM)
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def cleanup(self) -> None:
        """Clean up process resources."""
        if self._process:
            self._process = None

    def _build_command(
        self,
        repo_path: str,
        target_path: str,
        output_dir: str,
        variables: dict | None = None,
        tags_include: str | None = None,
        tags_exclude: str | None = None,
    ) -> list[str]:
        """Build the robot command line."""
        python = self._get_python_path() if self.venv_path else sys.executable

        cmd = [
            python, "-m", "robot",
            "--outputdir", output_dir,
            "--loglevel", "INFO",
            "--consolecolors", "off",
        ]

        if tags_include:
            for tag in tags_include.split(","):
                tag = tag.strip()
                if tag:
                    cmd.extend(["--include", tag])

        if tags_exclude:
            for tag in tags_exclude.split(","):
                tag = tag.strip()
                if tag:
                    cmd.extend(["--exclude", tag])

        if variables:
            for key, value in variables.items():
                cmd.extend(["--variable", f"{key}:{value}"])

        cmd.append(target_path)
        return cmd

    def _get_python_path(self) -> str:
        """Get python executable path from venv."""
        if self.venv_path:
            return str(Path(self.venv_path) / "bin" / "python")
        return sys.executable

    def _get_pip_path(self) -> str:
        """Get pip executable path from venv."""
        if self.venv_path:
            return str(Path(self.venv_path) / "bin" / "pip")
        return str(Path(sys.executable).parent / "pip")
