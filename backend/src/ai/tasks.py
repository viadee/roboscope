"""Background tasks for AI generation and reverse-engineering."""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401 — FK resolution
import src.repos.models  # noqa: F401 — FK resolution

from src.ai.llm_client import call_llm
from src.ai.models import AiJob, AiProvider
from src.ai.prompts import (
    SYSTEM_PROMPT_GENERATE,
    SYSTEM_PROMPT_REVERSE,
    build_generate_user_prompt,
    build_reverse_user_prompt,
)
from src.repos.models import Repository

logger = logging.getLogger("roboscope.ai.tasks")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def run_generate(job_id: int) -> None:
    """Background task: generate .robot from .roboscope spec."""
    with _get_sync_session() as session:
        job = session.execute(select(AiJob).where(AiJob.id == job_id)).scalar_one_or_none()
        if not job:
            logger.error("Job %d not found", job_id)
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        try:
            provider = session.execute(
                select(AiProvider).where(AiProvider.id == job.provider_id)
            ).scalar_one()
            repo = session.execute(
                select(Repository).where(Repository.id == job.repository_id)
            ).scalar_one()

            from pathlib import Path

            repo_path = Path(repo.local_path)
            spec_file = repo_path / job.spec_path
            spec_content = spec_file.read_text(encoding="utf-8")

            # Read existing .robot file if present (for context)
            existing_robot = None
            if job.target_path:
                target_file = repo_path / job.target_path
                if target_file.exists():
                    existing_robot = target_file.read_text(encoding="utf-8")
            else:
                # Derive target_path from spec metadata
                import yaml

                spec = yaml.safe_load(spec_content)
                target = spec.get("metadata", {}).get("target_file")
                if target:
                    job.target_path = target
                    target_file = repo_path / target
                    if target_file.exists():
                        existing_robot = target_file.read_text(encoding="utf-8")

            user_prompt = build_generate_user_prompt(spec_content, existing_robot)
            result = call_llm(provider, SYSTEM_PROMPT_GENERATE, user_prompt)

            # Strip markdown fences if LLM wrapped them
            content = _strip_code_fences(result.content)

            job.result_preview = content
            job.token_usage = result.tokens_used
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            session.commit()

            logger.info("Generate job %d completed (%d tokens)", job_id, result.tokens_used)

        except Exception as e:
            logger.exception("Generate job %d failed", job_id)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()


def run_reverse(job_id: int) -> None:
    """Background task: extract .roboscope spec from .robot file."""
    with _get_sync_session() as session:
        job = session.execute(select(AiJob).where(AiJob.id == job_id)).scalar_one_or_none()
        if not job:
            logger.error("Job %d not found", job_id)
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()

        try:
            provider = session.execute(
                select(AiProvider).where(AiProvider.id == job.provider_id)
            ).scalar_one()
            repo = session.execute(
                select(Repository).where(Repository.id == job.repository_id)
            ).scalar_one()

            from pathlib import Path

            repo_path = Path(repo.local_path)
            robot_file = repo_path / job.spec_path  # spec_path stores source .robot path
            robot_content = robot_file.read_text(encoding="utf-8")

            user_prompt = build_reverse_user_prompt(robot_content)
            result = call_llm(provider, SYSTEM_PROMPT_REVERSE, user_prompt)

            content = _strip_code_fences(result.content)

            job.result_preview = content
            job.token_usage = result.tokens_used
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            session.commit()

            logger.info("Reverse job %d completed (%d tokens)", job_id, result.tokens_used)

        except Exception as e:
            logger.exception("Reverse job %d failed", job_id)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()


def _strip_code_fences(content: str) -> str:
    """Strip markdown code fences from LLM output if present."""
    lines = content.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
