"""Repository management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import Role
from src.auth.dependencies import get_current_user, require_role
from src.auth.models import User
from src.celery_app import TaskDispatchError, dispatch_task
from src.database import get_db
from src.repos.schemas import (
    BranchResponse,
    RepoCreate,
    RepoResponse,
    RepoUpdate,
    SyncResponse,
)
from src.repos.service import (
    create_repository,
    delete_repository,
    get_repository,
    get_repository_by_name,
    list_branches,
    list_repositories,
    update_repository,
)

logger = logging.getLogger("mateox.repos")

router = APIRouter()


@router.get("", response_model=list[RepoResponse])
async def get_repos(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List all repositories."""
    return await list_repositories(db)


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def add_repo(
    data: RepoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Add a new repository."""
    existing = await get_repository_by_name(db, data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository with this name already exists",
        )
    repo = await create_repository(db, data, current_user.id)
    await db.commit()
    # Trigger async clone only for git repos
    if repo.repo_type == "git":
        try:
            from src.repos.tasks import clone_repo

            dispatch_task(clone_repo, repo.id)
        except TaskDispatchError as e:
            logger.error("Failed to dispatch clone for repo %d: %s", repo.id, e)
            repo.sync_status = "error"
            repo.sync_error = f"Task dispatch failed: {e}"
            await db.flush()
            await db.refresh(repo)
    return repo


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Get repository details."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


@router.patch("/{repo_id}", response_model=RepoResponse)
async def patch_repo(
    repo_id: int,
    data: RepoUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Update repository settings."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return await update_repository(db, repo, data)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_repo(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Delete a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    await delete_repository(db, repo)


@router.post("/{repo_id}/sync", response_model=SyncResponse)
async def sync_repo(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.EDITOR)),
):
    """Trigger git sync for a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if repo.repo_type == "local":
        return SyncResponse(status="skipped", message="Local repositories do not require sync")

    try:
        from src.repos.tasks import sync_repo

        result = dispatch_task(sync_repo, repo.id)
        return SyncResponse(status="syncing", message="Sync started", task_id=result.id)
    except TaskDispatchError as e:
        logger.error("Failed to dispatch sync for repo %d: %s", repo.id, e)
        repo.sync_status = "error"
        repo.sync_error = f"Task dispatch failed: {e}"
        await db.flush()
        return SyncResponse(status="error", message=f"Task dispatch failed: {e}")


@router.get("/{repo_id}/branches", response_model=list[BranchResponse])
async def get_branches(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List branches for a repository."""
    repo = await get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    branches = list_branches(repo.local_path)
    return [BranchResponse(**b) for b in branches]
