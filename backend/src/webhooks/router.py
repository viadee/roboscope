"""API endpoints for API tokens and webhooks."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.database import get_db
from src.webhooks.models import Webhook
from src.webhooks.schemas import (
    VALID_EVENTS,
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenResponse,
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdate,
)
from src.webhooks.service import (
    create_api_token,
    create_webhook,
    delete_webhook,
    get_webhook,
    list_deliveries,
    list_tokens,
    list_webhooks,
    revoke_token,
    test_webhook,
    update_webhook,
)

logger = logging.getLogger("roboscope.webhooks")

router = APIRouter()

# --- API Tokens ---


@router.post("/tokens", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(
    data: ApiTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Create a new API token (admin only). The plaintext token is shown only once."""
    token, plaintext = create_api_token(
        db,
        name=data.name,
        role=data.role,
        user_id=current_user.id,
        expires_in_days=data.expires_in_days,
    )
    token_data = ApiTokenResponse.model_validate(token).model_dump()
    token_data["token"] = plaintext
    return ApiTokenCreated(**token_data)


@router.get("/tokens", response_model=list[ApiTokenResponse])
def get_tokens(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """List all active API tokens (admin only)."""
    return list_tokens(db)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_token(
    token_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Revoke an API token (admin only)."""
    token = revoke_token(db, token_id)
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")


# --- Webhooks ---


@router.get("/events")
def get_available_events():
    """List all available webhook event types."""
    return {"events": VALID_EVENTS}


@router.post("/hooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_hook(
    data: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Create a new webhook."""
    try:
        webhook = create_webhook(db, data.model_dump(), current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return _webhook_to_response(webhook)


@router.get("/hooks", response_model=list[WebhookResponse])
def get_hooks(
    repository_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all webhooks."""
    webhooks = list_webhooks(db, repository_id=repository_id)
    return [_webhook_to_response(w) for w in webhooks]


@router.get("/hooks/{webhook_id}", response_model=WebhookResponse)
def get_hook(
    webhook_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get webhook details."""
    webhook = get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return _webhook_to_response(webhook)


@router.patch("/hooks/{webhook_id}", response_model=WebhookResponse)
def update_hook(
    webhook_id: int,
    data: WebhookUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Update a webhook."""
    webhook = get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    try:
        updated = update_webhook(db, webhook, data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return _webhook_to_response(updated)


@router.delete("/hooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hook(
    webhook_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Delete a webhook."""
    webhook = get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    delete_webhook(db, webhook)


@router.post("/hooks/{webhook_id}/test", response_model=WebhookTestResponse)
def test_hook(
    webhook_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Send a test ping to a webhook URL."""
    webhook = get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return test_webhook(webhook)


@router.get("/hooks/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
def get_deliveries(
    webhook_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get recent deliveries for a webhook."""
    webhook = get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return list_deliveries(db, webhook_id, limit=limit)


# --- Git Webhook Inbound ---


@router.post("/git")
def git_webhook_inbound(
    payload: dict,
    db: Session = Depends(get_db),
):
    """Receive inbound webhooks from GitHub/GitLab for auto-triggering test runs.

    No auth required — verification via webhook secret (future).
    Matches repository by git_url from the push event.
    """
    from sqlalchemy import select

    from src.repos.models import Repository

    # Try to extract git URL and branch from GitHub or GitLab payload format
    git_url = _extract_git_url(payload)
    branch = _extract_branch(payload)

    if not git_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not determine repository URL from payload",
        )

    # Match by git_url (try with and without .git suffix)
    urls_to_try = [git_url]
    if git_url.endswith(".git"):
        urls_to_try.append(git_url[:-4])
    else:
        urls_to_try.append(git_url + ".git")

    repo = None
    for url in urls_to_try:
        repo = db.execute(
            select(Repository).where(Repository.git_url == url)
        ).scalar_one_or_none()
        if repo:
            break

    if repo is None:
        logger.info("Git webhook: no matching repository for %s", git_url)
        return {"status": "ignored", "reason": "No matching repository"}

    # Create a test run for this repo
    from src.execution.models import ExecutionRun, RunStatus, RunType
    import src.auth.models  # noqa: F401 — FK resolution

    run = ExecutionRun(
        repository_id=repo.id,
        environment_id=repo.environment_id,
        run_type=RunType.BATCH,
        status=RunStatus.PENDING,
        target_path=".",
        branch=branch or repo.default_branch,
        triggered_by=repo.created_by,  # Use repo owner as trigger user
    )
    db.add(run)
    db.commit()

    # Dispatch to background executor
    try:
        from src.task_executor import dispatch_task
        from src.execution.tasks import execute_test_run

        result = dispatch_task(execute_test_run, run.id)
        run.task_id = result.id
        db.flush()
    except Exception as e:
        logger.error("Failed to dispatch git-triggered run %d: %s", run.id, e)
        run.status = RunStatus.ERROR
        run.error_message = f"Task dispatch failed: {e}"
        db.flush()

    logger.info(
        "Git webhook: triggered run %d for repo '%s' (branch: %s)",
        run.id, repo.name, branch or repo.default_branch,
    )
    return {
        "status": "triggered",
        "run_id": run.id,
        "repository": repo.name,
        "branch": branch or repo.default_branch,
    }


def _extract_git_url(payload: dict) -> str | None:
    """Extract git clone URL from GitHub or GitLab push payload."""
    # GitHub format
    repo = payload.get("repository", {})
    if isinstance(repo, dict):
        # GitHub: clone_url or html_url
        for key in ("clone_url", "html_url", "ssh_url", "git_url"):
            if key in repo:
                return repo[key]
        # GitLab: git_http_url or git_ssh_url
        for key in ("git_http_url", "git_ssh_url", "url"):
            if key in repo:
                return repo[key]
    return None


def _extract_branch(payload: dict) -> str | None:
    """Extract branch name from push payload."""
    ref = payload.get("ref", "")
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return None


def _webhook_to_response(webhook: Webhook) -> WebhookResponse:
    """Convert Webhook model to response schema."""
    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        has_secret=webhook.secret is not None and webhook.secret != "",
        events=json.loads(webhook.events),
        is_active=webhook.is_active,
        repository_id=webhook.repository_id,
        created_by=webhook.created_by,
        last_triggered_at=webhook.last_triggered_at,
        last_status_code=webhook.last_status_code,
        created_at=webhook.created_at,
    )
