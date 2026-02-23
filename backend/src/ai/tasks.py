"""Background tasks for AI generation and reverse-engineering."""

import asyncio
import logging
from datetime import datetime, timezone

import yaml
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import settings

import src.auth.models  # noqa: F401 — FK resolution
import src.repos.models  # noqa: F401 — FK resolution

from src.ai.llm_client import call_llm
from src.ai.models import AiJob, AiProvider
from src.ai.prompts import (
    SYSTEM_PROMPT_ANALYZE,
    SYSTEM_PROMPT_GENERATE,
    SYSTEM_PROMPT_REVERSE,
    build_analyze_user_prompt,
    build_reverse_user_prompt,
    enrich_generate_prompt,
)
from src.repos.models import Repository
from src.reports.models import Report, TestResult

logger = logging.getLogger("roboscope.ai.tasks")

_sync_url = settings.sync_database_url
_sync_engine = create_engine(_sync_url)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def _run_async(coro):
    """Run an async coroutine from a sync context (background thread)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in a thread with a running loop — create a new one
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _gather_rf_knowledge(spec_content: str) -> tuple[list[dict], list[str]]:
    """Gather keyword docs and library recommendations from rf-mcp.

    Returns (keyword_docs, library_recommendations). Both empty if rf-mcp unavailable.
    """
    from src.ai import rf_knowledge

    if not rf_knowledge.is_available():
        return [], []

    keyword_docs: list[dict] = []
    library_recs: list[str] = []

    try:
        spec = yaml.safe_load(spec_content)
        if not isinstance(spec, dict):
            return [], []

        # Extract libraries and step text for keyword search
        metadata = spec.get("metadata", {})
        libraries = metadata.get("libraries", [])
        description = metadata.get("title", "")

        # Gather steps from all test cases
        all_steps: list[str] = []
        for ts in spec.get("test_sets", []):
            for tc in ts.get("test_cases", []):
                for step in tc.get("steps", []):
                    if isinstance(step, str):
                        all_steps.append(step)
                    elif isinstance(step, dict):
                        all_steps.append(step.get("action", ""))

        # Search keywords based on first few steps
        search_terms = all_steps[:5]
        for term in search_terms:
            results = await rf_knowledge.search_keywords(term)
            keyword_docs.extend(results[:3])  # Limit per search

        # Deduplicate keyword_docs by name
        seen = set()
        unique_docs = []
        for kw in keyword_docs:
            name = kw.get("name", "")
            if name not in seen:
                seen.add(name)
                unique_docs.append(kw)
        keyword_docs = unique_docs[:15]  # Cap total

        # Get library recommendations
        if description or all_steps:
            rec_text = description
            if all_steps:
                rec_text += "\nSteps: " + "; ".join(all_steps[:10])
            library_recs = await rf_knowledge.recommend_libraries(rec_text)

    except Exception:
        logger.debug("rf-mcp enrichment failed, continuing without it", exc_info=True)

    return keyword_docs, library_recs


async def _gather_reverse_knowledge(robot_content: str) -> list[dict]:
    """Gather keyword docs for reverse-engineering enrichment."""
    from src.ai import rf_knowledge

    if not rf_knowledge.is_available():
        return []

    keyword_docs: list[dict] = []
    try:
        # Extract keyword names from robot content (basic parsing)
        keywords: list[str] = []
        for line in robot_content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("***"):
                # Lines that start with spaces are keyword calls
                if line.startswith("    ") and stripped:
                    # First word/phrase before spaces is often the keyword
                    parts = stripped.split("    ")
                    if parts:
                        keywords.append(parts[0].strip())

        # Search for up to 5 unique keywords
        seen = set()
        for kw in keywords[:10]:
            if kw in seen or not kw:
                continue
            seen.add(kw)
            doc = await rf_knowledge.get_keyword_docs(kw)
            if doc:
                keyword_docs.append({"name": kw, "doc": doc})
            if len(keyword_docs) >= 5:
                break

    except Exception:
        logger.debug("rf-mcp reverse enrichment failed", exc_info=True)

    return keyword_docs


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
                spec = yaml.safe_load(spec_content)
                target = spec.get("metadata", {}).get("target_file")
                if target:
                    job.target_path = target
                    target_file = repo_path / target
                    if target_file.exists():
                        existing_robot = target_file.read_text(encoding="utf-8")

            # Gather rf-mcp enrichment (optional)
            keyword_docs, library_recs = _run_async(
                _gather_rf_knowledge(spec_content)
            )

            user_prompt = enrich_generate_prompt(
                spec_content, existing_robot, keyword_docs, library_recs
            )
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

            # Gather rf-mcp keyword docs for better natural-language step generation
            keyword_docs = _run_async(_gather_reverse_knowledge(robot_content))

            user_prompt = build_reverse_user_prompt(robot_content)

            # Append keyword docs if available
            if keyword_docs:
                docs_text = "\n".join(
                    f"- {kw.get('name', '')}: {kw.get('doc', '')}" for kw in keyword_docs
                )
                user_prompt += (
                    "\n\n--- RF Keyword Documentation (via rf-mcp by Many Kasiriha) ---\n\n"
                    + docs_text
                )

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


async def _gather_analysis_knowledge(failed_tests: list[dict]) -> list[dict]:
    """Gather keyword docs from rf-mcp for failed test error messages.

    Extracts keyword names mentioned in error messages and searches for their
    documentation to help the LLM provide better fix suggestions.
    """
    import re
    from src.ai import rf_knowledge

    if not rf_knowledge.is_available():
        return []

    keyword_docs: list[dict] = []
    try:
        # Extract keyword names from error messages
        search_terms: set[str] = set()
        for test in failed_tests:
            error = test.get("error_message") or ""
            # "No keyword with name 'Xyz' found."
            for match in re.findall(r"No keyword with name '([^']+)'", error):
                search_terms.add(match)
            # "Keyword 'Xyz' expected N arguments"
            for match in re.findall(r"Keyword '([^']+)'", error):
                search_terms.add(match)
            # Also search for the test name itself (might match a keyword)
            name = test.get("name", "")
            if name and len(name.split()) <= 5:
                search_terms.add(name)

        # Search rf-mcp for each term
        seen: set[str] = set()
        for term in list(search_terms)[:8]:
            if term in seen:
                continue
            seen.add(term)
            results = await rf_knowledge.search_keywords(term)
            for r in results[:2]:
                kw_name = r.get("name", "")
                if kw_name and kw_name not in seen:
                    seen.add(kw_name)
                    keyword_docs.append({
                        "name": kw_name,
                        "library": r.get("library", "?"),
                        "doc": r.get("doc", "No documentation"),
                    })
            if len(keyword_docs) >= 10:
                break

    except Exception:
        logger.debug("rf-mcp analysis enrichment failed", exc_info=True)

    return keyword_docs


def run_analyze(job_id: int) -> None:
    """Background task: analyze test failures in a report."""
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

            report = session.execute(
                select(Report).where(Report.id == job.report_id)
            ).scalar_one()

            failed_results = list(
                session.execute(
                    select(TestResult)
                    .where(TestResult.report_id == report.id)
                    .where(TestResult.status == "FAIL")
                ).scalars().all()
            )

            if not failed_results:
                job.result_preview = "No failed tests found in this report."
                job.token_usage = 0
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
                return

            total = report.total_tests
            passed = report.passed_tests
            report_summary = {
                "total_tests": total,
                "passed": passed,
                "failed": report.failed_tests,
                "skipped": report.skipped_tests,
                "duration": report.total_duration_seconds,
                "pass_rate": (passed / total * 100) if total > 0 else 0.0,
            }

            failed_tests = [
                {
                    "name": tr.test_name,
                    "suite": tr.suite_name,
                    "error_message": tr.error_message,
                    "tags": tr.tags,
                    "duration": tr.duration_seconds,
                }
                for tr in failed_results
            ]

            user_prompt = build_analyze_user_prompt(report_summary, failed_tests)

            # Enrich with rf-mcp keyword docs if available
            keyword_docs = _run_async(_gather_analysis_knowledge(failed_tests))
            if keyword_docs:
                docs_text = "\n".join(
                    f"- **{kw['name']}**: {kw['doc']}" for kw in keyword_docs
                )
                user_prompt += (
                    "\n\n--- RF Keyword Documentation (via rf-mcp by Many Kasiriha) ---\n\n"
                    "Use this documentation to provide more accurate fix suggestions:\n\n"
                    + docs_text
                )

            result = call_llm(provider, SYSTEM_PROMPT_ANALYZE, user_prompt)

            job.result_preview = result.content
            job.token_usage = result.tokens_used
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            session.commit()

            logger.info("Analyze job %d completed (%d tokens)", job_id, result.tokens_used)

        except Exception as e:
            logger.exception("Analyze job %d failed", job_id)
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
