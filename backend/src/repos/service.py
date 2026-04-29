"""Repository management service: Git operations, CRUD."""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.repos.models import ProjectMember, Repository
from src.repos.schemas import RepoCreate, RepoUpdate


def list_repositories(db: Session, user_id: int | None = None, is_admin: bool = False) -> list[Repository]:
    """List repositories. Admins see all; others see only projects they are members of."""
    if is_admin or user_id is None:
        result = db.execute(select(Repository).order_by(Repository.name))
        return list(result.scalars().all())
    # Return repos where user is creator OR member
    member_repo_ids = db.execute(
        select(ProjectMember.repository_id).where(ProjectMember.user_id == user_id)
    ).scalars().all()
    result = db.execute(
        select(Repository)
        .where(
            (Repository.created_by == user_id) | Repository.id.in_(member_repo_ids)
        )
        .order_by(Repository.name)
    )
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
        # `data.local_path` is `str | None` on the schema; the
        # `validate_type_fields` model validator on RepoCreate enforces
        # it's set whenever repo_type == 'local'. Mypy can't see across
        # the validator, so we re-assert here.
        assert data.local_path is not None, (
            "RepoCreate.validate_type_fields should have rejected a "
            "local repo without local_path before reaching this point"
        )
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


def list_remote_branches(git_url: str) -> list[str]:
    """List remote branches without cloning (via git ls-remote)."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", git_url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        branches = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                ref = parts[1]
                if ref.startswith("refs/heads/"):
                    branches.append(ref[len("refs/heads/"):])
        return branches
    except Exception:
        return []


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


# ---------------------------------------------------------------------------
# Story REPO-1 — non-Git-user save loop (status / commit / push / publish)
# ---------------------------------------------------------------------------


class GitOperationError(Exception):
    """Raised by the save-loop helpers for any git failure that the
    router should translate to a structured error response. Carries
    a stable `kind` discriminator so the router knows whether a
    failure is a 404 / 400 / 409 / 502.

    `kind` is one of:
      - 'not_a_repo'         the path is not a git repo (404)
      - 'nothing_to_commit'  the index is clean (400)
      - 'non_fast_forward'   the remote rejected the push (409)
      - 'auth'               remote authentication failed (502)
      - 'other'              everything else (500)
    """

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def get_repo_status(local_path: str) -> dict:
    """Snapshot of the working tree + tracking-branch divergence.

    Returns a dict shaped for the API response:

        {
          "current_branch": str | None,
          "ahead": int,
          "behind": int,
          "modified": [str, ...],
          "staged":   [str, ...],
          "untracked":[str, ...],
          "deleted":  [str, ...],
          "is_dirty": bool,
        }

    Non-existent or non-git paths yield a benign empty snapshot rather
    than throwing — the router decides whether that is a 400.
    """
    from git import InvalidGitRepositoryError, Repo

    empty = {
        "current_branch": None,
        "ahead": 0,
        "behind": 0,
        "modified": [],
        "staged": [],
        "untracked": [],
        "deleted": [],
        "is_dirty": False,
    }
    path = Path(local_path)
    if not path.exists() or not (path / ".git").exists():
        return empty

    try:
        repo = Repo(local_path)
    except InvalidGitRepositoryError:
        return empty

    current_branch: str | None = None
    if not repo.head.is_detached:
        current_branch = repo.active_branch.name

    ahead = 0
    behind = 0
    if current_branch is not None:
        tracking = repo.active_branch.tracking_branch()
        if tracking is not None:
            try:
                ahead = sum(
                    1 for _ in repo.iter_commits(f"{tracking.name}..{current_branch}")
                )
                behind = sum(
                    1 for _ in repo.iter_commits(f"{current_branch}..{tracking.name}")
                )
            except Exception:
                pass

    # `repo.index.diff(None)`     = working-tree-vs-index (unstaged edits + deletes)
    # `repo.index.diff("HEAD")`   = index-vs-last-commit  (staged edits)
    modified: list[str] = []
    deleted: list[str] = []
    for change in repo.index.diff(None):
        path_str = change.a_path or change.b_path or ""
        if change.change_type == "D":
            deleted.append(path_str)
        elif path_str:
            modified.append(path_str)

    staged: list[str] = []
    try:
        for change in repo.index.diff("HEAD"):
            path_str = change.a_path or change.b_path or ""
            if path_str and path_str not in staged:
                staged.append(path_str)
    except Exception:
        # Empty repo (no HEAD yet) — index.diff("HEAD") raises.
        pass

    untracked = list(repo.untracked_files)

    is_dirty = bool(modified or staged or untracked or deleted)

    return {
        "current_branch": current_branch,
        "ahead": ahead,
        "behind": behind,
        "modified": sorted(modified),
        "staged": sorted(staged),
        "untracked": sorted(untracked),
        "deleted": sorted(deleted),
        "is_dirty": is_dirty,
    }


def commit_changes(
    local_path: str,
    message: str,
    paths: list[str] | None,
    author_name: str,
    author_email: str,
) -> dict:
    """Stage `paths` (or every dirty path when None) and commit with
    the given identity.

    Identity is supplied PER-COMMAND (`-c user.email=… -c user.name=…`)
    so concurrent commits by different users do not race on the
    repository's `.git/config` file.

    Raises `GitOperationError` with one of:
      - 'not_a_repo'
      - 'nothing_to_commit'
      - 'other'
    """
    from git import GitCommandError, InvalidGitRepositoryError, Repo

    path = Path(local_path)
    if not path.exists() or not (path / ".git").exists():
        raise GitOperationError("not_a_repo", "not a git repository")
    try:
        repo = Repo(local_path)
    except InvalidGitRepositoryError:
        raise GitOperationError("not_a_repo", "not a git repository")

    if paths is None:
        status = get_repo_status(local_path)
        targets = (
            list(status.get("modified") or [])
            + list(status.get("untracked") or [])
            + list(status.get("deleted") or [])
            + list(status.get("staged") or [])
        )
    else:
        targets = list(paths)

    # `git add -A -- <paths…>` covers modified, untracked, and deleted
    # in a single call. Empty list short-circuits to "nothing to stage".
    if targets:
        try:
            repo.git.add("-A", "--", *targets)
        except GitCommandError as e:
            raise GitOperationError("other", f"git add failed: {e}")

    try:
        diff_to_head = list(repo.index.diff("HEAD"))
        clean = not diff_to_head
    except Exception:
        # Empty repo: any staged entry counts as non-clean.
        clean = not list(repo.index.entries)

    if clean:
        raise GitOperationError("nothing_to_commit", "no staged changes to commit")

    try:
        # Identity via env vars — no .git/config write, so concurrent
        # commits by different users on the same repo can never race
        # on the config file. Author AND committer are set so
        # `git log --pretty=fuller` surfaces the real user (committer
        # otherwise defaults to whatever `git config --global` says).
        env = {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }
        repo.git.update_environment(**env)
        try:
            repo.git.commit("-m", message)
        finally:
            # Drop the env so the same Repo instance doesn't carry the
            # identity into unrelated subsequent commands.
            for key in env:
                repo.git.update_environment(**{key: None})
        head_sha = repo.head.commit.hexsha
    except GitCommandError as e:
        if "nothing to commit" in str(e).lower():
            raise GitOperationError("nothing_to_commit", "no staged changes to commit")
        raise GitOperationError("other", f"git commit failed: {e}")

    return {
        "commit_hash": head_sha,
        "message": message,
        "files": sorted(targets),
    }


def push_branch(local_path: str, branch: str | None = None) -> dict:
    """Push the given branch (or the current one) to its tracked
    upstream. Returns `{branch, remote_ref, ahead_after}`.

    Raises `GitOperationError` with one of:
      - 'not_a_repo'
      - 'non_fast_forward'
      - 'auth'
      - 'other'
    """
    from git import GitCommandError, InvalidGitRepositoryError, Repo

    path = Path(local_path)
    if not path.exists() or not (path / ".git").exists():
        raise GitOperationError("not_a_repo", "not a git repository")
    try:
        repo = Repo(local_path)
    except InvalidGitRepositoryError:
        raise GitOperationError("not_a_repo", "not a git repository")

    target_branch = branch
    if target_branch is None:
        if repo.head.is_detached:
            raise GitOperationError("other", "HEAD is detached; checkout a branch first")
        target_branch = repo.active_branch.name

    try:
        # Use `git push` directly so non-zero exit codes propagate as
        # GitCommandError — the high-level `.push()` swallows them.
        repo.git.push("origin", target_branch)
        remote_ref = f"origin/{target_branch}"
        ahead_after = 0
        try:
            tracking = repo.active_branch.tracking_branch()
            if tracking is not None:
                ahead_after = sum(
                    1 for _ in repo.iter_commits(f"{tracking.name}..{target_branch}")
                )
        except Exception:
            pass
        return {
            "branch": target_branch,
            "remote_ref": remote_ref,
            "ahead_after": ahead_after,
        }
    except GitCommandError as e:
        msg = str(e).lower()
        if (
            "non-fast-forward" in msg
            or "rejected" in msg
            or "fetch first" in msg
            or "updates were rejected" in msg
        ):
            raise GitOperationError("non_fast_forward", str(e))
        if (
            "authentication" in msg
            or "permission denied" in msg
            or "could not read username" in msg
            or "support for password authentication was removed" in msg
        ):
            raise GitOperationError("auth", str(e))
        raise GitOperationError("other", f"git push failed: {e}")


def publish_changes(
    local_path: str,
    message: str,
    paths: list[str] | None,
    author_name: str,
    author_email: str,
) -> dict:
    """Combined commit + push backing `POST /repos/{id}/publish`.

    On full success returns:
        {commit_hash, message, files, pushed: True, conflict: False, remote_ref}

    On commit-succeeded-but-push-failed re-raises the push's
    `GitOperationError` decorated with `commit_hash` + `committed_files`
    so the router can include them in the 409 body — the local commit
    stays in place so the user doesn't lose work.
    """
    commit_result = commit_changes(
        local_path, message, paths, author_name, author_email
    )
    try:
        push_result = push_branch(local_path)
    except GitOperationError as e:
        e.commit_hash = commit_result["commit_hash"]  # type: ignore[attr-defined]
        e.committed_files = commit_result["files"]   # type: ignore[attr-defined]
        raise

    return {
        **commit_result,
        "pushed": True,
        "conflict": False,
        "remote_ref": push_result["remote_ref"],
    }


# ---------------------------------------------------------------------------
# Story REPO-2 — auto-sync scheduler
# ---------------------------------------------------------------------------


def due_repos(db: Session, now: datetime | None = None) -> list[Repository]:
    """Return every git repo whose auto-sync is overdue.

    A repo is "due" when ALL of the following hold:
      - `repo_type == 'git'` (local repos have nothing to pull)
      - `git_url` is set (defensive: a repo with auto_sync=True but
        no URL would crash the dispatch task)
      - `auto_sync == True`
      - `sync_status != 'syncing'` (a previous sync still running →
        skip this tick instead of dispatching a duplicate)
      - `last_synced_at IS NULL` (never synced) OR
        `last_synced_at < now - sync_interval_minutes`

    The interval comparison happens in Python because SQLite's
    `datetime + interval` story is portability-hostile and the
    candidate set (auto_sync=True repos) is tiny in practice.

    `now` defaults to `datetime.now(UTC)`.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    candidates = db.execute(
        select(Repository).where(
            Repository.repo_type == "git",
            Repository.auto_sync.is_(True),
            Repository.git_url.is_not(None),
        )
    ).scalars().all()

    out: list[Repository] = []
    for repo in candidates:
        if repo.sync_status == "syncing":
            continue
        if repo.last_synced_at is None:
            out.append(repo)
            continue
        # Review fix M2 — normalise BOTH sides to aware-UTC in one
        # shot rather than dispatching on partial branches. Today
        # SQLite + plain `Mapped[datetime]` give us naive values back;
        # if the column is ever flipped to `DateTime(timezone=True)`
        # for Postgres, this code keeps working without an audit.
        last = repo.last_synced_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now_aware = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        boundary = last + timedelta(minutes=repo.sync_interval_minutes)
        if now_aware >= boundary:
            out.append(repo)
    return out


