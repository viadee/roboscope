"""Story W.2 / RECORDER-VIS-1 — per-session FIFO for Recorder v2.

A v2 session emits two kinds of payloads to its single live subscriber:

  - **`RecordedCommand`** — produced by the capture layer (injected JS
    for web, pywinauto hook for Windows) when the user interacts with
    the recorded page. The original Story W.2 contract.
  - **`LifecycleEvent`** — produced by the recorder task at well-defined
    phase boundaries (browser_starting, browser_ready,
    browser_crashed, browser_restarting). Story RECORDER-VIS-1, so the
    Live view can show whether Chromium is starting, ready, or
    crashed instead of staring at a silent "connecting…" badge.

Both ride the same FIFO so the SSE consumer keeps the natural ordering
(a `browser_ready` arrives after the last late-fire `command` from a
previous restart's tail, etc.).

The registry is process-local (AR-2 — in-process with the backend,
not a sidecar). When a session ends we delete the queue so late
subscribers can distinguish "still running, nothing to send" (queue
present, idle) from "session over" (queue gone).
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Iterator, Literal

from src.recording.selector_schema import RecordedCommand


LifecyclePhase = Literal[
    "browser_starting",
    "browser_ready",
    "browser_crashed",
    "browser_restarting",
]


@dataclass(frozen=True)
class LifecycleEvent:
    """A point-in-time signal about the recorder task / browser state.

    `phase` is the discriminator the frontend pill renders. `message`
    is optional human-readable detail for the crashed/error variants
    (e.g., the exception message). `ts` is epoch seconds, captured at
    enqueue time so consumers can render uptime relative to wall clock
    without needing a backend round-trip per second.
    """

    phase: LifecyclePhase
    ts: float = field(default_factory=time.time)
    message: str | None = None


# Sentinel pushed onto the queue to signal "session completed — close
# the stream". Using a distinct class is clearer than a string.
class _End:
    pass


_END_SENTINEL = _End()

_QueueItem = RecordedCommand | LifecycleEvent | _End


@dataclass
class _SessionQueue:
    q: queue.SimpleQueue


_registry: dict[int, _SessionQueue] = {}
_registry_lock = Lock()


def register_session(session_id: int) -> None:
    """Called when a v2 session is created (POST /sessions). Idempotent —
    a no-op when the session id already has a queue (restart path)."""
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


def enqueue_lifecycle(session_id: int, event: LifecycleEvent) -> bool:
    """Push one lifecycle event onto the session's queue. Returns False
    if the session's queue has been torn down already."""
    with _registry_lock:
        sq = _registry.get(session_id)
    if sq is None:
        return False
    sq.q.put(event)
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


def iterate_events(
    session_id: int, *, poll_timeout_s: float = 0.5
) -> Iterator[RecordedCommand | LifecycleEvent]:
    """Yield the heterogeneous stream of commands + lifecycle events for
    one session, terminating on the end sentinel.

    Used by the SSE endpoint's generator. Each `get(timeout=…)` call
    blocks for up to `poll_timeout_s` before checking again, which is
    the same trade-off the original `iterate_commands` used.
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
        # mypy-friendly narrowing: queue carries the union above.
        yield item  # type: ignore[misc]


def iterate_commands(
    session_id: int, *, poll_timeout_s: float = 0.5
) -> Iterator[RecordedCommand]:
    """Backward-compatible filter over `iterate_events` that yields only
    `RecordedCommand` items. Kept so older tests that assume a
    command-only iterator don't need to learn the new union type.
    """
    for item in iterate_events(session_id, poll_timeout_s=poll_timeout_s):
        if isinstance(item, RecordedCommand):
            yield item


def pending_count(session_id: int) -> int:
    """Test-only helper: how many items are queued without blocking."""
    with _registry_lock:
        sq = _registry.get(session_id)
    return sq.q.qsize() if sq else 0
