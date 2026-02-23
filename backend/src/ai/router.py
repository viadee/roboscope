"""AI module API endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.celery_app import TaskDispatchError, dispatch_task
from src.database import get_db
from src.repos.models import Repository

from src.ai.models import AiJob, AiProvider
from src.ai.schemas import (
    AiJobResponse,
    AiProviderCreate,
    AiProviderResponse,
    AiProviderUpdate,
    DriftResponse,
    GenerateRequest,
    JobAcceptRequest,
    ReverseRequest,
    RfKeywordSearchResponse,
    RfKnowledgeStatusResponse,
    RfMcpDetailedStatus,
    RfMcpSetupRequest,
    RfRecommendRequest,
    RfRecommendResponse,
    ValidateSpecRequest,
    ValidateSpecResponse,
    XrayExportRequest,
    XrayImportRequest,
    XrayImportResponse,
)
from src.ai.service import (
    check_drift,
    create_job,
    create_provider,
    delete_provider,
    get_default_provider,
    get_job,
    get_provider,
    list_providers,
    update_provider,
    update_spec_hash,
    validate_spec,
    write_generated_file,
)
from src.ai.tasks import run_generate, run_reverse

logger = logging.getLogger("roboscope.ai.router")

router = APIRouter()


# ---------------------------------------------------------------------------
# Provider management (Admin only)
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[AiProviderResponse])
def get_providers(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all configured LLM providers."""
    providers = list_providers(db)
    return [_provider_to_response(p) for p in providers]


@router.post("/providers", response_model=AiProviderResponse, status_code=201)
def add_provider(
    data: AiProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Create a new LLM provider."""
    provider = create_provider(db, data, current_user.id)
    return _provider_to_response(provider)


@router.patch("/providers/{provider_id}", response_model=AiProviderResponse)
def edit_provider(
    provider_id: int,
    data: AiProviderUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Update an LLM provider."""
    provider = update_provider(db, provider_id, data)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_to_response(provider)


@router.delete("/providers/{provider_id}", status_code=204)
def remove_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete an LLM provider."""
    if not delete_provider(db, provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")


# ---------------------------------------------------------------------------
# Generation (Spec → Robot)
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=AiJobResponse)
def generate_robot(
    data: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Generate a .robot file from a .roboscope specification."""
    repo = _get_repo(db, data.repository_id)

    # Resolve provider
    provider = None
    if data.provider_id:
        provider = get_provider(db, data.provider_id)
    else:
        provider = get_default_provider(db)
    if not provider:
        raise HTTPException(status_code=400, detail="No LLM provider configured")

    # Verify spec file exists
    spec_file = Path(repo.local_path) / data.spec_path
    if not spec_file.exists():
        raise HTTPException(status_code=404, detail="Spec file not found")

    # Read spec to get target_path
    import yaml

    try:
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        target_path = spec.get("metadata", {}).get("target_file")
    except Exception:
        target_path = None

    # Drift check (unless force)
    if not data.force and target_path:
        target_file = Path(repo.local_path) / target_path
        if target_file.exists():
            import hashlib

            current_hash = hashlib.sha256(target_file.read_bytes()).hexdigest()
            gen_hash = spec.get("metadata", {}).get("generation_hash")
            if gen_hash and current_hash != gen_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Target .robot file has been manually edited since last generation. "
                    "Set force=true to overwrite.",
                )

    job = create_job(db, "generate", repo.id, provider.id, data.spec_path, target_path,
                     current_user.id)
    db.commit()

    try:
        dispatch_task(run_generate, job.id)
    except TaskDispatchError as e:
        job.status = "failed"
        job.error_message = str(e)
        db.flush()

    return _job_to_response(job)


# ---------------------------------------------------------------------------
# Reverse (Robot → Spec)
# ---------------------------------------------------------------------------


