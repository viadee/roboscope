# Story SH-1 — Self-Healing Selectors (MVP)

**Type:** BMAD quick story (test-automation differentiator)
**Date:** 2026-04-24

## Background

The v2 Recorder already synthesises 3–6 ranked `SelectorCandidate`s per captured step (test-id, ARIA, text, CSS, XPath, Playwright locator). When the `.robot` file emitted from the recording is executed later and its primary selector misses, the executor fails the run with a generic "Element not found" — the alternative candidates never play a role again.

This story closes that loop at the **diagnosis** level (not yet the auto-retry level): when a run fails on a selector, RoboScope looks up the failing line in the recording's sidecar and shows the user the ranked alternatives so they can swap without re-recording.

## Acceptance Criteria

1. **Given** a user saves a v2-recorded flow via `POST /recordings/save`, **when** the `.robot` file is written, **then** a sibling file `<name>.rbs.json` is written in the same directory containing the full `RecordedFlow` JSON (schema + commands + candidates).
2. **Given** a subsequent run of that `.robot` file fails with an "element / locator not found" error, **when** the user opens the run detail panel, **then** a "Selector diagnosis" section lists each failing selector alongside the ranked alternative candidates from the sidecar.
3. **Given** the run was NOT produced from a v2 recording (no sidecar present), **when** the user views the run detail panel, **then** the section silently hides — no empty panel.
4. **Given** the run failure output contains no selector-not-found signal, **then** the section hides too.
5. **Backend endpoint** `GET /api/v1/runs/{run_id}/selector-health` returns a typed payload with `has_sidecar`, `file_path`, `candidates_by_line: [{line, raw_locator, candidates: [...]}]`. 404 for missing run, 200 + `has_sidecar: false` for runs with no sidecar.
6. **Parser** recognises at minimum: Robot Framework `Element ... not found`, Browser library `locator.<method>: Timeout`, Playwright `TimeoutError: locator(...).click()`. One test fixture per variant.
7. **Privacy** — the sidecar lives next to the `.robot` file inside the user's repo tree; never committed automatically to git (users are expected to `.gitignore` `*.rbs.json` if they don't want it checked in — a README note mentions this).
8. **i18n** keys in EN/DE/FR/ES for the diagnosis panel.
9. **Tests** — 1 backend test for sidecar emission, 1 for each of the 3 log-regex variants, 1 for 404, 1 for "no sidecar" fallback.

## Out of scope

- Automatic re-run with alternative candidate (future Story SH-2).
- Applying the fix to the `.robot` file with one click (future Story SH-3).
- Training-data / ML ranking refinement — still the pure heuristic ranking from `selector_synthesis.py`.
