"""Tests for recording service functions."""

import json

import pytest
from sqlalchemy.orm import Session

from src.recording.models import RecordingSession, RecordingStatus, RecordingSource
from src.recording.schemas import RecordingCreate
from src.recording.service import (
    append_event,
    cancel_recording,
    complete_recording,
    create_recording,
    delete_recording,
    fail_recording,
    get_recording,
    list_recordings,
    start_recording,
    stop_recording,
)
from src.repos.models import Repository


@pytest.fixture
def repo(db_session: Session, admin_user):
    """Create a repository for recording service tests."""
    repository = Repository(
        name="svc-test-repo",
        git_url="https://github.com/test/svc-repo.git",
        default_branch="main",
        local_path="/tmp/repos/svc-repo",
        created_by=admin_user.id,
    )
    db_session.add(repository)
    db_session.flush()
    db_session.refresh(repository)
    return repository


def _make_create(repo_id: int, **kwargs) -> RecordingCreate:
    defaults = {
        "repository_id": repo_id,
        "source": RecordingSource.PLAYWRIGHT,
        "target_library": "Browser",
    }
    defaults.update(kwargs)
    return RecordingCreate(**defaults)


class TestRecordingService:

    def test_create_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        assert rec.id is not None
        assert rec.status == RecordingStatus.PENDING
        assert rec.repository_id == repo.id
        assert rec.triggered_by == admin_user.id

    def test_get_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        found = get_recording(db_session, rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_recording_not_found(self, db_session):
        assert get_recording(db_session, 99999) is None

    def test_list_recordings(self, db_session, admin_user, repo):
        create_recording(db_session, _make_create(repo.id), admin_user.id)
        create_recording(db_session, _make_create(repo.id), admin_user.id)
        items, total = list_recordings(db_session)
        assert total == 2
        assert len(items) == 2

    def test_list_filter_by_repo(self, db_session, admin_user, repo):
        repo2 = Repository(
            name="other-svc",
            git_url="https://x.com/other.git",
            default_branch="main",
            local_path="/tmp/repos/other-svc",
            created_by=admin_user.id,
        )
        db_session.add(repo2)
        db_session.flush()

        create_recording(db_session, _make_create(repo.id), admin_user.id)
        create_recording(db_session, _make_create(repo2.id), admin_user.id)

        items, total = list_recordings(db_session, repository_id=repo.id)
        assert total == 1

    def test_start_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        start_recording(db_session, rec)
        assert rec.status == RecordingStatus.RECORDING
        assert rec.started_at is not None

    def test_append_event(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        start_recording(db_session, rec)

        append_event(db_session, rec, {"event_type": "click", "selector": "//btn"})
        assert rec.event_count == 1
        events = json.loads(rec.events_json)
        assert len(events) == 1
        assert events[0]["event_type"] == "click"

    def test_append_multiple_events(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        start_recording(db_session, rec)

        for i in range(5):
            append_event(db_session, rec, {"event_type": "click", "selector": f"//el[{i}]"})

        assert rec.event_count == 5

    def test_stop_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        start_recording(db_session, rec)
        stop_recording(db_session, rec)
        assert rec.status == RecordingStatus.PROCESSING
        assert rec.finished_at is not None
        assert rec.duration_seconds is not None

    def test_complete_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        complete_recording(db_session, rec, generated_robot="*** Test Cases ***\nTest\n    Log    ok")
        assert rec.status == RecordingStatus.COMPLETED
        assert "*** Test Cases ***" in rec.generated_robot

    def test_fail_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        fail_recording(db_session, rec, "Something went wrong")
        assert rec.status == RecordingStatus.FAILED
        assert rec.error_message == "Something went wrong"

    def test_cancel_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        start_recording(db_session, rec)
        cancel_recording(db_session, rec)
        assert rec.status == RecordingStatus.CANCELLED
        assert rec.finished_at is not None

    def test_delete_recording(self, db_session, admin_user, repo):
        rec = create_recording(db_session, _make_create(repo.id), admin_user.id)
        rec_id = rec.id
        delete_recording(db_session, rec)
        assert get_recording(db_session, rec_id) is None
