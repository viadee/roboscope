# Story EDITOR-1: Multi-selector picker in the Visual Flow Editor

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-1-multi-selector-picker-in-flow-editor`

## Context

`backend/examples/tests/flows/recording.robot` (recorded with Recorder v2) has a sibling `recording.rbs.json` sidecar that ships **multiple ranked selector candidates per recorded command** (text/css/xpath/aria/pw_locator, with `quality_score` and `verified_unique`). At runtime the self-healing library (Story SH-2) reads these candidates and falls through them when the active selector breaks.

A reusable component for swapping between candidates already exists: `frontend/src/components/recorder/SelectorPicker.vue` (Story S.4). Its module docstring even calls out the visual editor: *"Used inline in the Visual-Flow editor (step nodes) and as a gutter annotation in the Text editor."* Today it is only wired into `RecordingLiveView`. The visual editor (`FlowEditor.vue` + `KeywordNode.vue`) renders every argument as a plain text input — the user has no way to switch to one of the recorded alternatives without leaving the editor and hand-editing the `.robot` source.

## Story

As an **Editor user** working with a recorded `.robot` file,
I want to **switch between recorded selector candidates for any step that has them**,
so that **I can pick the most stable selector (e.g. ARIA over fragile XPath) without leaving the visual editor or hand-editing source**.

## Acceptance Criteria

1. **AC1 — Sidecar loading.** When the visual editor opens a `.robot` file, it tries to load the sibling `<basename>.rbs.json` via the existing explorer file API. Loading is non-blocking (the editor renders without the sidecar if the file is missing or malformed) and silent (a missing sidecar is **not** an error toast). Schema is validated via `validateSchemaVersion()`.

2. **AC2 — Step ↔ command matching.** The editor matches each visible step in the active test case / keyword to a `RecordedCommand` from the sidecar by **positional index within the active test case's keyword steps** (control-flow nodes like `IF`, `FOR`, `END` are skipped on both sides). A short comment in the converter explains the matching strategy and its limits (re-ordered or hand-inserted steps may go unmatched — that is acceptable, the picker simply does not appear).

3. **AC3 — Selector parameter detection.** For matched commands whose `selector_candidates.length > 0`, the **first positional argument** of the keyword in the `.robot` step is treated as the selector slot (this matches the convention of `Browser.Click`, `Browser.Fill Text`, `Browser.Press Keys`, `Scroll To Element`, etc.). The detection is encapsulated behind a single helper so it can be tightened later (e.g. via a per-keyword whitelist) without touching the UI code.

4. **AC4 — Picker rendered in the detail panel.** In the editable detail panel (`FlowEditor.vue`, the "Arguments" section), the selector slot replaces the plain `<input>` with the existing `SelectorPicker` component. The component receives the matched `RecordedCommand` and emits `update:activeIndex`. On change:
   - The step's first positional arg is rewritten to the new candidate's `value` and the `.robot` source updates immediately (visible in the text editor).
   - The sidecar's `active_candidate_index` is updated for that command.
   - The sidecar is re-saved via the same file-write API used for the `.robot` file (silently — no toast spam; the editor's existing dirty/save flow handles persistence).

5. **AC5 — Inline marker on the node.** When a step has selector candidates, the keyword node body (`KeywordNode.vue`) renders a small **quality dot** (the same green/amber/red band the picker uses) next to the first arg chip plus a `× N` counter (e.g. `× 4`) so the user sees at a glance that there is something to pick. Hand-written tests (no sidecar match) keep the current plain chip style — no visual regression.

6. **AC6 — Graceful fallbacks.**
   - If the sidecar loads but no command matches the current step → no picker, no marker, plain input as today.
   - If the keyword has zero arguments declared but a sidecar entry exists → no picker.
   - If `activeSelector(cmd)` is null (empty candidate list) → no picker, no marker.
   - If the user has already hand-edited the selector value to something not in `selector_candidates` → the picker still opens, the menu shows all recorded candidates, and the current value is shown above the menu with a "(custom value, not from recording)" hint.

7. **AC7 — Editor reorder/insert/delete keep matching consistent.** Moving a step up/down, inserting a new step, or deleting a step uses the **post-edit positional index** for matching. Hand-inserted steps that were never recorded simply get no picker; the existing matched siblings keep theirs. No assertion failures, no console errors. (This is the cheap, predictable behaviour — full re-fingerprinting is explicitly out of scope.)

8. **AC8 — i18n (EN/DE/FR/ES).** New user-facing strings live under `flowEditor.selector.*` and have entries in all four locales. Strings:
   - `flowEditor.selector.candidatesBadge` — `"× {count}"` (count interpolation)
   - `flowEditor.selector.customValueHint` — `"(custom value, not from recording)"`
   - `flowEditor.selector.tooltipHasCandidates` — `"{count} recorded candidates — click to switch"`
   - All four locale files updated; `npm run build` passes (no vue-i18n syntax errors).

9. **AC9 — Tests + build green.**
   - **Vitest:** new spec `tests/components/FlowEditorSelectorPicker.spec.ts` covering: sidecar matched → picker rendered, swap → arg + sidecar updated, no sidecar → plain input, custom value → hint shown.
   - **Vitest:** `tests/components/KeywordNode.spec.ts` extended (or created) to assert the badge appears only when candidates are present.
   - **E2E (Playwright):** `e2e/tests/flow-editor-selector-picker.spec.ts` — open `recording.robot` from the example repo in the visual editor, confirm a step shows the picker badge, click swap, confirm the `.robot` text reflects the new selector value.
   - All existing backend / Vitest / Playwright suites pass.
   - `vue-tsc --noEmit` reports no new errors in `src/components/editor/**` or `src/types/recorder.types.ts`.

10. **AC10 — Out of scope (explicit non-goals).**
    - Cross-file or cross-test re-fingerprinting (a step inserted from the palette stays unmatched until re-recorded).
    - Editing / re-ranking / deleting candidates from the picker menu (read-only swap only).
    - Selector picking for non-first-positional arguments (e.g. `Browser.Drag And Drop` source vs target — separate story).
    - Sidecar editing for control-flow constructs (IF/FOR/WHILE).

## Tasks / Subtasks

- [x] **Task 1 — Sidecar loader & matcher**
  - [x] `frontend/src/composables/useRecordingSidecar.ts` — `loadSidecar` (silent on 404 / bad JSON / wrong schema) + `saveSidecar` + `sidecarPathFor` helper.
  - [x] `matchStepToCommand` + `recordedIndex` + `isRecordedStep` in `flow/flowConverter.ts` — positional-index strategy, control-flow + `var` skipped on both sides, documented.
  - [x] 8 Vitest specs in `tests/composables/useRecordingSidecar.spec.ts` and matcher coverage in `tests/components/FlowEditorSelectorPicker.spec.ts`.

- [x] **Task 2 — Wire picker into `FlowEditor.vue` detail panel**
  - [x] `RobotEditor.vue` loads the sidecar via `loadSidecar` (keyed on `repoId` + `filePath`, race-token guarded) and passes it to `FlowEditor`. Persistence sits in `RobotEditor` (single source of truth).
  - [x] `FlowEditor.vue` renders `SelectorPicker` for `args[0]` when the matched command has candidates; falls back to a plain `<input>` otherwise.
  - [x] `update:activeIndex` → `applySelectorSwap` (pure helper) rewrites `args[0]` + `active_candidate_index`, marks the form dirty via the existing watcher chain, and emits `update:sidecar` upward.
  - [x] Custom-value hint shown when `args[0]` is not in the candidates; an additional `confirm()` gates the overwrite of a custom value (review fix #5).

- [x] **Task 3 — Inline marker on `KeywordNode.vue`**
  - [x] `FlowNodeData.recording: RecordedCommand | null` populated by `stepsToFlow`.
  - [x] Quality dot + `× N` badge on the first arg chip (i18n key `flowEditor.selector.candidatesBadge`).
  - [x] Quality-band thresholds extracted to `src/utils/selectorQuality.ts` and shared with `SelectorPicker.vue`.

- [x] **Task 4 — Sidecar persistence (revised after review)**
  - [x] FlowEditor never writes to disk. On swap it emits `update:sidecar` and `RobotEditor` sets a `sidecarDirty` flag.
  - [x] `RobotEditor.saveSidecarIfDirty()` is exposed via `defineExpose`; `ExplorerView.handleSave()` calls it before writing the `.robot` so sidecar + `.robot` land together. Resolves review must-fix #1, #2, #4.
  - [x] Race fix: `refreshSidecar` resets `sidecar.value = null` *before* awaiting load and uses a token to discard stale resolutions (review must-fix #3).

- [x] **Task 5 — i18n + tests**
  - [x] Four keys under `flowEditor.selector.*` (`tooltipHasCandidates`, `customValueHint`, `candidatesBadge`, `replaceCustomConfirm`) in EN / DE / FR / ES.
  - [x] Vitest: `useRecordingSidecar` (8), `FlowEditorSelectorPicker` (18 — matcher + `applySelectorSwap` + `isCustomSelectorValue` + persistence smoke), `KeywordNode` (6) → **32 new tests**, full suite 242/242 green.
  - [ ] Playwright spec — deferred (review nice-to-have #10). Listed in `_bmad-output/implementation-artifacts/deferred-work.md` for follow-up.

- [x] **Task 6 — Verification**
  - [x] `npx vitest run` → 242/242 pass.
  - [x] `npx vue-tsc --noEmit` — no new errors in `src/components/editor/**`, `src/composables/**`, or `src/i18n/locales/**` from EDITOR-1 (total error count unchanged at 31; remaining errors pre-existing in `teams.*` / `sso.store.ts` / locale duplicates).
  - [ ] Manual smoke (browser) — pending; backend serves `flows/recording.robot` and `flows/recording.rbs.json` correctly (verified via curl).

## Out of scope (re-stated)
See AC10. Anything not listed there belongs to a follow-up story.

## Risk notes
- **Position-based matching is brittle by design.** A user inserting a hand-written step in the middle of a recorded test will desync everything below it. This is acceptable for V1 because (a) the picker just disappears for unmatched steps — no broken test — and (b) full fingerprint-based matching is a significantly larger story. Re-recording is the recommended workflow.
- **Sidecar writes during editor sessions** must use the existing dirty-state + save flow. Bypassing it (auto-save on every swap) would re-introduce the "silent edits" anti-pattern called out in CLAUDE.md.
