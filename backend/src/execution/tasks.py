"""Background tasks for test execution."""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

# Import all models so SQLAlchemy can resolve foreign keys.
import src.auth.models  # noqa: F401
import src.repos.models  # noqa: F401

from src.config import settings
from src.database import get_sync_session
from src.environments.tasks import _is_browser_package
from src.environments.venv_utils import check_rfbrowser_initialized
from src.execution.models import ExecutionRun, RunStatus, RunnerType
from src.execution.runners.subprocess_runner import SubprocessRunner
from src.environments.models import Environment, EnvironmentPackage

logger = logging.getLogger("roboscope.execution.tasks")

# Registry of currently running runners, keyed by run_id.
# Allows cancel_run() to actually kill the spawned process.
_active_runners: dict[int, "AbstractRunner"] = {}  # type: ignore[name-defined]
_active_runners_lock = threading.Lock()

_PLAYWRIGHT_HINTS = [
    "could not connect to the playwright process",
    "playwright process",
    "browser library requires",
    "browser library cannot connect",
    "rfbrowser",
    "calling method '_end_test' of listener 'browser' failed",
    "calling method '_end_suite' of listener 'browser' failed",
    "econnrefused",
]


def _enrich_error_with_hints(
    error_msg: str,
    combined_output: str,
    runner_type: str,
) -> str:
    """Append actionable hints when Browser/Playwright errors are detected."""
    lower = (error_msg + " " + combined_output).lower()
    if not any(hint in lower for hint in _PLAYWRIGHT_HINTS):
        return error_msg

    hints = [error_msg] if error_msg else []
    hints.append(
        "Hint: The Browser library's Playwright process could not be reached. "
        "Ensure Node.js 18+ is installed and 'rfbrowser init' has been run in the environment."
    )
    if runner_type == RunnerType.DOCKER:
        hints.append(
            "Docker: Your Docker image may be missing Node.js or browser binaries. "
            "Rebuild the image in Package Manager to include the required dependencies."
        )
    return " | ".join(hints)


def _broadcast_run_status(run_id: int, status: str) -> None:
    """Broadcast a run status change from a sync background thread."""
    from src.websocket.manager import ws_manager
    from src.main import _event_loop

    coro = ws_manager.broadcast_run_status(run_id, status)

    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    else:
        logger.warning("No event loop available to broadcast run %d status", run_id)


def cancel_active_run(run_id: int) -> bool:
    """Cancel the runner for a currently executing run.

    Returns True if a runner was found and cancelled, False otherwise.
    """
    with _active_runners_lock:
        runner = _active_runners.get(run_id)
    if runner is not None:
        logger.info("Cancelling active runner for run %d", run_id)
        runner.cancel()
        return True
    return False


def _get_runner(runner_type: str, env_config: dict | None = None):
    """Factory function to get the appropriate runner."""
    if runner_type == RunnerType.DOCKER:
        from src.execution.runners.docker_runner import DockerRunner
        image = env_config.get("docker_image") if env_config else None
        return DockerRunner(image=image)
    else:
        venv_path = env_config.get("venv_path") if env_config else None
        return SubprocessRunner(venv_path=venv_path)


def _get_env_config(session: Session, env_id: int | None) -> dict | None:
    """Load environment configuration."""
    if env_id is None:
        return None
    env = session.execute(
        select(Environment).where(Environment.id == env_id)
    ).scalar_one_or_none()
    if env is None:
        return None
    # Load installed packages so SubprocessRunner can bootstrap a new venv
    packages = session.execute(
        select(EnvironmentPackage)
        .where(EnvironmentPackage.environment_id == env_id)
        .where(EnvironmentPackage.install_status == "installed")
    ).scalars().all()
    pkg_specs = []
    for p in packages:
        if p.installed_version:
            pkg_specs.append(f"{p.package_name}=={p.installed_version}")
        elif p.version:
            pkg_specs.append(f"{p.package_name}=={p.version}")
        else:
            pkg_specs.append(p.package_name)

    return {
        "name": env.name,
        "python_version": env.python_version,
        "venv_path": env.venv_path,
        "docker_image": env.docker_image,
        "default_runner_type": env.default_runner_type,
        "packages": pkg_specs,
    }


