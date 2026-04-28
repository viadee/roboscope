"""Story REPO-1 — non-Git-user save loop integration tests.

Each test spins up a temp `bare.git` upstream + a working clone, drives
the new endpoints / service helpers against them, and asserts that:

  - status reflects what `git status` would show
  - commit records the user's identity + happens to the right branch
  - push lands when fast-forward, returns 409 when divergent
  - publish (combined) keeps the local commit when push fails
  - RBAC blocks non-editors
  - local repos are politely rejected
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from git import Repo
from sqlalchemy.orm import Session

from src.auth.constants import Role
from src.auth.service import hash_password
from src.repos.models import Repository
from src.repos.service import (
    GitOperationError,
    commit_changes,
    get_repo_status,
    publish_changes,
    push_branch,
)
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """Create an empty bare repository to act as the upstream."""
    bare = tmp_path / "remote.git"
    Repo.init(bare, bare=True, initial_branch="main")
    return bare


@pytest.fixture
def working_clone(tmp_path: Path, bare_remote: Path) -> Path:
    """Clone the bare remote and seed it with one initial commit so
    `main` exists upstream and the clone can do fast-forward pushes."""
    clone = tmp_path / "clone"
    repo = Repo.clone_from(str(bare_remote), str(clone))

    # Seed: a single committed file so HEAD exists.
    seed = clone / "README.md"
    seed.write_text("seed\n", encoding="utf-8")
    repo.index.add(["README.md"])
    # Commit with a stable identity so `committer` doesn't pick up the
    # test runner's local git config.
    repo.git.update_environment(
        GIT_AUTHOR_NAME="seed", GIT_AUTHOR_EMAIL="seed@example.com",
        GIT_COMMITTER_NAME="seed", GIT_COMMITTER_EMAIL="seed@example.com",
    )
    repo.git.commit("-m", "seed")
    repo.git.push("origin", "main")
    return clone


@pytest.fixture
def divergent_clone(tmp_path: Path, bare_remote: Path) -> Path:
    """Second clone of the same remote — used to push a competing
    commit that triggers a non-fast-forward error in the primary
    clone's push."""
    other = tmp_path / "other"
    Repo.clone_from(str(bare_remote), str(other))
    return other


@pytest.fixture
def editor_user(db_session: Session):
    from src.auth.models import User

    u = User(
        email="editor@test.com",
        username="editor",
        hashed_password=hash_password("editor123"),
        role=Role.EDITOR,
    )
    db_session.add(u)
    db_session.flush()
    db_session.refresh(u)
    return u


@pytest.fixture
def runner_user(db_session: Session):
    from src.auth.models import User

    u = User(
        email="runner@test.com",
        username="runner",
        hashed_password=hash_password("runner123"),
        role=Role.RUNNER,
    )
    db_session.add(u)
    db_session.flush()
    db_session.refresh(u)
    return u


