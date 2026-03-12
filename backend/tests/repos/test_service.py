"""Tests for repos service (CRUD operations)."""

import pytest
from src.repos.models import Repository
from unittest.mock import MagicMock, patch

from src.repos.service import (
    checkout_branch,
    create_repository,
    delete_repository,
    get_current_branch,
    get_repository,
    get_repository_by_name,
    list_branches,
    list_repositories,
    update_repository,
)
from src.repos.schemas import RepoCreate, RepoUpdate


def _make_repo(user_id: int, **overrides) -> Repository:
    """Helper to build a Repository instance with sensible defaults."""
    defaults = {
        "name": "test-repo",
        "git_url": "https://github.com/org/test-repo.git",
        "default_branch": "main",
        "local_path": "/tmp/workspace/test-repo",
        "auto_sync": True,
        "sync_interval_minutes": 15,
        "created_by": user_id,
    }
    defaults.update(overrides)
    return Repository(**defaults)


class TestListRepositories:
    def test_list_empty(self, db_session):
        repos = list_repositories(db_session)
        assert repos == []

    def test_list_with_repos(self, db_session, admin_user):
        repo_a = _make_repo(admin_user.id, name="alpha-repo")
        repo_b = _make_repo(admin_user.id, name="beta-repo")
        db_session.add_all([repo_b, repo_a])
        db_session.flush()

        repos = list_repositories(db_session)
        assert len(repos) == 2
        # Results are ordered by name
        assert repos[0].name == "alpha-repo"
        assert repos[1].name == "beta-repo"


class TestGetRepository:
    def test_get_by_id_found(self, db_session, admin_user):
        repo = _make_repo(admin_user.id, name="find-me")
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        result = get_repository(db_session, repo.id)
        assert result is not None
        assert result.id == repo.id
        assert result.name == "find-me"

    def test_get_by_id_not_found(self, db_session):
        result = get_repository(db_session, 99999)
        assert result is None

    def test_get_by_name_found(self, db_session, admin_user):
        repo = _make_repo(admin_user.id, name="named-repo")
        db_session.add(repo)
        db_session.flush()

        result = get_repository_by_name(db_session, "named-repo")
        assert result is not None
        assert result.name == "named-repo"

    def test_get_by_name_not_found(self, db_session):
        result = get_repository_by_name(db_session, "nonexistent")
        assert result is None


class TestCreateRepository:
    def test_create(self, db_session, admin_user):
        data = RepoCreate(
            name="new-repo",
            git_url="https://github.com/org/new-repo.git",
            default_branch="develop",
            auto_sync=False,
            sync_interval_minutes=30,
        )
        repo = create_repository(db_session, data, admin_user.id)

        assert repo.id is not None
        assert repo.name == "new-repo"
        assert repo.git_url == "https://github.com/org/new-repo.git"
        assert repo.default_branch == "develop"
        assert repo.auto_sync is False
        assert repo.sync_interval_minutes == 30
        assert repo.created_by == admin_user.id
        assert "new-repo" in repo.local_path

    def test_create_with_defaults(self, db_session, admin_user):
        data = RepoCreate(
            name="default-repo",
            git_url="https://github.com/org/default-repo.git",
        )
        repo = create_repository(db_session, data, admin_user.id)

        assert repo.default_branch == "main"
        assert repo.auto_sync is True
        assert repo.sync_interval_minutes == 15


class TestUpdateRepository:
    def test_update_partial(self, db_session, admin_user):
        repo = _make_repo(admin_user.id, name="update-me")
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        data = RepoUpdate(auto_sync=False, sync_interval_minutes=60)
        updated = update_repository(db_session, repo, data)

        assert updated.auto_sync is False
        assert updated.sync_interval_minutes == 60
        # Unchanged fields remain the same
        assert updated.name == "update-me"
        assert updated.default_branch == "main"

    def test_update_name(self, db_session, admin_user):
        repo = _make_repo(admin_user.id, name="old-name")
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        data = RepoUpdate(name="new-name")
        updated = update_repository(db_session, repo, data)

        assert updated.name == "new-name"

    def test_update_no_fields(self, db_session, admin_user):
        """Updating with no fields set should be a no-op."""
        repo = _make_repo(admin_user.id, name="no-change")
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)

        data = RepoUpdate()
        updated = update_repository(db_session, repo, data)

        assert updated.name == "no-change"