# ---------------------------------------------------------------------------
# Story REPO-3 — pre-run sync (best-effort pull right before each run)
# ---------------------------------------------------------------------------


def sync_for_run(
    repo: Repository,
    session: Session | None = None,
    timeout_seconds: int = 60,
) -> tuple[str, str | None]:
    """Pull `origin/<default_branch>` synchronously *before* a test run.

    Returns a `(status, detail)` tuple — the caller logs / decides
    whether to update `last_synced_at`. **Never raises**: a pre-run
    sync failure must not abort the run; the runner falls through with
    whatever's on disk.

    When `session` is provided, the helper flips `repo.sync_status` to
    `'syncing'` *before* the pull and to `'success'` / `'error'` after
    (review fix M2). This blocks the REPO-2 scheduler from racing a
    second `git pull` on the same working copy. When `session` is
    `None` (e.g. from unit tests that just want to exercise the return
    contract), the status writes are skipped.

    Possible status values:
      - `"skipped"` — feature off, repo not git, or another sync in flight.
        `detail` carries the reason for ops.
      - `"ok"`     — pull succeeded; `detail` is the short message from
        `sync_repository()` (e.g. `"synced to abc12345"`).
      - `"error"`  — git surfaced a recoverable error (auth, ref not
        found, dirty tree, …). `detail` is the message.
      - `"timeout"` — the pull exceeded `timeout_seconds`. `detail` is
        the timeout in seconds. The pull thread is leaked (it will
        eventually finish in the background); see story risk notes.
    """
    if repo.repo_type != "git" or not repo.pre_run_sync:
        return ("skipped", "pre_run_sync disabled")
    if repo.sync_status == "syncing":
        # AC5 — don't race a manual / scheduled sync.
        return ("skipped", "another sync in progress")
    if not repo.git_url:
        return ("skipped", "no git url")

    import concurrent.futures

    # Review fix M2 — flip sync_status synchronously *before* dispatching
    # so the auto-sync scheduler's `due_repos()` filter sees the in-flight
    # state. Skip the write if the caller didn't pass a session (unit-test
    # mode).
    if session is not None:
        repo.sync_status = "syncing"
        session.commit()

    # Review fix M1 — explicit pool + `shutdown(wait=False)` in `finally`.
    # The naive `with ThreadPoolExecutor(...) as pool:` form blocks on
    # __exit__ → shutdown(wait=True), which negates the wall-clock timeout
    # we just imposed.
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="pre-run-sync"
    )
    msg: str | None = None
    status: str
    detail: str | None
    try:
        future = pool.submit(
            sync_repository, repo.local_path, repo.default_branch
        )
        try:
            msg = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            status, detail = "timeout", f"{timeout_seconds}s"
        except Exception as exc:  # defensive — sync_repository swallows GitCommandError already
            status, detail = "error", str(exc)[:200]
        else:
            # `sync_repository` returns "error: ..." for git failures.
            if isinstance(msg, str) and msg.startswith("error"):
                status, detail = "error", msg.removeprefix("error:").strip()
            else:
                status, detail = "ok", msg
    finally:
        pool.shutdown(wait=False)

    if session is not None:
        if status == "ok":
            repo.sync_status = "success"
            repo.sync_error = None
        else:
            # error / timeout — surface on the repo card so the user knows
            # the most recent pull failed. The run itself still proceeds
            # with whatever's on disk.
            repo.sync_status = "error"
            repo.sync_error = (detail or status)[:500]
        session.commit()

    return (status, detail)


