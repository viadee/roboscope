"""Pydantic schemas for the DEBUG-2 router."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StartDebugSessionRequest(BaseModel):
    """Body for ``POST /api/v1/debug/sessions``.

    Currently only the ``run_id`` shape (DEBUG-2). DEBUG-3 will extend
    this with a ``{file, test_name, line, repo_id}`` shape; that
    extension is additive — keep this schema permissive for forward
    compat.
    """

    run_id: int


class DebugSessionStartResponse(BaseModel):
    session_id: str
    robot_file: str
    breakpoint_line: int
    test_name: str | None = None


class PausedAt(BaseModel):
    file: str | None = None
    line: int | None = None
    keyword: str | None = None


class CallStackFrame(BaseModel):
    name: str
    file: str | None = None
    line: int | None = None


class ScopeVariable(BaseModel):
    name: str
    value: str
    type: str


class Scope(BaseModel):
    name: str
    variables: list[ScopeVariable] = Field(default_factory=list)


class DebugSessionState(BaseModel):
    session_id: str
    paused: bool = False
    terminated: bool = False
    paused_at: PausedAt = Field(default_factory=PausedAt)
    scopes: list[Scope] = Field(default_factory=list)
    call_stack: list[CallStackFrame] = Field(default_factory=list)
    output_lines: list[str] = Field(default_factory=list)


class DebugWebSocketEvent(BaseModel):
    """Envelope for DAP-derived events forwarded to the frontend.

    The shape mirrors what `useWebSocket.ts` already expects: a
    top-level ``type`` discriminator. Anything debug-related uses
    ``type=debug_event`` so the existing handler dispatches it.
    """

    type: str = "debug_event"
    topic: str  # e.g. "debug:session:<uuid>"
    kind: str  # "stopped" | "output" | "terminated" | "state"
    body: dict[str, Any] = Field(default_factory=dict)
