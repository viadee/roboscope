"""Subprocess-based test runner using virtualenv."""

import os
import platform
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from src.config import settings
from src.environments.venv_utils import (
    create_venv_cmd,
    get_python_path,
    get_venv_bin_dir,
    pip_install_cmd,
)
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
            subprocess.run(
                create_venv_cmd(self.venv_path),
                check=True,
                capture_output=True,
            )

            # Install packages if specified
            if env_config and env_config.get("packages"):
                for package in env_config["packages"]:
                    subprocess.run(
                        pip_install_cmd(self.venv_path, package),
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
        listeners: list[str] | None = None,
    ) -> RunResult:
        """Execute Robot Framework tests via subprocess."""
        start_time = time.time()

        # C1: honor a cancel that arrived during prepare()/sync. The runner
        # is registered for cancellation BEFORE prepare() runs, so a cancel
        # during the (often slow) venv-create / pip-install / git-sync window
        # sets `_cancelled` while `_process` is still None. We must NOT reset
        # the flag here — the old `self._cancelled = False` erased that cancel
        # and let the whole suite execute despite the run being CANCELLED.
        if self._cancelled:
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                cancelled=True,
                error_message="Run cancelled before execution started",
                duration_seconds=time.time() - start_time,
            )

        # Build robot command
        cmd = self._build_command(
            repo_path=repo_path,
            target_path=target_path,
            output_dir=output_dir,
            variables=variables,
            tags_include=tags_include,
            tags_exclude=tags_exclude,
            listeners=listeners,
        )

        # Prepare environment
        env = os.environ.copy()
        if self.venv_path:
            venv_bin = get_venv_bin_dir(self.venv_path)
            env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = self.venv_path

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        last_activity = time.time()
        lock = threading.Lock()

        # L1: cap heap (RLIMIT_DATA), NOT virtual address space (RLIMIT_AS).
        # RLIMIT_AS counts mmap'd memory — Chromium/Node reserve >2 GB of
        # *virtual* address space (not resident), so a 2 GB RLIMIT_AS made the
        # headline Browser-library tests fail to even launch with an opaque
        # allocation error. RLIMIT_DATA bounds the brk-based data segment and
        # leaves the browser's mmap reservations alone.
        preexec = None
        if platform.system() != "Windows":
            import resource

            def _set_limits() -> None:
                four_gb = 4 * 1024 * 1024 * 1024
                try:
                    resource.setrlimit(resource.RLIMIT_DATA, (four_gb, four_gb))
                except (ValueError, OSError):
                    pass  # best-effort; some systems don't support RLIMIT_DATA

            preexec = _set_limits

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=repo_path,
                env=env,
                text=True,
                bufsize=1,
                preexec_fn=preexec,
            )

            # Read stdout in a background thread so readline() can't block timeouts
            def _read_stdout() -> None:
                nonlocal last_activity
                if self._process and self._process.stdout:
                    for line in iter(self._process.stdout.readline, ""):
                        if self._cancelled:
                            break
                        with lock:
                            stdout_lines.append(line)
                            last_activity = time.time()
                        if on_output:
                            on_output(line.rstrip("\n"))

            reader = threading.Thread(target=_read_stdout, daemon=True)
            reader.start()

            # C2: drain stderr concurrently in its own thread. Reading stderr
            # only AFTER process.wait() deadlocks any run that writes more than
            # the OS pipe buffer (~64 KB) to stderr — common with deprecation
            # warnings, Browser-library Node stderr, or stack-trace-heavy
            # failures — because the child blocks on the full stderr pipe and
            # never exits, which the poll loop then mis-reports as a hang.
            def _read_stderr() -> None:
                if self._process and self._process.stderr:
                    for line in iter(self._process.stderr.readline, ""):
                        with lock:
                            stderr_lines.append(line)

            stderr_reader = threading.Thread(target=_read_stderr, daemon=True)
            stderr_reader.start()

            # Poll with total timeout + inactivity timeout
            INACTIVITY_TIMEOUT = 120
            deadline = start_time + timeout
            while True:
                reader.join(timeout=5)
                if not reader.is_alive():
                    break
                now = time.time()
                if now > deadline:
                    raise subprocess.TimeoutExpired(cmd, timeout)
                with lock:
                    idle = now - last_activity
                if idle > INACTIVITY_TIMEOUT and self._process.poll() is None:
                    self.cancel()
                    reader.join(timeout=10)
                    stderr_reader.join(timeout=10)
                    duration = time.time() - start_time
                    with lock:
                        captured_err = "".join(stderr_lines)
                    return RunResult(
                        success=False,
                        exit_code=-1,
                        output_dir=output_dir,
                        timed_out=True,
                        stdout="".join(stdout_lines),
                        stderr=captured_err,
                        error_message=(
                            f"No output for {INACTIVITY_TIMEOUT} seconds — process appears"
                            " hung. This often happens when the Browser library cannot"
                            " connect to Playwright."
                        ),
                        duration_seconds=duration,
                    )

            self._process.wait(timeout=30)

            # stderr was drained concurrently by stderr_reader (C2); just
            # wait for it to flush the last lines after the process exits.
            stderr_reader.join(timeout=10)

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
            with lock:
                captured_err = "".join(stderr_lines)
            return RunResult(
                success=False,
                exit_code=-1,
                output_dir=output_dir,
                timed_out=True,
                stdout="".join(stdout_lines),
                stderr=captured_err,
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
        listeners: list[str] | None = None,
    ) -> list[str]:
        """Build the robot command line."""
        python = get_python_path(self.venv_path) if self.venv_path else sys.executable

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

        if listeners:
            for spec in listeners:
                spec = spec.strip()
                if spec:
                    cmd.extend(["--listener", spec])

        if variables:
            for key, value in variables.items():
                cmd.extend(["--variable", f"{key}:{value}"])

        cmd.append(target_path)
        return cmd