def execute_test_run(run_id: int) -> dict:
    """Execute a test run in a background thread."""
    with get_sync_session() as session:
        run = session.execute(
            select(ExecutionRun).where(ExecutionRun.id == run_id)
        ).scalar_one_or_none()

        if run is None:
            logger.error("Run %d not found", run_id)
            return {"status": "error", "message": "Run not found"}

        # Update status to RUNNING
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        session.commit()
        _broadcast_run_status(run_id, RunStatus.RUNNING)

        # Prepare output directory
        output_dir = str(
            Path(settings.REPORTS_DIR) / f"run_{run.id}_{uuid.uuid4().hex[:8]}"
        )
        run.output_dir = output_dir
        session.commit()

        # Get environment config
        env_config = _get_env_config(session, run.environment_id)

        if run.environment_id and env_config is None:
            run.status = RunStatus.ERROR
            run.error_message = (
                f"Environment #{run.environment_id} no longer exists. "
                "Please retry with a valid environment."
            )
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
            _broadcast_run_status(run_id, RunStatus.ERROR)
            return {"status": "error", "message": run.error_message}

        # Determine effective runner type: use env default if run still has subprocess default
        effective_runner_type = run.runner_type
        if (env_config
                and env_config.get("default_runner_type") == RunnerType.DOCKER
                and run.runner_type == RunnerType.SUBPROCESS):
            effective_runner_type = RunnerType.DOCKER

        # Fail early if Docker runner requested but no Docker image configured
        if (effective_runner_type == RunnerType.DOCKER
                and (not env_config or not env_config.get("docker_image"))):
            env_name = env_config.get("name", f"#{run.environment_id}") if env_config else "None"
            run.status = RunStatus.ERROR
            run.error_message = (
                f"Runner type is Docker but environment \"{env_name}\" has no Docker image. "
                "Build a Docker image in Package Manager first, or switch to Subprocess runner."
            )
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
            _broadcast_run_status(run_id, RunStatus.ERROR)
            return {"status": "error", "message": run.error_message}

        # Pre-run check: verify rfbrowser init if Browser library is installed
        if (effective_runner_type == RunnerType.SUBPROCESS
                and env_config and env_config.get("venv_path")):
            has_browser = any(
                _is_browser_package(p.split("==")[0])
                for p in (env_config.get("packages") or [])
            )
            if has_browser and not check_rfbrowser_initialized(env_config["venv_path"]):
                run.status = RunStatus.ERROR
                run.error_message = (
                    "robotframework-browser is installed but not initialized. "
                    "The Browser library requires 'rfbrowser init' to download "
                    "Playwright browsers and Node.js dependencies. "
                    "Go to Package Manager, remove and re-install the package, "
                    "or ensure Node.js 18+ is installed and run 'rfbrowser init' "
                    "manually in the environment's venv."
                )
                run.finished_at = datetime.now(timezone.utc)
                session.commit()
                _broadcast_run_status(run_id, RunStatus.ERROR)
                return {"status": "error", "message": run.error_message}

        # Get runner
        runner = _get_runner(effective_runner_type, env_config)

        # Register runner so cancel_active_run() can kill the process
        with _active_runners_lock:
            _active_runners[run_id] = runner

        try:
            # Prepare runner
            from src.repos.models import Repository
            repo = session.execute(
                select(Repository).where(Repository.id == run.repository_id)
            ).scalar_one_or_none()

            if repo is None:
                run.status = RunStatus.ERROR
                run.error_message = "Repository not found"
                run.finished_at = datetime.now(timezone.utc)
                session.commit()
                _broadcast_run_status(run_id, RunStatus.ERROR)
                return {"status": "error", "message": "Repository not found"}

            runner.prepare(repo.local_path, run.target_path, env_config)

            # Parse variables
            variables = json.loads(run.variables) if run.variables else None

            # Execute
            result = runner.execute(
                repo_path=repo.local_path,
                target_path=run.target_path,
                output_dir=output_dir,
                variables=variables,
                tags_include=run.tags_include,
                tags_exclude=run.tags_exclude,
                timeout=run.timeout_seconds,
            )

            # Re-read run status — it may have been set to CANCELLED while we were executing
            session.refresh(run)
            if run.status == RunStatus.CANCELLED:
                logger.info("Run %d was cancelled during execution", run_id)
                run.finished_at = datetime.now(timezone.utc)
                run.duration_seconds = result.duration_seconds
                session.commit()
                return {"status": "cancelled", "run_id": run.id}

            # Update run with results
            run.duration_seconds = result.duration_seconds
            run.finished_at = datetime.now(timezone.utc)

            if result.success:
                run.status = RunStatus.PASSED
            elif result.error_message and "timeout" in result.error_message.lower():
                run.status = RunStatus.TIMEOUT
                run.error_message = result.error_message
            else:
                run.status = RunStatus.FAILED
                raw_error = result.error_message or (
                    result.stderr[:1000] if result.stderr else None
                )
                combined = (result.stdout or "") + (result.stderr or "")
                run.error_message = _enrich_error_with_hints(
                    raw_error or "", combined, effective_runner_type,
                )[:1000]

            session.commit()
            _broadcast_run_status(run_id, run.status)

            # Save stdout/stderr to files in output_dir
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            if result.stdout:
                (out_path / "stdout.log").write_text(result.stdout, encoding="utf-8")
            if result.stderr:
                (out_path / "stderr.log").write_text(result.stderr, encoding="utf-8")

            # Parse report if output.xml exists
            if result.output_xml_path and Path(result.output_xml_path).exists():
                try:
                    from src.reports.tasks import parse_report
                    parse_report(run.id, result.output_xml_path)
                except Exception as report_exc:
                    logger.warning(
                        "Failed to parse report for run %d: %s",
                        run.id, report_exc,
                    )

            return {
                "status": run.status,
                "run_id": run.id,
                "duration": result.duration_seconds,
                "exit_code": result.exit_code,
            }

        except Exception as e:
            logger.exception("Error executing run %d", run.id)
            # Don't overwrite CANCELLED status
            session.refresh(run)
            if run.status != RunStatus.CANCELLED:
                run.status = RunStatus.ERROR
                run.error_message = str(e)[:1000]
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
            _broadcast_run_status(run_id, run.status)
            return {"status": "error", "message": str(e)}

        finally:
            with _active_runners_lock:
                _active_runners.pop(run_id, None)
            runner.cleanup()
