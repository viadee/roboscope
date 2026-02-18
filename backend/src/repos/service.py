"""Repository management service: Git operations, CRUD."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.repos.models import Repository
from src.repos.schemas import RepoCreate, RepoUpdate


def list_repositories(db: Session) -> list[Repository]:
    """List all repositories."""
    result = db.execute(select(Repository).order_by(Repository.name))
    return list(result.scalars().all())


def get_repository(db: Session, repo_id: int) -> Repository | None:
    """Get a repository by ID."""
    result = db.execute(select(Repository).where(Repository.id == repo_id))
    return result.scalar_one_or_none()


def get_repository_by_name(db: Session, name: str) -> Repository | None:
    """Get a repository by name."""
    result = db.execute(select(Repository).where(Repository.name == name))
    return result.scalar_one_or_none()


def create_repository(
    db: Session, data: RepoCreate, user_id: int
) -> Repository:
    """Create a new repository entry."""
    if data.repo_type == "local":
        local_path = data.local_path
        path = Path(local_path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
    else:
        workspace = Path(settings.WORKSPACE_DIR)
        workspace.mkdir(parents=True, exist_ok=True)
        local_path = str(workspace / data.name)

    repo = Repository(
        name=data.name,
        repo_type=data.repo_type,
        git_url=data.git_url,
        default_branch=data.default_branch,
        local_path=local_path,
        auto_sync=data.auto_sync if data.repo_type == "git" else False,
        sync_interval_minutes=data.sync_interval_minutes,
        created_by=user_id,
    )
    db.add(repo)
    db.flush()
    db.refresh(repo)
    return repo


def update_repository(
    db: Session, repo: Repository, data: RepoUpdate
) -> Repository:
    """Update repository fields."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(repo, key, value)
    db.flush()
    db.refresh(repo)
    return repo


def delete_repository(db: Session, repo: Repository) -> None:
    """Delete a repository and its local clone (only for git repos)."""
    if repo.repo_type == "git":
        local_path = Path(repo.local_path)
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)
    db.delete(repo)
    db.flush()


def clone_repository(git_url: str, local_path: str, branch: str = "main"):
    """Clone a git repository (synchronous, for background tasks)."""
    from git import Repo

    path = Path(local_path)
    if path.exists():
        shutil.rmtree(path)
    return Repo.clone_from(git_url, local_path, branch=branch)


def sync_repository(local_path: str, branch: str | None = None) -> str:
    """Pull latest changes from remote (synchronous, for background tasks)."""
    from git import GitCommandError, InvalidGitRepositoryError, Repo

    try:
        repo = Repo(local_path)
    except InvalidGitRepositoryError:
        return "error: not a git repository"

    try:
        origin = repo.remotes.origin
        if branch:
            repo.git.checkout(branch)
        origin.pull()
        return f"synced to {repo.head.commit.hexsha[:8]}"
    except GitCommandError as e:
        return f"error: {e}"


def list_branches(local_path: str) -> list[dict]:
    """List all branches of a local repository."""
    from git import InvalidGitRepositoryError, Repo

    try:
        repo = Repo(local_path)
        active = repo.active_branch.name if not repo.head.is_detached else None
        branches = []
        for ref in repo.references:
            name = ref.name
            if name.startswith("origin/"):
                name = name[7:]
            if name not in [b["name"] for b in branches] and name != "HEAD":
                branches.append({"name": name, "is_active": name == active})
        return branches
    except (InvalidGitRepositoryError, Exception):
        return []


def get_current_branch(local_path: str) -> str | None:
    """Get the current active branch."""
    from git import InvalidGitRepositoryError, Repo

    try:
        repo = Repo(local_path)
        if repo.head.is_detached:
            return None
        return repo.active_branch.name
    except (InvalidGitRepositoryError, Exception):
        return None


def checkout_branch(local_path: str, branch: str) -> str:
    """Checkout a specific branch."""
    from git import GitCommandError, Repo

    try:
        repo = Repo(local_path)
        repo.git.checkout(branch)
        return f"checked out {branch}"
    except GitCommandError as e:
        return f"error: {e}"
