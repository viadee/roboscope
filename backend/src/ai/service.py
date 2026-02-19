"""AI module business logic — spec parsing, provider CRUD, drift detection."""

import hashlib
import json
import logging
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ai.encryption import encrypt_api_key
from src.ai.models import AiJob, AiProvider
from src.ai.schemas import (
    AiProviderCreate,
    AiProviderUpdate,
    DriftResult,
)

logger = logging.getLogger("roboscope.ai.service")


# ---------------------------------------------------------------------------
# Provider CRUD
# ---------------------------------------------------------------------------


def create_provider(db: Session, data: AiProviderCreate, user_id: int) -> AiProvider:
    """Create a new LLM provider configuration."""
    provider = AiProvider(
        name=data.name,
        provider_type=data.provider_type,
        api_base_url=data.api_base_url,
        api_key_encrypted=encrypt_api_key(data.api_key) if data.api_key else None,
        model_name=data.model_name,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        is_default=data.is_default,
        created_by=user_id,
    )
    # If marked as default, unset other defaults
    if data.is_default:
        _unset_defaults(db)
    db.add(provider)
    db.flush()
    return provider


def update_provider(db: Session, provider_id: int, data: AiProviderUpdate) -> AiProvider | None:
    """Update an existing provider."""
    provider = db.execute(
        select(AiProvider).where(AiProvider.id == provider_id)
    ).scalar_one_or_none()
    if not provider:
        return None

    if data.name is not None:
        provider.name = data.name
    if data.provider_type is not None:
        provider.provider_type = data.provider_type
    if data.api_base_url is not None:
        provider.api_base_url = data.api_base_url
    if data.api_key is not None:
        provider.api_key_encrypted = encrypt_api_key(data.api_key) if data.api_key else None
    if data.model_name is not None:
        provider.model_name = data.model_name
    if data.temperature is not None:
        provider.temperature = data.temperature
    if data.max_tokens is not None:
        provider.max_tokens = data.max_tokens
    if data.is_default is not None:
        if data.is_default:
            _unset_defaults(db)
        provider.is_default = data.is_default

    db.flush()
    return provider


def delete_provider(db: Session, provider_id: int) -> bool:
    """Delete a provider. Returns True if found and deleted."""
    provider = db.execute(
        select(AiProvider).where(AiProvider.id == provider_id)
    ).scalar_one_or_none()
    if not provider:
        return False
    db.delete(provider)
    db.flush()
    return True


def list_providers(db: Session) -> list[AiProvider]:
    """List all providers."""
    return list(db.execute(select(AiProvider).order_by(AiProvider.name)).scalars().all())


def get_provider(db: Session, provider_id: int) -> AiProvider | None:
    """Get a single provider by ID."""
    return db.execute(
        select(AiProvider).where(AiProvider.id == provider_id)
    ).scalar_one_or_none()


def get_default_provider(db: Session) -> AiProvider | None:
    """Get the default provider."""
    return db.execute(
        select(AiProvider).where(AiProvider.is_default.is_(True))
    ).scalar_one_or_none()


def _unset_defaults(db: Session) -> None:
    """Unset is_default on all providers."""
    providers = db.execute(
        select(AiProvider).where(AiProvider.is_default.is_(True))
    ).scalars().all()
    for p in providers:
        p.is_default = False


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


def create_job(
    db: Session,
    job_type: str,
    repository_id: int,
    provider_id: int,
    spec_path: str,
    target_path: str | None,
    user_id: int,
) -> AiJob:
    """Create a new AI job record."""
    job = AiJob(
        job_type=job_type,
        status="pending",
        repository_id=repository_id,
        provider_id=provider_id,
        spec_path=spec_path,
        target_path=target_path,
        triggered_by=user_id,
    )
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: int) -> AiJob | None:
    """Get a job by ID."""
    return db.execute(select(AiJob).where(AiJob.id == job_id)).scalar_one_or_none()


def list_jobs(db: Session, repository_id: int | None = None) -> list[AiJob]:
    """List jobs, optionally filtered by repository."""
    query = select(AiJob).order_by(AiJob.id.desc()).limit(50)
    if repository_id is not None:
        query = query.where(AiJob.repository_id == repository_id)
    return list(db.execute(query).scalars().all())


