"""C1 regression: sidecar quality_score (0–100) must be normalized to the
0–1 confidence scale the heal threshold gate uses. Pre-fix, a quality_score
of 60 became confidence 60.0, which always passed the 0.7 threshold —
defeating the "confidence thresholds gate every swap" safety invariant on
recorded tests."""

from __future__ import annotations

import json
from pathlib import Path

from RoboScopeHeal.candidate_finder import (
    HealCandidate,
    _sidecar_candidates,
    pick_best_candidate,
)


def _sidecar(tmp_path: Path, candidates: list[dict]) -> Path:
    p = tmp_path / "flow.rbs.json"
    p.write_text(
        json.dumps({"commands": [{"active_candidate_index": 0,
                                  "selector_candidates": candidates}]}),
        encoding="utf-8",
    )
    return p


def test_sidecar_quality_score_normalized_to_0_1(tmp_path: Path) -> None:
    sidecar = _sidecar(tmp_path, [
        {"value": "css=.failed", "strategy": "css", "quality_score": 95},
        {"value": "id=good", "strategy": "css", "quality_score": 60},
        {"value": "css=.weak", "strategy": "css", "quality_score": 20},
    ])
    cands = _sidecar_candidates("css=.failed", sidecar)
    confs = {c.value: c.confidence for c in cands}
    assert confs["id=good"] == 0.6   # 60 → 0.6 (was 60.0)
    assert confs["css=.weak"] == 0.2
    assert all(0.0 <= c.confidence <= 1.0 for c in cands)


def test_sidecar_already_0_1_scale_preserved(tmp_path: Path) -> None:
    sidecar = _sidecar(tmp_path, [
        {"value": "css=.failed", "strategy": "css", "quality_score": 1.0},
        {"value": "id=good", "strategy": "css", "quality_score": 0.95},
    ])
    cands = _sidecar_candidates("css=.failed", sidecar)
    assert cands[0].confidence == 0.95  # <= 1 preserved, not divided


def test_threshold_now_gates_low_quality_sidecar(tmp_path: Path) -> None:
    """The point of C1: a deliberately-fragile sidecar candidate (quality 20)
    must NOT be swapped in under the mutating 0.7 threshold."""
    sidecar = _sidecar(tmp_path, [
        {"value": "css=.failed", "strategy": "css", "quality_score": 50},
        {"value": "css=.weak", "strategy": "css", "quality_score": 20},
    ])
    cands = _sidecar_candidates("css=.failed", sidecar)
    assert pick_best_candidate(cands, threshold=0.7) is None  # gated (was bypassed)
    # a strong candidate still qualifies
    strong = [HealCandidate(value="x", strategy="css", confidence=0.9, source="sidecar")]
    assert pick_best_candidate(strong, threshold=0.7) is not None