@pytest.fixture
def seed_repo_for_clone(db_session: Session, editor_user, working_clone: Path) -> Repository:
    """Insert a Repository row pointing at the working clone."""
    repo = Repository(
        name="save-loop-test",
        repo_type="git",
        git_url=str(working_clone.parent / "remote.git"),
        default_branch="main",
        local_path=str(working_clone),
        auto_sync=False,
        sync_interval_minutes=15,
        created_by=editor_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def local_repo(db_session: Session, editor_user, tmp_path: Path) -> Repository:
    """A `repo_type='local'` row — used by the rejection tests."""
    p = tmp_path / "local-only"
    p.mkdir()
    repo = Repository(
        name="local-only-test",
        repo_type="local",
        git_url=None,
        default_branch="main",
        local_path=str(p),
        auto_sync=False,
        sync_interval_minutes=15,
        created_by=editor_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


# ---------------------------------------------------------------------------
# service-layer tests
# ---------------------------------------------------------------------------


class TestServiceLayer:
    def test_status_clean_after_clone(self, working_clone: Path):
        snap = get_repo_status(str(working_clone))
        assert snap["is_dirty"] is False
        assert snap["current_branch"] == "main"
        assert snap["modified"] == []
        assert snap["untracked"] == []

    def test_status_modified_path_shows_up(self, working_clone: Path):
        (working_clone / "README.md").write_text("changed\n", encoding="utf-8")
        snap = get_repo_status(str(working_clone))
        assert snap["is_dirty"] is True
        assert "README.md" in snap["modified"]

    def test_status_untracked_path_shows_up(self, working_clone: Path):
        (working_clone / "fresh.robot").write_text("*** Test Cases ***\n", encoding="utf-8")
        snap = get_repo_status(str(working_clone))
        assert "fresh.robot" in snap["untracked"]

    def test_commit_records_user_identity(self, working_clone: Path):
        (working_clone / "new.robot").write_text("*** Test Cases ***\n", encoding="utf-8")
        result = commit_changes(
            str(working_clone),
            message="add new test",
            paths=None,
            author_name="Alice",
            author_email="alice@example.com",
        )
        assert result["commit_hash"]
        repo = Repo(str(working_clone))
        head = repo.head.commit
        assert head.author.name == "Alice"
        assert head.author.email == "alice@example.com"
        # Committer = author when set via `-c user.* …`.
        assert head.committer.email == "alice@example.com"

    def test_commit_with_no_changes_raises(self, working_clone: Path):
        with pytest.raises(GitOperationError) as excinfo:
            commit_changes(
                str(working_clone),
                "empty",
                paths=None,
                author_name="A",
                author_email="a@b.com",
            )
        assert excinfo.value.kind == "nothing_to_commit"

    def test_push_succeeds_when_fast_forward(self, working_clone: Path):
        (working_clone / "ff.robot").write_text("ff\n", encoding="utf-8")
        commit_changes(
            str(working_clone), "add ff",
            paths=None, author_name="A", author_email="a@b.com",
        )
        result = push_branch(str(working_clone))
        assert result["branch"] == "main"
        assert result["ahead_after"] == 0

    def test_push_raises_on_non_fast_forward(
        self, working_clone: Path, divergent_clone: Path,
    ):
        # divergent_clone pushes first — main moves on the remote.
        (divergent_clone / "from-other.robot").write_text("other\n", encoding="utf-8")
        other = Repo(divergent_clone)
        other.index.add(["from-other.robot"])
        other.git.update_environment(
            GIT_AUTHOR_NAME="other", GIT_AUTHOR_EMAIL="other@example.com",
            GIT_COMMITTER_NAME="other", GIT_COMMITTER_EMAIL="other@example.com",
        )
        other.git.commit("-m", "from other")
        other.git.push("origin", "main")

        # Now the primary clone makes its own commit and tries to push.
        (working_clone / "from-primary.robot").write_text("primary\n", encoding="utf-8")
        commit_changes(
            str(working_clone), "from primary",
            paths=None, author_name="P", author_email="p@example.com",
        )
        with pytest.raises(GitOperationError) as excinfo:
            push_branch(str(working_clone))
        assert excinfo.value.kind == "non_fast_forward"

    def test_publish_combined_succeeds(self, working_clone: Path):
        (working_clone / "publish.robot").write_text("ok\n", encoding="utf-8")
        result = publish_changes(
            str(working_clone), "publish",
            paths=None, author_name="A", author_email="a@b.com",
        )
        assert result["pushed"] is True
        assert result["conflict"] is False

    def test_publish_keeps_local_commit_on_push_conflict(
        self, working_clone: Path, divergent_clone: Path,
    ):
        # Make the remote diverge first.
        (divergent_clone / "rival.robot").write_text("rival\n", encoding="utf-8")
        other = Repo(divergent_clone)
        other.index.add(["rival.robot"])
        other.git.update_environment(
            GIT_AUTHOR_NAME="other", GIT_AUTHOR_EMAIL="other@example.com",
            GIT_COMMITTER_NAME="other", GIT_COMMITTER_EMAIL="other@example.com",
        )
        other.git.commit("-m", "rival")
        other.git.push("origin", "main")

        (working_clone / "ours.robot").write_text("ours\n", encoding="utf-8")
        with pytest.raises(GitOperationError) as excinfo:
            publish_changes(
                str(working_clone), "ours",
                paths=None, author_name="A", author_email="a@b.com",
            )
        e = excinfo.value
        assert e.kind == "non_fast_forward"
        # The local commit must STAY so the user doesn't lose work.
        assert hasattr(e, "commit_hash")
        # And HEAD on the working clone has indeed moved.
        repo = Repo(str(working_clone))
        head = repo.head.commit
        assert head.message.strip() == "ours"
        # The error carries the same hash as HEAD.
        assert e.commit_hash == head.hexsha


# ---------------------------------------------------------------------------
# router tests
# ---------------------------------------------------------------------------


class TestRouterStatus:
    def test_returns_status_for_authenticated_user(
        self, client, admin_user, seed_repo_for_clone, working_clone,
    ):
        (working_clone / "x.robot").write_text("x\n", encoding="utf-8")
        r = client.get(
            f"/api/v1/repos/{seed_repo_for_clone.id}/status",
            headers=auth_header(admin_user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_dirty"] is True
        assert "x.robot" in body["untracked"]

    def test_local_repo_returns_zeroed_status(
        self, client, admin_user, local_repo,
    ):
        r = client.get(
            f"/api/v1/repos/{local_repo.id}/status",
            headers=auth_header(admin_user),
        )
        assert r.status_code == 200
        assert r.json()["is_dirty"] is False


class TestRouterCommit:
    def test_commit_happy_path(
        self, client, editor_user, seed_repo_for_clone, working_clone,
    ):
        (working_clone / "ok.robot").write_text("ok\n", encoding="utf-8")
        r = client.post(
            f"/api/v1/repos/{seed_repo_for_clone.id}/commit",
            json={"message": "add ok"},
            headers=auth_header(editor_user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["message"] == "add ok"
        assert "ok.robot" in body["files"]
        # Identity propagated.
        head = Repo(str(working_clone)).head.commit
        assert head.author.email == editor_user.email

    def test_commit_with_no_changes_returns_400(
        self, client, editor_user, seed_repo_for_clone,
    ):
        r = client.post(
            f"/api/v1/repos/{seed_repo_for_clone.id}/commit",
            json={"message": "empty"},
            headers=auth_header(editor_user),
        )
        assert r.status_code == 400

    def test_runner_cannot_commit(
        self, client, runner_user, seed_repo_for_clone, working_clone,
    ):
        (working_clone / "blocked.robot").write_text("nope\n", encoding="utf-8")
        r = client.post(
            f"/api/v1/repos/{seed_repo_for_clone.id}/commit",
            json={"message": "blocked"},
            headers=auth_header(runner_user),
        )
        assert r.status_code == 403

    def test_local_repo_returns_400(
        self, client, editor_user, local_repo,
    ):
        r = client.post(
            f"/api/v1/repos/{local_repo.id}/commit",
            json={"message": "no remote"},
            headers=auth_header(editor_user),
        )
        assert r.status_code == 400


class TestRouterPublish:
    def test_publish_happy_path(
        self, client, editor_user, seed_repo_for_clone, working_clone,
    ):
        (working_clone / "pub.robot").write_text("pub\n", encoding="utf-8")
        r = client.post(
            f"/api/v1/repos/{seed_repo_for_clone.id}/publish",
            json={"message": "publish"},
            headers=auth_header(editor_user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pushed"] is True
        assert body["conflict"] is False
        assert body["commit_hash"]

    def test_publish_returns_409_on_non_fast_forward(
        self, client, editor_user, seed_repo_for_clone,
        working_clone, divergent_clone,
    ):
        # Remote diverges first.
        (divergent_clone / "rival.robot").write_text("rival\n", encoding="utf-8")
        other = Repo(divergent_clone)
        other.index.add(["rival.robot"])
        other.git.update_environment(
            GIT_AUTHOR_NAME="other", GIT_AUTHOR_EMAIL="other@example.com",
            GIT_COMMITTER_NAME="other", GIT_COMMITTER_EMAIL="other@example.com",
        )
        other.git.commit("-m", "rival")
        other.git.push("origin", "main")

        (working_clone / "ours.robot").write_text("ours\n", encoding="utf-8")
        r = client.post(
            f"/api/v1/repos/{seed_repo_for_clone.id}/publish",
            json={"message": "ours"},
            headers=auth_header(editor_user),
        )
        assert r.status_code == 409, r.text
        body = r.json()
        # FastAPI nests our payload under "detail" for HTTPException.
        detail = body["detail"]
        assert detail["conflict"] is True
        assert detail["pushed"] is False
        assert detail["commit_hash"]
