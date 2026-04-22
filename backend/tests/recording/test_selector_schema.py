"""Story S.1 — RecordedFlow / RecordedCommand / SelectorCandidate types.

Locks in:
  - Types round-trip losslessly through JSON.
  - schema_version guard rejects too-new / too-old / missing / non-int.
  - active_candidate_index must be in range at construction time.
  - active_selector returns None for a no-target command, else the pick.
  - quality_score is bounded to 0–100.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.recording.selector_schema import (
    SCHEMA_VERSION,
    RecordedCommand,
    RecordedFlow,
    SelectorCandidate,
    validate_schema_version,
)


class TestSelectorCandidate:
    def test_ok(self) -> None:
        c = SelectorCandidate(strategy="testid", value="user-submit", quality_score=95, verified_unique=True)
        assert c.quality_score == 95

    def test_score_rejects_above_100(self) -> None:
        with pytest.raises(ValidationError):
            SelectorCandidate(strategy="testid", value="x", quality_score=101)

    def test_score_rejects_below_0(self) -> None:
        with pytest.raises(ValidationError):
            SelectorCandidate(strategy="testid", value="x", quality_score=-1)

    def test_frozen_prevents_mutation(self) -> None:
        c = SelectorCandidate(strategy="css", value=".x", quality_score=50)
        with pytest.raises(ValidationError):
            c.value = ".y"  # type: ignore[misc]


class TestRecordedCommand:
    def test_no_target_command_active_selector_is_none(self) -> None:
        cmd = RecordedCommand(index=0, keyword="Go To", args={"url": "https://example.com"})
        assert cmd.active_selector is None

    def test_with_targets_returns_active(self) -> None:
        cands = [
            SelectorCandidate(strategy="testid", value="a", quality_score=90),
            SelectorCandidate(strategy="css", value=".a", quality_score=50),
        ]
        cmd = RecordedCommand(index=0, keyword="Click", selector_candidates=cands)
        assert cmd.active_selector is not None
        assert cmd.active_selector.strategy == "testid"

    def test_active_index_defaults_to_zero(self) -> None:
        cands = [SelectorCandidate(strategy="testid", value="a", quality_score=95)]
        cmd = RecordedCommand(index=0, keyword="Click", selector_candidates=cands)
        assert cmd.active_candidate_index == 0

    def test_active_index_out_of_range_rejected(self) -> None:
        cands = [SelectorCandidate(strategy="testid", value="a", quality_score=95)]
        with pytest.raises(ValidationError):
            RecordedCommand(
                index=0, keyword="Click",
                selector_candidates=cands, active_candidate_index=5,
            )


class TestRecordedFlow:
    def test_roundtrip_preserves_every_field(self) -> None:
        flow = RecordedFlow(
            transport="web_playwright",
            session_id="sess-123",
            name="Login happy path",
            commands=[
                RecordedCommand(
                    index=0,
                    keyword="Go To",
                    args={"url": "https://example.com"},
                ),
                RecordedCommand(
                    index=1,
                    keyword="Click",
                    selector_candidates=[
                        SelectorCandidate(strategy="testid", value="submit", quality_score=95, verified_unique=True),
                        SelectorCandidate(strategy="css", value=".btn-submit", quality_score=45),
                    ],
                ),
            ],
        )

        serialised = flow.model_dump(mode="json")
        rehydrated = RecordedFlow.model_validate(serialised)
        assert rehydrated == flow

    def test_schema_version_default_is_current(self) -> None:
        flow = RecordedFlow(transport="web_playwright", session_id="s")
        assert flow.schema_version == SCHEMA_VERSION

    def test_json_string_roundtrips(self) -> None:
        flow = RecordedFlow(transport="web_playwright", session_id="s")
        blob = flow.model_dump_json()
        parsed = RecordedFlow.model_validate_json(blob)
        assert parsed.session_id == "s"


class TestSchemaVersionGuard:
    def test_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="missing schema_version"):
            validate_schema_version({"transport": "web_playwright"})

    def test_non_int_raises(self) -> None:
        with pytest.raises(ValueError, match="must be int"):
            validate_schema_version({"schema_version": "1"})

    def test_too_new_raises(self) -> None:
        with pytest.raises(ValueError, match="newer than supported"):
            validate_schema_version({"schema_version": SCHEMA_VERSION + 1})

    def test_below_one_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 1"):
            validate_schema_version({"schema_version": 0})

    def test_current_version_ok(self) -> None:
        validate_schema_version({"schema_version": SCHEMA_VERSION})
