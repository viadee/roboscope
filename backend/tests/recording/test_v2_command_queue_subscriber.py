"""H2 regression: a recording session's SSE queue allows at most one
subscriber. Two consumers would split the single SimpleQueue, so each tab
would see only part of the recording."""

from __future__ import annotations

from src.recording.v2_command_queue import (
    register_session,
    release_subscriber,
    tear_down_session,
    try_acquire_subscriber,
)


def test_single_subscriber_enforced() -> None:
    sid = 990001
    register_session(sid)
    try:
        assert try_acquire_subscriber(sid) is True   # first consumer wins
        assert try_acquire_subscriber(sid) is False  # second is rejected (→409)
        release_subscriber(sid)
        assert try_acquire_subscriber(sid) is True    # reconnect after release
        release_subscriber(sid)
    finally:
        tear_down_session(sid)


def test_no_queue_allows_acquire() -> None:
    # An ended / never-registered session has no queue → acquire returns True
    # and iterate_events simply yields nothing (clean empty stream, not 409).
    assert try_acquire_subscriber(424242) is True
