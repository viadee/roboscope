"""Story W.2 — SSE command stream + in-process FIFO queue.

Covers the queue module directly (unit-style) + a streaming smoke test
that hits the endpoint, enqueues two commands from the test thread,
finalizes, and asserts the SSE body contains both events + the end
sentinel.
"""

from __future__ import annotations

import queue as _queue
import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.recording.models import RecordingSession, RecordingStatus
from src.recording.selector_schema import RecordedCommand, SelectorCandidate
from src.recording.v2_command_queue import (
    enqueue_command,
    finalize_session,
    iterate_commands,
    pending_count,
    register_session,
    tear_down_session,
)
from src.repos.models import Repository
from tests.conftest import auth_header


def _mk_cmd(keyword: str = "Click", index: int = 0) -> RecordedCommand:
    return RecordedCommand(
        index=index,
        keyword=keyword,
        selector_candidates=[
            SelectorCandidate(strategy="testid", value=f"[data-testid=\"{index}\"]", quality_score=95)
        ],
    )


class TestQueueModule:
    def test_enqueue_before_register_returns_false(self) -> None:
        result = enqueue_command(9999, _mk_cmd())
        assert result is False

    def test_register_then_enqueue_and_drain(self) -> None:
        sid = 10001
        register_session(sid)
        assert enqueue_command(sid, _mk_cmd(keyword="Click", index=0)) is True
        assert enqueue_command(sid, _mk_cmd(keyword="Type Text", index=1)) is True
        assert pending_count(sid) == 2

        # iterate_commands blocks until end-sentinel; run in another thread.
        received: list[RecordedCommand] = []

        def consume():
            for c in iterate_commands(sid, poll_timeout_s=0.05):
                received.append(c)

        t = threading.Thread(target=consume)
        t.start()

        # Let the consumer drain, then close the stream.
        time.sleep(0.2)
        finalize_session(sid)
        t.join(timeout=2)

        assert not t.is_alive()
        assert len(received) == 2
        assert received[0].keyword == "Click"
        assert received[1].keyword == "Type Text"

        tear_down_session(sid)
        assert pending_count(sid) == 0

    def test_tear_down_drops_registry(self) -> None:
        sid = 10002
        register_session(sid)
        enqueue_command(sid, _mk_cmd())
        tear_down_session(sid)
        # Further enqueues fail — the queue is gone.
        assert enqueue_command(sid, _mk_cmd()) is False

    def test_iterate_on_unknown_session_returns_nothing(self) -> None:
        received = list(iterate_commands(99999, poll_timeout_s=0.01))
        assert received == []


def _mk_repo_and_session(
    db: Session, owner: User
) -> tuple[Repository, RecordingSession]:
    r = Repository(
        name=f"cmdstream-{owner.id}",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path="/tmp/cmdstream",
        created_by=owner.id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)

    s = RecordingSession(
        repository_id=r.id,
        status=RecordingStatus.RECORDING,
        source="playwright",
        triggered_by=owner.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return r, s


class TestSseEndpoint:
    def test_non_owner_forbidden(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        from src.auth.service import hash_password
        owner = User(
            email="owner-sse@test.com", username="owner-sse",
            hashed_password=hash_password("pw"), role="editor",
        )
        db_session.add(owner)
        db_session.commit()
        db_session.refresh(owner)

        _, session = _mk_repo_and_session(db_session, owner)

        other = User(
            email="other-sse@test.com", username="other-sse",
            hashed_password=hash_password("pw"), role="editor",
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        resp = client.get(
            f"/api/v1/recordings/sessions/{session.id}/commands",
            headers=auth_header(other),
        )
        assert resp.status_code == 403

    def test_stream_yields_enqueued_commands_and_end_event(
        self, client: TestClient, db_session: Session, admin_user: User
    ) -> None:
        _, session = _mk_repo_and_session(db_session, admin_user)
        register_session(session.id)

        # Producer thread enqueues + finalizes while the request is pending.
        def produce():
            time.sleep(0.1)  # let the stream handler subscribe first
            enqueue_command(session.id, _mk_cmd(keyword="Go To", index=0))
            enqueue_command(session.id, _mk_cmd(keyword="Click", index=1))
            time.sleep(0.05)
            finalize_session(session.id)

        t = threading.Thread(target=produce)
        t.start()

        # TestClient streams the response body; read everything.
        with client.stream(
            "GET",
            f"/api/v1/recordings/sessions/{session.id}/commands",
            headers=auth_header(admin_user),
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = "".join(chunk for chunk in resp.iter_text())

        t.join(timeout=5)

        assert 'event: command' in body
        assert '"keyword": "Go To"' in body or '"keyword":"Go To"' in body
        assert '"keyword": "Click"' in body or '"keyword":"Click"' in body
        assert 'event: end' in body

        tear_down_session(session.id)

    def test_404_on_unknown_session(
        self, client: TestClient, admin_user: User
    ) -> None:
        resp = client.get(
            "/api/v1/recordings/sessions/999999/commands",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