# ---------------------------------------------------------------------------
# Project Members
# ---------------------------------------------------------------------------


def list_project_members(db: Session, repo_id: int) -> list[dict]:
    """List all members of a project with user info."""
    import src.auth.models  # noqa: F401

    from src.auth.models import User

    members = db.execute(
        select(ProjectMember, User.username, User.email)
        .join(User, ProjectMember.user_id == User.id)
        .where(ProjectMember.repository_id == repo_id)
        .order_by(User.username)
    ).all()
    result = []
    for member, username, email in members:
        result.append({
            "id": member.id,
            "user_id": member.user_id,
            "repository_id": member.repository_id,
            "role": member.role,
            "username": username,
            "email": email,
            "created_at": member.created_at,
        })
    return result


def add_project_member(
    db: Session, repo_id: int, user_id: int, role: str = "viewer"
) -> ProjectMember:
    """Add a user as a member of a project."""
    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.repository_id == repo_id,
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = role
        db.flush()
        db.refresh(existing)
        return existing
    member = ProjectMember(user_id=user_id, repository_id=repo_id, role=role)
    db.add(member)
    db.flush()
    db.refresh(member)
    return member


def update_project_member_role(
    db: Session, member_id: int, role: str
) -> ProjectMember | None:
    """Update a project member's role."""
    member = db.execute(
        select(ProjectMember).where(ProjectMember.id == member_id)
    ).scalar_one_or_none()
    if not member:
        return None
    member.role = role
    db.flush()
    db.refresh(member)
    return member


def remove_project_member(db: Session, member_id: int) -> bool:
    """Remove a user from a project."""
    member = db.execute(
        select(ProjectMember).where(ProjectMember.id == member_id)
    ).scalar_one_or_none()
    if not member:
        return False
    db.delete(member)
    db.flush()
    return True


def is_project_member(db: Session, repo_id: int, user_id: int) -> bool:
    """Check if a user has access to a project (member or creator)."""
    repo = get_repository(db, repo_id)
    if repo and repo.created_by == user_id:
        return True
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.repository_id == repo_id,
        )
    ).scalar_one_or_none()
    return member is not None
