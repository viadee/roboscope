"""Pydantic schemas for the DEBUG-2 / DEBUG-3 router."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class StartDebugSessionRequest(BaseModel):
    """Body for ``POST /api/v1/debug/sessions``.

    Two invocation shapes — exactly one MUST be supplied:

    * **DEBUG-2** — ``{run_id}``: re-debug a failed run; the router
      walks ``output.xml`` to find the breakpoint line.
    * **DEBUG-3** — ``{file, test_name, line, repo_id}``: run a clicked
      step in the Flow Editor. ``line`` is 1-based; ``test_name`` must
      match a test inside ``file``; ``repo_id`` must be a project the
      caller has RUNNER+ on.

    The two shapes are validated against each other in
    :meth:`_check_exactly_one_shape` so we get a clean 422 instead of
    a confusing partial-payload mix.
    """

    # DEBUG-2 path
    run_id: int | None = None
    # DEBUG-3 path
    file: str | None = None
    test_name: str | None = None
    line: int | None = None
    repo_id: int | None = None

    @model_validator(mode="after")
    def _check_exactly_one_shape(self) -> StartDebugSessionRequest:
        run_shape = self.run_id is not None
        step_fields = (self.file, self.test_name, self.line, self.repo_id)
        step_shape_full = all(f is not None for f in step_fields)
        step_shape_any = any(f is not None for f in step_fields)

        if run_shape and step_shape_any:
            raise ValueError(
                "Provide either {run_id} or {file, test_name, line, repo_id}, not both"
            )
        if not run_shape and not step_shape_any:
            raise ValueError(
                "Body must include either {run_id} or "
                "{file, test_name, line, repo_id}"
            )
        if step_shape_any and not step_shape_full:
            missing = [
                name for name, val in zip(
                    ("file", "test_name", "line", "repo_id"), step_fields, strict=True
                ) if val is None
            ]
            raise ValueError(
                f"Step-shape body is missing required fields: {', '.join(missing)}"
            )
        if self.line is not None and self.line < 1:
            raise ValueError("line must be a 1-based positive integer")
        return self

    @property
    def is_step_shape(self) -> bool:
        """True iff this request uses the DEBUG-3 ``file/test_name/line/repo_id`` shape."""
        return self.file is not None


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


class InstallPrereqRequest(BaseModel):
    """Body for ``POST /api/v1/debug/sessions/install-prerequisites``."""

    repo_id: int


class InstallPrereqResponse(BaseModel):
    """Result of a prereq-install attempt."""

    already_installed: bool
    log_tail: str | None = None


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
