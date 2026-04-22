"""Story S.1 — Recorder v2 shared selector + command datamodel.

Backend-canonical Pydantic types. A matching TypeScript definition lives
at `frontend/src/types/recorder.types.ts` and MUST round-trip losslessly
through JSON.

The `RecordedFlow` root carries `schema_version` so a future v2 bump
doesn't silently corrupt older saved files. The serialisation guard
raises on unknown versions — fail loud, never silently coerce.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SelectorStrategy = Literal[
    "testid",       # data-test-id / data-testid / data-qa / data-test
    "aria",         # role + name / aria-label
    "text",         # stable visible text content
    "css",          # shortest-unique CSS selector
    "xpath",        # absolute / relative-anchored / text-anchored
    "pw_locator",   # Playwright getByRole / getByText / getByLabel
    # Desktop-specific — shipped here so the Desktop epic reuses the shape.
    "automation_id",   # Windows UIA AutomationId
    "uia_name",        # Windows UIA Name property
    "uia_class_name",  # Windows UIA ClassName
]

RecordingTransport = Literal[
    "chrome_extension",  # v1, unchanged
    "web_playwright",    # v2 MVP
    "desktop_windows",   # v2 Epic D
    "desktop_macos",     # v2 Epic DM (tentative)
]

SCHEMA_VERSION = 1


class SelectorCandidate(BaseModel):
    """One of several locator strings that points to the same element."""

    strategy: SelectorStrategy
    value: str
    quality_score: int = Field(ge=0, le=100)
    verified_unique: bool = False

    model_config = {"frozen": True}


class RecordedCommand(BaseModel):
    """A single recorded user interaction mapped to a Robot keyword.

    `selector_candidates` MUST be sorted by (verified_unique DESC,
    quality_score DESC) before being handed to the frontend. The editor
    uses `active_candidate_index` to pick which one serialises into the
    .robot file.
    """

    index: int = Field(ge=0)
    keyword: str
    args: dict = Field(default_factory=dict)
    selector_candidates: list[SelectorCandidate] = Field(default_factory=list)
    active_candidate_index: int = 0

    def model_post_init(self, _context) -> None:  # type: ignore[override]
        if self.selector_candidates:
            if not (0 <= self.active_candidate_index < len(self.selector_candidates)):
                raise ValueError(
                    f"active_candidate_index {self.active_candidate_index} out of "
                    f"range for {len(self.selector_candidates)} candidates"
                )

    @property
    def active_selector(self) -> SelectorCandidate | None:
        if not self.selector_candidates:
            return None
        return self.selector_candidates[self.active_candidate_index]


class RecordedFlow(BaseModel):
    """Root shape: what `/finalize` returns and `/save` accepts.

    Never stored as a DB row — this serialises to a `.robot` file on
    save, mirroring the Phase 4 "flows live in git, not in the app DB"
    decision.
    """

    schema_version: int = SCHEMA_VERSION
    transport: RecordingTransport
    session_id: str
    name: str | None = None
    commands: list[RecordedCommand] = Field(default_factory=list)


def validate_schema_version(flow_json: dict) -> None:
    """Raise if the serialised flow was written by a newer schema version.

    Call this at the first point of contact with untrusted JSON (file
    load, POST body). Pydantic's own field validation handles type
    mismatches; this guards the version boundary specifically.
    """
    v = flow_json.get("schema_version")
    if v is None:
        raise ValueError("RecordedFlow missing schema_version")
    if not isinstance(v, int):
        raise ValueError(f"RecordedFlow schema_version must be int, got {type(v).__name__}")
    if v > SCHEMA_VERSION:
        raise ValueError(
            f"RecordedFlow schema_version {v} newer than supported {SCHEMA_VERSION}. "
            "Upgrade RoboScope to load this flow."
        )
    if v < 1:
        raise ValueError(f"RecordedFlow schema_version must be >= 1, got {v}")