# ---------------------------------------------------------------------------
# Spec parsing & validation
# ---------------------------------------------------------------------------


def parse_spec(content: str) -> dict:
    """Parse a .roboscope YAML spec and return the dict."""
    return yaml.safe_load(content)


def validate_spec(content: str) -> tuple[bool, list[str], int]:
    """Validate a .roboscope YAML spec.

    Returns (is_valid, error_messages, test_count).
    """
    errors: list[str] = []
    test_count = 0

    try:
        spec = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return False, [f"Invalid YAML: {e}"], 0

    if not isinstance(spec, dict):
        return False, ["Spec must be a YAML mapping"], 0

    if "version" not in spec:
        errors.append("Missing 'version' field")

    metadata = spec.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("Missing or invalid 'metadata' section")
    else:
        if "title" not in metadata:
            errors.append("metadata.title is required")
        if "target_file" not in metadata:
            errors.append("metadata.target_file is required")

    test_sets = spec.get("test_sets")
    if not isinstance(test_sets, list):
        errors.append("Missing or invalid 'test_sets' section (must be a list)")
    else:
        for i, ts in enumerate(test_sets):
            if not isinstance(ts, dict):
                errors.append(f"test_sets[{i}] must be a mapping")
                continue
            if "name" not in ts:
                errors.append(f"test_sets[{i}].name is required")
            cases = ts.get("test_cases")
            if not isinstance(cases, list):
                errors.append(f"test_sets[{i}].test_cases must be a list")
            else:
                for j, tc in enumerate(cases):
                    if not isinstance(tc, dict):
                        errors.append(f"test_sets[{i}].test_cases[{j}] must be a mapping")
                        continue
                    if "name" not in tc:
                        errors.append(f"test_sets[{i}].test_cases[{j}].name is required")
                    test_count += 1

    return len(errors) == 0, errors, test_count


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 of a file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def check_drift(repo_path: Path) -> list[DriftResult]:
    """Scan all .roboscope files in a repo and check target .robot file drift."""
    results: list[DriftResult] = []

    for spec_file in repo_path.rglob("*.roboscope"):
        try:
            spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(spec, dict):
            continue

        metadata = spec.get("metadata", {})
        target = metadata.get("target_file")
        if not target:
            continue

        robot_path = repo_path / target
        gen_hash = metadata.get("generation_hash")

        if not robot_path.exists():
            results.append(DriftResult(
                spec_file=str(spec_file.relative_to(repo_path)),
                target_file=target,
                status="missing",
            ))
        elif not gen_hash:
            results.append(DriftResult(
                spec_file=str(spec_file.relative_to(repo_path)),
                target_file=target,
                status="missing",
            ))
        else:
            current_hash = compute_file_hash(robot_path)
            status = "in_sync" if current_hash == gen_hash else "drifted"
            results.append(DriftResult(
                spec_file=str(spec_file.relative_to(repo_path)),
                target_file=target,
                status=status,
            ))

    return results


# ---------------------------------------------------------------------------
# File write helpers
# ---------------------------------------------------------------------------


def write_generated_file(repo_path: Path, relative_path: str, content: str) -> str:
    """Write generated content to a file in the repo and return its SHA256."""
    target = repo_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def update_spec_hash(repo_path: Path, spec_relative: str, new_hash: str) -> None:
    """Update the generation_hash in a .roboscope file after writing generated output."""
    spec_path = repo_path / spec_relative
    if not spec_path.exists():
        return
    content = spec_path.read_text(encoding="utf-8")
    try:
        spec = yaml.safe_load(content)
    except yaml.YAMLError:
        return

    if not isinstance(spec, dict) or "metadata" not in spec:
        return

    from datetime import datetime, timezone

    spec["metadata"]["generation_hash"] = new_hash
    spec["metadata"]["last_generated"] = datetime.now(timezone.utc).isoformat()

    spec_path.write_text(
        yaml.dump(spec, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
