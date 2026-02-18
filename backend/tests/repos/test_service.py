"""Tests for repos service (CRUD operations)."""

import pytest
from src.repos.models import Repository
from src.repos.service import (
    create_repository,
    delete_repository,
    get_repository,
    get_repository_by_name,
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
