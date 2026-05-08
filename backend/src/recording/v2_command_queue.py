"""Story W.2 — in-process per-session FIFO for Recorder v2 commands.

A RecordedCommand is produced by the capture layer (injected JS for
web, pywinauto hook for Windows) and consumed by the SSE endpoint that
streams it to the browser. Because one session has exactly one live
viewer (AR-10 + AR-3 "single subscriber"), a plain FIFO per session is
enough — no pub/sub, no broker.

The registry is process-local. It assumes the same Python process hosts
both the capture thread and the HTTP handler — which is the AR-2 decision
("in-process with the backend, not a sidecar"). When a session ends we
delete the queue so late subscribers can distinguish "still running,
nothing to send" (queue present, idle) from "session over" (queue gone).

No locking: the stdlib `queue.SimpleQueue` is thread-safe for the
enqueue / dequeue contract we use here.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass
from threading import Lock
from typing import Iterator

from src.recording.selector_schema import RecordedCommand


# Sentinel pushed onto the queue to signal "session completed — close
# the stream". Using a distinct class is clearer than a string.
class _End:
    pass


_END_SENTINEL = _End()


@dataclass
class _SessionQueue:
    q: queue.SimpleQueue


_registry: dict[int, _SessionQueue] = {}
_registry_lock = Lock()


def register_session(session_id: int) -> None:
    """Called when a v2 session is created (POST /sessions)."""
    with _registry_lock:
        if session_id not in _registry:
            _registry[session_id] = _SessionQueue(q=queue.SimpleQueue())


def enqueue_command(session_id: int, command: RecordedCommand) -> bool:
    """Push one command onto the session's queue. Returns False if the
    session's queue has been torn down already (late producer)."""
    with _registry_lock:
        sq = _registry.get(session_id)
    if sq is None:
        return False
    sq.q.put(command)
    return True


def finalize_session(session_id: int) -> None:
    """Push the end sentinel so any blocked consumer wakes up and exits."""
    with _registry_lock:
        sq = _registry.get(session_id)
    if sq is None:
        return
    sq.q.put(_END_SENTINEL)


def tear_down_session(session_id: int) -> None:
    """Remove the queue entry — called after the consumer has drained."""
    with _registry_lock:
        _registry.pop(session_id, None)


def iterate_commands(
    session_id: int, *, poll_timeout_s: float = 0.5
) -> Iterator[RecordedCommand]:
    """Yield commands from the session queue until the end-sentinel is
    seen. Used by the SSE endpoint's generator. Each `get(timeout=…)` call
    means this blocks for up to `poll_timeout_s` before checking again.
    """
    with _registry_lock:
        sq = _registry.get(session_id)
    if sq is None:
        return
    while True:
        try:
            item = sq.q.get(timeout=poll_timeout_s)
        except queue.Empty:
            continue
        if isinstance(item, _End):
            return
        assert isinstance(item, RecordedCommand)
        yield item


def pending_count(session_id: int) -> int:
    """Test-only helper: how many commands are queued without blocking."""
    with _registry_lock:
        sq = _registry.get(session_id)
    return sq.q.qsize() if sq else 0
