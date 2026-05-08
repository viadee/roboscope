"""Pull a `DebugSessionState` snapshot from a paused RobotDebugSession.

DAP's variable/scope tree requires three roundtrips per `stopped`:

1. ``stackTrace`` → list of frames.
2. For each frame: ``scopes`` → list of variable references.
3. For each scope: ``variables`` → the actual `name/value/type` rows.

We only fetch scopes for the TOP frame (where execution is paused);
the call stack itself is rendered from the `stackTrace` response, but
we don't recurse into every frame's variable tree because that would
hammer the adapter and balloon the WebSocket payload. The frontend
can fetch a deeper view on demand if we ever build a "step into
frame" affordance — DEBUG-2 does not.

All DAP errors are absorbed: state-fetch is best-effort. A blank
`DebugSessionState` is preferable to a 500 on the websocket layer.
"""

from __future__ import annotations

import logging
from typing import Any

from src.debug.dap_client import DapApplicationError
from src.debug.robot_debug_session import RobotDebugSession
from src.debug.schemas import (
    CallStackFrame,
    DebugSessionState,
    PausedAt,
    Scope,
    ScopeVariable,
)

logger = logging.getLogger("roboscope.debug.state_fetcher")


async def fetch_state(session: RobotDebugSession) -> DebugSessionState:
    """Run the stackTrace → scopes → variables sequence and pack the
    response into a frontend-friendly `DebugSessionState`.

    The session_id field is left empty here — the caller (forwarder)
    knows the id and patches it before broadcast. We can't reach the
    manager from this layer cleanly without a dependency cycle.
    """
    state = DebugSessionState(session_id="")
    if session._client is None:  # noqa: SLF001 — internal hook for foundation
        return state

    state.paused = session.state.paused
    state.terminated = session.state.terminated
    state.output_lines = list(session.state.output_lines[-200:])  # cap

    # 1. Stack trace.
    frames: list[dict[str, Any]] = []
    try:
        body = await session._client.request(  # noqa: SLF001
            "stackTrace", {"threadId": 1, "startFrame": 0, "levels": 50}
        )
        frames = list(body.get("stackFrames", []))
    except (DapApplicationError, Exception) as e:  # noqa: BLE001
        logger.debug("stackTrace failed: %s", e)
        return state

    state.call_stack = [_pack_frame(f) for f in frames]
    if not frames:
        return state

    top = frames[0]
    state.paused_at = PausedAt(
        file=_source_path(top.get("source", {})),
        line=top.get("line"),
        keyword=top.get("name"),
    )

    # 2. Scopes for the top frame.
    try:
        body = await session._client.request(  # noqa: SLF001
            "scopes", {"frameId": top.get("id")}
        )
        scope_descs = list(body.get("scopes", []))
    except (DapApplicationError, Exception) as e:  # noqa: BLE001
        logger.debug("scopes failed: %s", e)
        return state

    # 3. Variables per scope.
    for scope_desc in scope_descs:
        ref = scope_desc.get("variablesReference")
        if not ref:
            continue
        try:
            body = await session._client.request(  # noqa: SLF001
                "variables", {"variablesReference": ref}
            )
        except (DapApplicationError, Exception) as e:  # noqa: BLE001
            logger.debug("variables(%d) failed: %s", ref, e)
            continue
        var_rows = body.get("variables", [])
        scope = Scope(
            name=str(scope_desc.get("name", "")),
            variables=[_pack_variable(v) for v in var_rows],
        )
        state.scopes.append(scope)

    return state


def _pack_frame(f: dict[str, Any]) -> CallStackFrame:
    return CallStackFrame(
        name=str(f.get("name", "")),
        file=_source_path(f.get("source", {})),
        line=f.get("line"),
    )


def _pack_variable(v: dict[str, Any]) -> ScopeVariable:
    return ScopeVariable(
        name=str(v.get("name", "")),
        value=str(v.get("value", "")),
        type=str(v.get("type", "")),
    )


def _source_path(source: dict[str, Any] | None) -> str | None:
    if not source:
        return None
    p = source.get("path") or source.get("name")
    return str(p) if p else None