class TestDeleteRepository:
    def test_delete(self, db_session, admin_user):
        repo = _make_repo(admin_user.id, name="delete-me")
        db_session.add(repo)
        db_session.flush()
        db_session.refresh(repo)
        repo_id = repo.id

        delete_repository(db_session, repo)

        result = get_repository(db_session, repo_id)
        assert result is None


# ---------------------------------------------------------------------------
# Branch operations (mocking git.Repo)
# ---------------------------------------------------------------------------


def _make_git_ref(name: str) -> MagicMock:
    """Create a mock git reference."""
    ref = MagicMock()
    ref.name = name
    return ref


class TestListBranches:
    @patch("git.Repo")
    def test_list_branches_returns_local_and_remote(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.head.is_detached = False
        mock_repo.references = [
            _make_git_ref("main"),
            _make_git_ref("develop"),
            _make_git_ref("origin/main"),
            _make_git_ref("origin/feature-x"),
        ]
        mock_repo_cls.return_value = mock_repo

        result = list_branches("/tmp/repo")

        names = [b["name"] for b in result]
        assert "main" in names
        assert "develop" in names
        assert "feature-x" in names
        # "origin/main" should be deduped to "main"
        assert names.count("main") == 1

    @patch("git.Repo")
    def test_list_branches_marks_active(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "develop"
        mock_repo.head.is_detached = False
        mock_repo.references = [
            _make_git_ref("main"),
            _make_git_ref("develop"),
        ]
        mock_repo_cls.return_value = mock_repo

        result = list_branches("/tmp/repo")

        active = [b for b in result if b["is_active"]]
        assert len(active) == 1
        assert active[0]["name"] == "develop"

    @patch("git.Repo")
    def test_list_branches_detached_head(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.head.is_detached = True
        mock_repo.references = [_make_git_ref("main")]
        mock_repo_cls.return_value = mock_repo

        result = list_branches("/tmp/repo")

        # No branch should be active when HEAD is detached
        assert all(not b["is_active"] for b in result)

    @patch("git.Repo")
    def test_list_branches_filters_HEAD(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.head.is_detached = False
        mock_repo.references = [
            _make_git_ref("main"),
            _make_git_ref("HEAD"),
        ]
        mock_repo_cls.return_value = mock_repo

        result = list_branches("/tmp/repo")

        names = [b["name"] for b in result]
        assert "HEAD" not in names

    @patch("git.Repo")
    def test_list_branches_invalid_repo_returns_empty(self, mock_repo_cls):
        from git import InvalidGitRepositoryError

        mock_repo_cls.side_effect = InvalidGitRepositoryError("/tmp/bad")

        result = list_branches("/tmp/bad")

        assert result == []


class TestGetCurrentBranch:
    @patch("git.Repo")
    def test_get_current_branch_returns_name(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "feature-branch"
        mock_repo_cls.return_value = mock_repo

        result = get_current_branch("/tmp/repo")

        assert result == "feature-branch"

    @patch("git.Repo")
    def test_get_current_branch_detached_returns_none(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.head.is_detached = True
        mock_repo_cls.return_value = mock_repo

        result = get_current_branch("/tmp/repo")

        assert result is None

    @patch("git.Repo")
    def test_get_current_branch_invalid_repo_returns_none(self, mock_repo_cls):
        from git import InvalidGitRepositoryError

        mock_repo_cls.side_effect = InvalidGitRepositoryError("/tmp/bad")

        result = get_current_branch("/tmp/bad")

        assert result is None


class TestCheckoutBranch:
    @patch("git.Repo")
    def test_checkout_success(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        result = checkout_branch("/tmp/repo", "develop")

        mock_repo.git.checkout.assert_called_once_with("develop")
        assert result == "checked out develop"

    @patch("git.Repo")
    def test_checkout_error(self, mock_repo_cls):
        from git import GitCommandError

        mock_repo = MagicMock()
        mock_repo.git.checkout.side_effect = GitCommandError(
            "checkout", 128, "pathspec 'nope' did not match"
        )
        mock_repo_cls.return_value = mock_repo

        result = checkout_branch("/tmp/repo", "nope")

        assert result.startswith("error:")
