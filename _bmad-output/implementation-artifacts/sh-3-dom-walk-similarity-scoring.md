# Story SH-3 — DOM-walk similarity scoring

**Type:** BMAD story (SH-2 follow-up — Healenium-class)
**Date:** 2026-04-24

## Background

SH-2 heals via **transposition** (id↔testid↔aria↔text variants) and
**sidecar lookup**. Both rely on the user's failing selector sharing
a value with a viable alternative (`id=submit` → `[data-testid=submit]`).
That covers drift *within* strategy siblings.

What transposition misses: bigger refactorings. Dev renames the
button id from `submit` to `submit-btn`, moves it inside a
`<form class="v2">`, adds wrapper divs. No string sibling of
`id=submit` will resolve. Healenium's answer is **element fingerprint
matching** — persist a multi-signal snapshot of the element at record
time, then at heal time score every candidate element on the live
page for similarity, pick the best.

SH-3 ships the scorer + walker + recorder-side fingerprint emission
so the SH-2 heal library can fall back to similarity matching when
transposition + sidecar both come up dry.

## Acceptance Criteria

### Schema

1. `RecordedCommand.element_fingerprint: dict | None` — optional field
   on the v2 recording shape. Legacy commands without a fingerprint
   deserialise cleanly (default None).
2. **Fingerprint fields (MVP)**: `tag`, `id`, `testid`, `classes`
   (list), `name`, `role`, `text` (first 80 chars, normalised
   whitespace), `ancestors` (list of up to 4 parent tag+id+testid
   triples).

### Recorder-side capture

3. The capture script (`capture_script.py`) enriches every primitive
   event with an `element_fingerprint` block built from the DOM node
   that triggered it.
4. The v2 translator (`v2_payload_translator.py`) forwards the
   block through to the `RecordedCommand` unchanged. Sidecar writes
   it; sidecar reads it via the existing `parsed` model.

### Runtime scorer

5. `score_fingerprint_similarity(stored, live) -> float` returns
   0..1. Scoring weights (sum to 1.0):
   - `testid` exact match → 0.45 (strongest signal)
   - `id` exact match     → 0.20
   - `role + tag`         → 0.10
   - `classes` Jaccard    → 0.08
   - `text` overlap       → 0.10
   - `ancestors` overlap  → 0.07

### Runtime walker

6. `find_best_by_fingerprint(stored, live_candidates) -> (value, score) | None`
   — given a list of `(locator_value, live_snapshot)` tuples, returns
   the best match with its score, or None if nothing exceeds the
   configured threshold (default 0.6).
7. `build_live_candidate_set(page)` collects interactive elements
   (`button`, `input`, `a`, `select`, `textarea`, any element with
   `data-testid`, any element with a `role`) plus their per-element
   snapshots. Used by the heal library when sidecar + transposition
   fail.

### Heal-library integration

8. In `RoboScopeHeal._dispatch`, after transposition + sidecar produce
   no above-threshold candidate, consult the fingerprint walker if
   the step has a stored fingerprint. Picks are marked with
   `source="fingerprint"` on the audit record.
9. The same confidence threshold gates the walker's winner — a
   fingerprint match below the mutating keyword threshold is ignored.

### Tests

10. **13+ unit tests for the scorer**: all-fields match = 1.0, no
    fields match = 0.0, testid-only = 0.45, partial text overlap,
    Jaccard on classes, ancestors partial match, empty stored /
    empty live edge cases.
11. **Walker tests** with synthetic candidate lists covering: unique
    testid winner, tie-break by secondary signals, below-threshold
    returns None.
12. **One integration test** (skipped by default, opt-in via
    `-m integration`) that renders a mutated fixture (button id
    renamed, parent class changed) and verifies the walker still
    picks the right element.

## Out of scope

- **Fingerprint storage beyond v2 flows**. Legacy v1 flows and
  hand-written tests don't emit fingerprints — they keep the
  transposition-only path. Sidecar is the prerequisite.
- **Visual fingerprints** (bounding box, screenshot crop). Pure DOM
  signal for now; visual comes later if it adds recall.
- **Recorder-side UI indicator**. Fingerprints are invisible to the
  user — they just make heal more effective. No new UI in this story.

## Rollback posture

- Schema change is **additive** and optional — old sidecars read
  fine because `element_fingerprint` defaults to None.
- When the fingerprint field is None, the fingerprint walker is
  never invoked — zero overhead for legacy flows.
- The walker's threshold default (0.6) is deliberately higher than
  any single strong signal would land on its own; a real multi-
  signal match is needed to clear it. Matches a wrong element only
  when multiple signals align — strictly rarer than a transposition
  false positive.
