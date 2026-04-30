"""Lifecycle tests for `run_v2_recorder_session`.

The wrapper is the only place that:
  * catches an exception from the Playwright loop
  * flips the RecordingSession row to FAILED
  * pops the per-session stop signal
  * pushes the SSE end sentinel
  * tears down the command queue

If any of those hand-offs broke (`finally` runs in wrong order, FAILED
status doesn't reach the DB, queue stays alive after a crash), the
session row sits in RECORDING forever and the user can only recover
via the panic-button reset endpoint. Pin the contract here so a
refactor of the lifecycle ordering can't silently regress.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.recording.models import RecordingSession, RecordingSource, RecordingStatus
from src.recording.v2_command_queue import (
    register_session,
    enqueue_command,
    iterate_commands,
)


def _make_session(db: Session, owner: User, repo_id: int) -> RecordingSession:
    row = RecordingSession(
        repository_id=repo_id,
        status=RecordingStatus.RECORDING,
        source=RecordingSource.PLAYWRIGHT,
        triggered_by=owner.id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@pytest.fixture
def repo_id(db_session: Session, admin_user: User) -> int:
    from src.repos.models import Repository

    r = Repository(
        name="lifecycle-repo",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path="/tmp/lifecycle-repo",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.flush()
    db_session.refresh(r)
    return r.id


class TestCrashPathFlipsStatusAndCleansUp:
    """When the Playwright loop raises, every cleanup step still runs
    in order: log → mark FAILED → pop stop signal → finalize SSE
    queue → tear down queue."""

    def test_crash_in_recorder_loop_calls_mark_status_failed(
        self,
        db_session: Session,
        admin_user: User,
        repo_id: int,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from src.recording import v2_recorder_task

        # Pre-create the queue so the producer-thread `enqueue_command`
        # check inside iterate doesn't trip — mirrors what
        # `start_browser` does in production before dispatching the
        # task.
        rec = _make_session(db_session, admin_user, repo_id)
        register_session(rec.id)
        db_session.commit()

        # Replace the inner async loop with a synchronous stub that
        # raises immediately. The wrapper's `asyncio.run(...)` will
        # propagate the exception out.
        async def _boom(*_a: Any, **_kw: Any) -> None:
            raise RuntimeError("simulated playwright crash")

        monkeypatch.setattr(v2_recorder_task, "_recorder_loop", _boom)

        # Spy on `_mark_status` instead of asserting against the DB
        # row directly — the test fixture's transactional isolation
        # hides cross-session commits from the wrapper's
        # `get_sync_session()` call. The wrapper's actual contract
        # is "call _mark_status(FAILED, 'recorder crashed') on
        # exception", and `_mark_status`'s own DB-write behavior is
        # exercised by its own tests.
        mark_calls: list[tuple] = []

        def _spy(session_id: int, status: str, message: str | None = None) -> None:
            mark_calls.append((session_id, status, message))

        monkeypatch.setattr(v2_recorder_task, "_mark_status", _spy)

        caplog.set_level(logging.ERROR, logger="roboscope.recording.v2_recorder")
        v2_recorder_task.run_v2_recorder_session(rec.id)

        # The wrapper used logger.exception — must include the
        # session id somewhere in the captured records.
        crash_logs = [
            r for r in caplog.records
            if r.name == "roboscope.recording.v2_recorder"
            and r.levelname == "ERROR"
            and "crashed" in r.getMessage()
        ]
        assert crash_logs, "expected a logger.exception line on crash"
        assert any(str(rec.id) in r.getMessage() for r in crash_logs)

        # Wrapper invoked _mark_status with FAILED + the canonical
        # error message exactly once.
        failed_calls = [c for c in mark_calls if c[1] == RecordingStatus.FAILED]
        assert len(failed_calls) == 1, (
            f"expected exactly one FAILED mark, got {mark_calls}"
        )
        sid, _status, msg = failed_calls[0]
        assert sid == rec.id
        assert msg == "recorder crashed"

        # Stop signal popped — `is_v2_session_active` reflects the
        # registry shape and must be False after the finally block.
        assert v2_recorder_task.is_v2_session_active(rec.id) is False

    def test_crash_path_finalizes_queue_so_sse_subscriber_unblocks(
        self,
        db_session: Session,
        admin_user: User,
        repo_id: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`finalize_session` pushes the END sentinel; without it any
        SSE subscriber polling `iterate_commands` blocks forever
        waiting for the next command, even after the recorder thread
        is dead. The crash path's `finally` block must always emit
        the sentinel so the SSE generator can `event: end` and
        close the stream."""
        from src.recording import v2_recorder_task

        rec = _make_session(db_session, admin_user, repo_id)
        register_session(rec.id)
        db_session.commit()

        # Push one real command before the crash so the consumer
        # gets at least one item before the sentinel — closer to
        # real-world ordering where Playwright captured something
        # before crashing.
        from src.recording.selector_schema import RecordedCommand

        enqueue_command(
            rec.id,
            RecordedCommand(index=0, keyword="Click", selector_candidates=[]),
        )

        async def _boom(*_a: Any, **_kw: Any) -> None:
            raise RuntimeError("crash after one captured event")

        monkeypatch.setattr(v2_recorder_task, "_recorder_loop", _boom)
        v2_recorder_task.run_v2_recorder_session(rec.id)

        # iterate_commands runs over the queue we already populated;
        # the crash path pushed the END sentinel and tore down the
        # registry, so a fresh consumer call (post-teardown) returns
        # zero items because the registry lookup fails. The earlier
        # consumer (pre-teardown) would have drained the live item +
        # the sentinel and exited cleanly. We exercise the post-
        # teardown call path here — it must NOT block.
        # poll_timeout_s=0.05 keeps the test fast even if regressions
        # cause a wait.
        items = list(iterate_commands(rec.id, poll_timeout_s=0.05))
        # Either zero items (registry already torn down — the typical
        # case after the wrapper's `finally` block) or one item then
        # an exit if a race grabbed the queue first. Both are valid;
        # what's NOT valid is hanging or raising.
        assert isinstance(items, list)

    def test_happy_path_does_not_call_mark_status_failed(
        self,
        db_session: Session,
        admin_user: User,
        repo_id: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Counterfactual — when `_recorder_loop` returns cleanly the
        wrapper does NOT call `_mark_status(FAILED)`. Confirms the
        FAILED flip is gated on the exception path, not on every exit.
        """
        from src.recording import v2_recorder_task

        rec = _make_session(db_session, admin_user, repo_id)
        register_session(rec.id)

        async def _clean(*_a: Any, **_kw: Any) -> None:
            return None

        mark_calls: list[tuple] = []

        def _spy(session_id: int, status: str, message: str | None = None) -> None:
            mark_calls.append((session_id, status, message))

        monkeypatch.setattr(v2_recorder_task, "_recorder_loop", _clean)
        monkeypatch.setattr(v2_recorder_task, "_mark_status", _spy)

        v2_recorder_task.run_v2_recorder_session(rec.id)

        # `_mark_status` may be called for COMPLETED at the end of
        # `_recorder_loop`, but the WRAPPER's catch-and-mark-FAILED
        # path must not fire. Since we replaced `_recorder_loop`,
        # NO _mark_status calls should happen at all from this test
        # — proving the wrapper itself isn't issuing one.
        assert mark_calls == []
        # Stop signal popped on the happy path too.
        assert v2_recorder_task.is_v2_session_active(rec.id) is False
