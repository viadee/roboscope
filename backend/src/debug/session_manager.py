"""In-process registry of active debug sessions + lifecycle plumbing.

A session is started by ``POST /api/v1/debug/sessions`` (DEBUG-2 router).
It stays alive until any of the following:

* DAP ``terminated`` event — auto-disconnect, broadcast `terminated`.
* Frontend calls ``POST /debug/sessions/<id>/disconnect``.
* No control command for ``IDLE_TIMEOUT_SECONDS`` seconds.
* App shutdown — best-effort cleanup in lifespan.

Each session lives entirely in the asyncio event loop; the router
spawns + drives it through this manager. Background-thread access is
NOT supported — DEBUG-2 is request-driven, not task-executor-driven.

The 5-minute idle-timeout is a heuristic; revisit after first user
feedback. Add a setting if ops complain.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.debug.robot_debug_session import Breakpoint, RobotDebugSession
from src.debug.schemas import (
    DebugSessionState,
)

logger = logging.getLogger("roboscope.debug.session_manager")

IDLE_TIMEOUT_SECONDS = 300  # 5 min — heuristic, see module docstring.
TERMINATED_GRACE_SECONDS = 30  # DAP terminated → subprocess wait → kill
SUBPROCESS_KILL_TIMEOUT_SECONDS = 5


# A factory protocol so tests can inject a fake RobotDebugSession
# without touching the manager's lifecycle code.
class SessionFactory(Protocol):
    def __call__(
        self,
        *,
        robot_path: str,
        test_name: str | None,
        breakpoints: list[Breakpoint],
        env_python_path: str,
    ) -> Any: ...


def _default_factory(
    *,
    robot_path: str,
    test_name: str | None,
    breakpoints: list[Breakpoint],
    env_python_path: str,
) -> RobotDebugSession:
    return RobotDebugSession(
        robot_path=robot_path,
        test_name=test_name,
        breakpoints=breakpoints,
        env_python_path=env_python_path,
    )


# ---------------------------------------------------------------------------
# Per-session record
# ---------------------------------------------------------------------------


@dataclass
class _ActiveSession:
    """Per-session state kept in-process by the manager."""

    session_id: str
    user_id: int
    run_id: int | None
    repo_id: int
    robot_file: str
    breakpoint_line: int
    test_name: str | None
    started_at: float = field(default_factory=time.time)
    last_command_at: float = field(default_factory=time.time)
    # The actual RobotDebugSession context manager + the task driving
    # its event loop.
    session: Any = None
    forwarder_task: asyncio.Task[None] | None = None
    idle_task: asyncio.Task[None] | None = None
    state_cache: DebugSessionState | None = None


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


# Forwarder + state-fetcher callable shapes — injected by the router so
# the manager doesn't depend on websocket or DAP-fetch internals.
EventForwarder = Callable[[str, str, dict[str, Any]], None]
"""Called with (topic, kind, body) for every DAP event."""

StateFetcher = Callable[[Any], "Awaitable[DebugSessionState]"]
"""Called with the RobotDebugSession; returns an awaitable that resolves
to the freshly-pulled DebugSessionState."""


class DebugSessionManager:
    """Tracks active debug sessions, deduplicates per (user, run),
    drives the per-session event forwarder + idle timeout."""

    def __init__(
        self,
        *,
        factory: SessionFactory | None = None,
        forwarder: EventForwarder | None = None,
        state_fetcher: StateFetcher | None = None,
        idle_timeout_seconds: float = IDLE_TIMEOUT_SECONDS,
        terminated_grace_seconds: float = TERMINATED_GRACE_SECONDS,
    ) -> None:
        self._factory: SessionFactory = factory or _default_factory
        self._forwarder = forwarder
        self._state_fetcher = state_fetcher
        self._idle_timeout = idle_timeout_seconds
        self._terminated_grace = terminated_grace_seconds

        # session_id → record. Lock guards both maps.
        self._sessions: dict[str, _ActiveSession] = {}
        # (user_id, run_id) → session_id; for AC6 dedup.
        self._by_user_run: dict[tuple[int, int], str] = {}
        self._lock = asyncio.Lock()

    # -- configuration injection -----------------------------------------

    def set_forwarder(self, forwarder: EventForwarder) -> None:
        self._forwarder = forwarder

    def set_state_fetcher(self, state_fetcher: StateFetcher) -> None:
        self._state_fetcher = state_fetcher

    def set_factory(self, factory: SessionFactory) -> None:
        self._factory = factory

    # -- accessors --------------------------------------------------------

    def get(self, session_id: str) -> _ActiveSession | None:
        return self._sessions.get(session_id)

    def find_by_user_run(self, user_id: int, run_id: int) -> _ActiveSession | None:
        sid = self._by_user_run.get((user_id, run_id))
        if sid is None:
            return None
        return self._sessions.get(sid)

    def find_by_user_step(
        self,
        *,
        user_id: int,
        repo_id: int,
        robot_file: str,
        breakpoint_line: int,
    ) -> _ActiveSession | None:
        """DEBUG-3 dedup helper — same-step click silently resumes.

        Linear scan over active sessions; in practice a single user
        has at most one or two debug sessions running, so the cost is
        negligible compared to maintaining a parallel index.
        """
        for rec in self._sessions.values():
            if (
                rec.user_id == user_id
                and rec.repo_id == repo_id
                and rec.robot_file == robot_file
                and rec.breakpoint_line == breakpoint_line
            ):
                return rec
        return None

    # -- start / stop -----------------------------------------------------

    async def start(
        self,
        *,
        user_id: int,
        run_id: int | None,
        repo_id: int,
        robot_file: str,
        breakpoint_line: int,
        test_name: str | None,
        env_python_path: str,
    ) -> _ActiveSession:
        """Spawn a session, wire its event pump + idle timer.

        Caller MUST first call :meth:`find_by_user_run` to honour the
        409-dedup rule from AC6 — this method will overwrite the
        existing record without checking. The router does the lookup
        before issuing the audit event so we keep dedup logic at the
        boundary.
        """
        async with self._lock:
            session_id = uuid.uuid4().hex
            record = _ActiveSession(
                session_id=session_id,
                user_id=user_id,
                run_id=run_id,
                repo_id=repo_id,
                robot_file=robot_file,
                breakpoint_line=breakpoint_line,
                test_name=test_name,
            )
            self._sessions[session_id] = record
            if run_id is not None:
                self._by_user_run[(user_id, run_id)] = session_id

        # Spawn the session under the lock-free path so a slow
        # `robotcode` startup doesn't block other API requests.
        session = self._factory(
            robot_path=robot_file,
            test_name=test_name,
            breakpoints=[Breakpoint(robot_file, breakpoint_line)],
            env_python_path=env_python_path,
        )
        # Use the async-context entry path manually so we can store
        # the session reference and unwind on cleanup.
        try:
            await session.__aenter__()
        except Exception:
            await self._discard(session_id)
            raise
        record.session = session

        # Wire forwarder + idle timer. Both run as long-lived tasks
        # cancelled by stop().
        record.forwarder_task = asyncio.create_task(
            self._pump_events(record), name=f"debug-forwarder-{session_id[:8]}"
        )
        record.idle_task = asyncio.create_task(
            self._watch_idle(record), name=f"debug-idle-{session_id[:8]}"
        )
        return record

    async def touch(self, session_id: str) -> None:
        """Reset the idle clock — called by every control endpoint."""
        rec = self._sessions.get(session_id)
        if rec is not None:
            rec.last_command_at = time.time()

    async def stop(self, session_id: str) -> None:
        """Disconnect a session. Idempotent."""
        rec = self._sessions.get(session_id)
        if rec is None:
            return
        await self._cleanup(rec)

    async def stop_all(self) -> None:
        """Best-effort shutdown — call from the FastAPI lifespan."""
        ids = list(self._sessions.keys())
        for sid in ids:
            with suppress(Exception):
                await self.stop(sid)

    # -- internals --------------------------------------------------------

    async def _pump_events(self, rec: _ActiveSession) -> None:
        """Drain the session's event queue → forwarder.

        The RobotDebugSession publishes ``{"kind": <name>, "body": <dict>}``
        items; we forward each as ``(topic, kind, body)``. After every
        ``stopped`` event we synthesize a ``state`` event with the
        freshly-fetched scope/stack tree so the frontend has live
        variable data without a separate roundtrip.
        """
        topic = f"debug:session:{rec.session_id}"
        try:
            while True:
                evt = await rec.session.events.get()
                kind = evt.get("kind", "")
                body = evt.get("body", {})
                self._forward(topic, kind, body)
                if kind == "stopped" and self._state_fetcher is not None:
                    try:
                        snapshot = await self._state_fetcher(rec.session)
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "state-fetcher failed for session %s", rec.session_id
                        )
                        snapshot = None
                    if snapshot is not None:
                        rec.state_cache = snapshot
                        self._forward(
                            topic,
                            "state",
                            snapshot.model_dump(mode="json"),
                        )
                if kind == "terminated":
                    # Schedule cleanup; we deliberately don't await it
                    # here so the forwarder task can exit cleanly.
                    asyncio.create_task(self._terminated_cleanup(rec))
                    return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("event pump crashed for session %s", rec.session_id)

    async def _watch_idle(self, rec: _ActiveSession) -> None:
        """Disconnect the session if no control command lands within
        ``idle_timeout`` seconds. Recheck every second so the deadline
        slides forward on every ``touch()``."""
        try:
            while True:
                await asyncio.sleep(1.0)
                if rec.session_id not in self._sessions:
                    return
                idle_for = time.time() - rec.last_command_at
                if idle_for >= self._idle_timeout:
                    logger.info(
                        "debug session %s idle for %.1fs — auto-disconnecting",
                        rec.session_id, idle_for,
                    )
                    asyncio.create_task(self._cleanup(rec))
                    return
        except asyncio.CancelledError:
            raise

    def _forward(self, topic: str, kind: str, body: dict[str, Any]) -> None:
        if self._forwarder is None:
            logger.debug("no forwarder set; dropping event %s/%s", topic, kind)
            return
        try:
            self._forwarder(topic, kind, body)
        except Exception:  # noqa: BLE001
            logger.exception("forwarder raised on %s/%s", topic, kind)

    async def _terminated_cleanup(self, rec: _ActiveSession) -> None:
        """30-second grace from `terminated` to subprocess wait, then
        kill if necessary."""
        try:
            await asyncio.sleep(0)  # let the forwarder exit first
            with suppress(Exception):
                await asyncio.wait_for(
                    rec.session.disconnect(), timeout=self._terminated_grace
                )
            await self._cleanup(rec)
        except Exception:  # noqa: BLE001
            logger.exception("terminated-cleanup crashed for %s", rec.session_id)

    async def _cleanup(self, rec: _ActiveSession) -> None:
        # 1. Cancel forwarder + idle tasks.
        for task in (rec.forwarder_task, rec.idle_task):
            if task and not task.done():
                task.cancel()
        for task in (rec.forwarder_task, rec.idle_task):
            if task is None:
                continue
            with suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(task, timeout=2.0)
        # 2. Tear down the session (DAP disconnect + subprocess reap).
        if rec.session is not None:
            with suppress(Exception):
                await rec.session.__aexit__(None, None, None)
        # 3. Drop registry entries.
        await self._discard(rec.session_id)

    async def _discard(self, session_id: str) -> None:
        async with self._lock:
            rec = self._sessions.pop(session_id, None)
            if rec is not None and rec.run_id is not None:
                stored = self._by_user_run.get((rec.user_id, rec.run_id))
                if stored == session_id:
                    self._by_user_run.pop((rec.user_id, rec.run_id), None)


# Singleton — wired in `main.py` lifespan with the WebSocket forwarder
# and DAP state-fetcher.
session_manager = DebugSessionManager()