@router.post("/reverse", response_model=AiJobResponse)
def reverse_robot(
    data: ReverseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Extract a .roboscope spec from an existing .robot file."""
    repo = _get_repo(db, data.repository_id)

    provider = None
    if data.provider_id:
        provider = get_provider(db, data.provider_id)
    else:
        provider = get_default_provider(db)
    if not provider:
        raise HTTPException(status_code=400, detail="No LLM provider configured")

    robot_file = Path(repo.local_path) / data.robot_path
    if not robot_file.exists():
        raise HTTPException(status_code=404, detail="Robot file not found")

    output_path = data.output_path
    if not output_path:
        # Auto-derive: same dir, same name with .roboscope extension
        robot_p = Path(data.robot_path)
        output_path = str(robot_p.with_suffix(".roboscope"))

    job = create_job(db, "reverse", repo.id, provider.id, data.robot_path, output_path,
                     current_user.id)
    db.commit()

    try:
        dispatch_task(run_reverse, job.id)
    except TaskDispatchError as e:
        job.status = "failed"
        job.error_message = str(e)
        db.flush()

    return _job_to_response(job)


# ---------------------------------------------------------------------------
# Job status & accept
# ---------------------------------------------------------------------------


@router.get("/status/{job_id}", response_model=AiJobResponse)
def job_status(
    job_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Poll the status of an AI generation/reverse job."""
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.post("/accept", status_code=200)
def accept_job(
    data: JobAcceptRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Accept a completed job result — writes the generated file to the repo."""
    job = get_job(db, data.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed")
    if not job.result_preview:
        raise HTTPException(status_code=400, detail="Job has no result to accept")
    if not job.target_path:
        raise HTTPException(status_code=400, detail="Job has no target path")

    from sqlalchemy import select as sa_select

    repo = db.execute(
        sa_select(Repository).where(Repository.id == job.repository_id)
    ).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_path = Path(repo.local_path)
    file_hash = write_generated_file(repo_path, job.target_path, job.result_preview)

    # Update generation_hash in the .roboscope spec (only for generate jobs)
    if job.job_type == "generate":
        update_spec_hash(repo_path, job.spec_path, file_hash)

    return {"status": "written", "target_path": job.target_path, "hash": file_hash}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@router.post("/validate", response_model=ValidateSpecResponse)
def validate_spec_endpoint(
    data: ValidateSpecRequest,
    _current_user: User = Depends(get_current_user),
):
    """Validate .roboscope YAML syntax."""
    valid, errors, test_count = validate_spec(data.content)
    return ValidateSpecResponse(valid=valid, errors=errors, test_count=test_count)


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


@router.get("/drift/{repo_id}", response_model=DriftResponse)
def drift_check(
    repo_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Check drift between .roboscope specs and generated .robot files."""
    repo = _get_repo(db, repo_id)
    results = check_drift(Path(repo.local_path))
    return DriftResponse(repository_id=repo_id, results=results)


# ---------------------------------------------------------------------------
# rf-mcp knowledge endpoints
# ---------------------------------------------------------------------------


@router.get("/rf-knowledge/status", response_model=RfKnowledgeStatusResponse)
def rf_knowledge_status(
    _current_user: User = Depends(get_current_user),
):
    """Check if the rf-mcp server is configured and available."""
    from src.ai import rf_knowledge
    from src.ai.rf_mcp_manager import get_effective_url

    return RfKnowledgeStatusResponse(
        available=rf_knowledge.is_available(),
        url=get_effective_url(),
    )


@router.get("/rf-knowledge/keywords", response_model=RfKeywordSearchResponse)
async def rf_knowledge_keywords(
    q: str,
    _current_user: User = Depends(get_current_user),
):
    """Search for Robot Framework keywords via rf-mcp."""
    from src.ai import rf_knowledge

    results = await rf_knowledge.search_keywords(q)
    return RfKeywordSearchResponse(
        results=[
            {"name": r.get("name", ""), "library": r.get("library", ""), "doc": r.get("doc", "")}
            for r in results
        ]
    )


@router.post("/rf-knowledge/recommend", response_model=RfRecommendResponse)
async def rf_knowledge_recommend(
    data: RfRecommendRequest,
    _current_user: User = Depends(get_current_user),
):
    """Get library recommendations for a test description via rf-mcp."""
    from src.ai import rf_knowledge

    libraries = await rf_knowledge.recommend_libraries(data.description)
    return RfRecommendResponse(libraries=libraries)


# ---------------------------------------------------------------------------
# rf-mcp server management
# ---------------------------------------------------------------------------


@router.get("/rf-mcp/status", response_model=RfMcpDetailedStatus)
def rf_mcp_status(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get detailed rf-mcp server status including install/running state."""
    from src.ai import rf_mcp_manager

    status = rf_mcp_manager.get_status()

    # Resolve environment name if we have an env_id
    env_name = None
    env_id = status.get("environment_id")
    if env_id:
        from sqlalchemy import select as sa_select
        from src.environments.models import Environment

        env = db.execute(
            sa_select(Environment).where(Environment.id == env_id)
        ).scalar_one_or_none()
        if env:
            env_name = env.name

    return RfMcpDetailedStatus(
        status=status["status"],
        running=status["running"],
        port=status.get("port"),
        pid=status.get("pid"),
        url=status.get("url", ""),
        environment_id=env_id,
        environment_name=env_name,
        error_message=status.get("error_message", ""),
        installed_version=status.get("installed_version"),
    )


@router.post("/rf-mcp/setup", response_model=RfMcpDetailedStatus)
def rf_mcp_setup(
    data: RfMcpSetupRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Install rf-mcp (if needed) and start the server. Runs as background task."""
    from sqlalchemy import select as sa_select
    from src.environments.models import Environment
    from src.ai import rf_mcp_manager

    # Validate environment exists
    env = db.execute(
        sa_select(Environment).where(Environment.id == data.environment_id)
    ).scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    if not env.venv_path:
        raise HTTPException(status_code=400, detail="Environment has no virtual environment")

    # Stop any running instance first
    rf_mcp_manager.stop_server()

    # Set status to "installing" immediately so polling sees it before the
    # background task starts (avoids race where poll sees "stopped" and quits)
    rf_mcp_manager._status = "installing"
    rf_mcp_manager._environment_id = data.environment_id
    rf_mcp_manager._error_message = ""

    # Dispatch setup as background task
    try:
        dispatch_task(rf_mcp_manager.setup, data.environment_id, data.port)
    except TaskDispatchError as e:
        raise HTTPException(status_code=500, detail=f"Failed to dispatch setup task: {e}")

    # Return current status (will be "installing" or "starting" soon)
    return RfMcpDetailedStatus(
        status="installing",
        running=False,
        environment_id=data.environment_id,
        environment_name=env.name,
    )


@router.post("/rf-mcp/stop", response_model=RfMcpDetailedStatus)
def rf_mcp_stop(
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Stop the managed rf-mcp server."""
    from src.ai import rf_mcp_manager

    rf_mcp_manager.stop_server()
    status = rf_mcp_manager.get_status()

    return RfMcpDetailedStatus(
        status=status["status"],
        running=status["running"],
    )


# ---------------------------------------------------------------------------
# Xray bridge endpoints
# ---------------------------------------------------------------------------


@router.post("/xray/export")
def xray_export(
    data: XrayExportRequest,
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Convert .roboscope spec content to Xray JSON format."""
    import yaml as yaml_lib

    from src.ai.xray_bridge import roboscope_to_xray

    try:
        spec = yaml_lib.safe_load(data.content)
    except yaml_lib.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    if not isinstance(spec, dict):
        raise HTTPException(status_code=400, detail="Spec must be a YAML mapping")

    return roboscope_to_xray(spec)


@router.post("/xray/import", response_model=XrayImportResponse)
def xray_import(
    data: XrayImportRequest,
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Convert Xray JSON to .roboscope v2 YAML format."""
    import yaml as yaml_lib

    from src.ai.xray_bridge import xray_to_roboscope

    xray_data = {"info": data.info, "tests": data.tests}
    spec = xray_to_roboscope(xray_data)
    yaml_content = yaml_lib.dump(
        spec, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    return XrayImportResponse(content=yaml_content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_repo(db: Session, repo_id: int) -> Repository:
    """Get repository or raise 404."""
    from sqlalchemy import select as sa_select

    repo = db.execute(
        sa_select(Repository).where(Repository.id == repo_id)
    ).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


def _provider_to_response(provider: AiProvider) -> dict:
    """Convert provider to response dict (hide API key)."""
    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "api_base_url": provider.api_base_url,
        "has_api_key": provider.api_key_encrypted is not None,
        "model_name": provider.model_name,
        "temperature": provider.temperature,
        "max_tokens": provider.max_tokens,
        "is_default": provider.is_default,
        "created_by": provider.created_by,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }


def _job_to_response(job: AiJob) -> dict:
    """Convert job to response dict."""
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "repository_id": job.repository_id,
        "provider_id": job.provider_id,
        "spec_path": job.spec_path,
        "target_path": job.target_path,
        "result_preview": job.result_preview,
        "error_message": job.error_message,
        "token_usage": job.token_usage,
        "triggered_by": job.triggered_by,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }
