"""Story W.8 — idle-recording-session auto-abort + audit."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.audit.models import AuditLog
from src.auth.models import User
from src.auth.retention_cleanup import abort_idle_recording_sessions
from src.auth.service import hash_password
from src.recording.models import RecordingSession, RecordingStatus
from src.repos.models import Repository


def _mk_user(db: Session) -> User:
    u = User(
        email="rec-owner@test.com",
        username="rec-owner",
        hashed_password=hash_password("pw"),
        role="editor",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _mk_repo(db: Session, owner: User) -> Repository:
    r = Repository(
        name="rec-repo",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path="/tmp/rec-repo",
        created_by=owner.id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _mk_session(
    db: Session,
    *,
    owner: User,
    repo: Repository,
    status: str,
    started_minutes_ago: int,
) -> RecordingSession:
    s = RecordingSession(
        repository_id=repo.id,
        status=status,
        source="playwright",
        triggered_by=owner.id,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(minutes=started_minutes_ago),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


class TestAbortIdleRecordingSessions:
    def test_aborts_idle_over_threshold(self, db_session: Session) -> None:
        owner = _mk_user(db_session)
        repo = _mk_repo(db_session, owner)
        idle = _mk_session(
            db_session,
            owner=owner, repo=repo,
            status=RecordingStatus.RECORDING,
            started_minutes_ago=45,  # well beyond 30-min cutoff
        )

        aborted = abort_idle_recording_sessions(db_session)
        assert aborted == 1

        db_session.expire_all()
        refreshed = db_session.get(RecordingSession, idle.id)
        assert refreshed is not None
        assert refreshed.status == RecordingStatus.CANCELLED
        assert refreshed.finished_at is not None

        audits = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "recording.session.aborted")
            .all()
        )
        assert len(audits) == 1
        detail = json.loads(audits[0].detail)
        assert detail["reason"] == "idle_timeout"
        assert detail["session_id"] == idle.id

    def test_leaves_fresh_sessions_alone(self, db_session: Session) -> None:
        owner = _mk_user(db_session)
        repo = _mk_repo(db_session, owner)
        _mk_session(
            db_session,
            owner=owner, repo=repo,
            status=RecordingStatus.RECORDING,
            started_minutes_ago=10,  # well under cutoff
        )

        aborted = abort_idle_recording_sessions(db_session)
        assert aborted == 0

    def test_ignores_non_recording_status(self, db_session: Session) -> None:
        owner = _mk_user(db_session)
        repo = _mk_repo(db_session, owner)
        _mk_session(
            db_session,
            owner=owner, repo=repo,
            status=RecordingStatus.COMPLETED,
            started_minutes_ago=120,
        )

        aborted = abort_idle_recording_sessions(db_session)
        assert aborted == 0

    def test_no_sessions_returns_zero(self, db_session: Session) -> None:
        aborted = abort_idle_recording_sessions(db_session)
        assert aborted == 0

    def test_multiple_idle_sessions_all_aborted(self, db_session: Session) -> None:
        owner = _mk_user(db_session)
        repo = _mk_repo(db_session, owner)
        _mk_session(
            db_session, owner=owner, repo=repo,
            status=RecordingStatus.RECORDING, started_minutes_ago=40,
        )
        _mk_session(
            db_session, owner=owner, repo=repo,
            status=RecordingStatus.RECORDING, started_minutes_ago=90,
        )
        # Plus a fresh one that must NOT be aborted.
        fresh = _mk_session(
            db_session, owner=owner, repo=repo,
            status=RecordingStatus.RECORDING, started_minutes_ago=5,
        )

        aborted = abort_idle_recording_sessions(db_session)
        assert aborted == 2

        db_session.expire_all()
        fresh_refreshed = db_session.get(RecordingSession, fresh.id)
        assert fresh_refreshed is not None
        assert fresh_refreshed.status == RecordingStatus.RECORDING
