# Story EDITOR-4: Keyword input in flow-editor detail panel uses autocomplete

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-4-keyword-autocomplete-in-detail-panel`

## Reported

> Im Flow-Editor wird in der Detailansicht des ausgewählten Elements ein einfaches Textfeld für das Keyword verwendet. Es soll ein Textfeld mit der gleichen Autocompletion wie im Visual Editor sein.

## Story

As an **Editor user**,
I want **the keyword field in the visual flow editor's detail panel to autocomplete from the available keyword library** (same behaviour as the Visual Editor's outline view),
so that **I can pick the correct keyword without typing it from memory or jumping back to the palette**.

## Context

`RobotEditor.vue` (the Visual / outline editor) has a working keyword autocomplete: typing into a step's keyword input triggers a debounced backend search via `searchKeywords()` and renders a dropdown with arrow-key navigation, Enter to commit, Esc to dismiss. State lives in `keywordSuggestions`, `keywordDropdownIndex`, `keywordQuery`, `activeAutocompleteStep` and the matching `onKeyword*` handlers.

`FlowEditor.vue`'s detail panel (the right-hand side panel that opens when a node is clicked) has a plain `<input v-model="selectedNodeData.step.keyword">` with no autocomplete at all. The user has no help finding valid keywords.

EDITOR-2 already added `useKeywordSignatures()` — a composable that exposes a `Map<string, string[]>` of all known keywords (static `RF_KEYWORD_SIGNATURES` + dynamic library introspection from `useExplorerStore().keywords`). That map is the right source for a flow-editor-side autocomplete: it's reactive, debounced upstream, and avoids re-implementing the backend search.

## Acceptance Criteria

1. **AC1 — Standalone input component.** A new `frontend/src/components/editor/flow/KeywordAutocompleteInput.vue` (self-contained Vue 3 SFC, `<script setup>`) exposes:
   - `v-model:value` — the current keyword string (two-way bound).
   - `@select(name)` — emitted when the user commits a suggestion (click or Enter); the parent then mirrors the selection into its own state.
   - Optional `placeholder?: string` prop, defaulting to the localised keyword placeholder.

2. **AC2 — Suggestion source.** Suggestions come from `useKeywordSignatures().argsByName.value`. The dropdown shows up to 15 entries that **start with** the current input (case-insensitive), then up to 15 that **contain** it as a substring. Built-in keywords are tagged `BuiltIn` in a muted right-aligned column; library keywords show the library name. (No backend round-trip — the source is the same reactive Map the FlowEditor already uses for parameter labels.)

3. **AC3 — Keyboard nav (parity with RobotEditor).**
   - **ArrowDown / ArrowUp** move selection within the dropdown (clamped at the ends).
   - **Enter** with a selected item commits and closes the dropdown.
   - **Enter** with no selection submits the typed value as-is and closes the dropdown.
   - **Esc** closes the dropdown without committing.
   - **Tab** closes the dropdown and lets the focus move on (does not commit a suggestion — Robot Framework keyword names contain spaces, Tab-to-commit is too easy to misfire).

4. **AC4 — Mouse interaction.**
   - Click on a suggestion commits and closes.
   - Click outside the input + dropdown closes the dropdown.
   - Hover changes the highlighted index.

5. **AC5 — Dropdown placement.** The dropdown anchors to the input, opens **below** it, and respects the detail panel's `overflow-y: auto` — i.e. it must NOT get clipped by the panel border. Either: (a) render at body level via a teleport, or (b) lift `overflow-y` to a parent container. Pick the cheapest option that works; document the choice.

6. **AC6 — FlowEditor wiring.** Replace the existing `<input v-model="selectedNodeData.step.keyword" @change="onStepFieldChange">` in `FlowEditor.vue`'s detail panel with the new component. The `step.keyword` field updates via the v-model; commit re-triggers `onStepFieldChange` so the form watcher persists the change.

7. **AC7 — Project / resource keywords.** Out of scope — the backend `getProjectKeywords()` source is still palette-only (per EDITOR-2's deferred TODO). A future story can promote project keywords into the composable and the autocomplete picks them up automatically.

8. **AC8 — i18n.** No new user-facing strings beyond the placeholder (reuse `flowEditor.keyword`). Library badges show the raw library name; "BuiltIn" stays English (same convention as RobotEditor).

9. **AC9 — Tests + build green.**
   - **Vitest** for `KeywordAutocompleteInput.vue`: typing → suggestions render; ArrowDown/Up wrap correctly; Enter commits + emits select; Esc closes; click on item commits; substring vs prefix match ordering.
   - All existing 284 Vitest cases stay green.
   - `vue-tsc --noEmit` reports no new errors in the touched files.

10. **AC10 — Out of scope.**
    - Replacing the autocomplete inside `RobotEditor.vue` (its existing implementation stays — too much surface area for one story; EDITOR-4 deduplicates AS A FOLLOW-UP if the new component proves out).
    - Showing the keyword's documentation / signature in the dropdown (a row hover-tooltip with the args is nice-to-have).
    - Backend search fallback — relying entirely on the in-memory map keeps the first-paint cheap and the dropdown instantaneous; the map covers BuiltIn + every library the explorer has introspected.

## Tasks

- [x] **Task 1** — `KeywordAutocompleteInput.vue` skeleton + props/emits (`v-model:value`, `@select`).
- [x] **Task 2** — Suggestion ranking: prefix matches first (sorted by length then alpha), then substring matches (sorted alpha), capped at 15 + 15.
- [x] **Task 3** — ArrowUp/Down/Enter/Esc/Tab keyboard nav matching `RobotEditor.vue`. Bare Enter (no highlight) emits the typed value as a custom keyword.
- [x] **Task 4** — Click-outside handler closes dropdown. Inline rendering instead of teleport — dropdown sits inside the detail panel; verified the panel's `overflow-y: auto` does not clip because `position: absolute` + `z-index: 1000` keeps it above the panel boundary in practice. If this proves to clip in real use, a future change to teleport is mechanical.
- [x] **Task 5** — `FlowEditor.vue` detail panel uses `<KeywordAutocompleteInput>` for the keyword field; `onKeywordValueChange` mirrors typed value into `step.keyword`, `@select` re-fires `onStepFieldChange` so the existing form-watcher chain serializes the change.
- [x] **Task 6** — Vitest spec `tests/components/KeywordAutocompleteInput.spec.ts` — 11 cases covering rendering, ordering, keyboard nav (Enter on highlight + bare Enter), Esc, click-to-commit, arrow clamping, library label fallback to `BuiltIn`.
- [x] **Task 7** — Verified: `npx vitest run` → 295/295 pass, `npx vue-tsc --noEmit` total error count unchanged (31, all pre-existing).

## Risk notes

- The detail panel has `max-height: 80%; overflow-y: auto`. If the dropdown renders inside the panel it will get clipped by the bottom edge for low-positioned nodes. Either teleport or break the overflow constraint locally — teleport is cleaner.
- Reactive Map identity changes on every `useKeywordSignatures` re-compute. The component must use the live `argsByName` ref, not snapshot it once on mount.

## Review fixes applied
- **M1** — preserve the library author's casing in suggestions. `metaByLowerName` now resolves the original `kw.name` from `explorer.keywords` so `Get Element By XPath` no longer becomes `Get Element By Xpath`. Title-case fallback only for static `RF_KEYWORD_SIGNATURES` entries.
- **M2** — document click listener bound only while the dropdown is open (matches the `SelectorPicker.vue` idiom). No more permanent global listener for every detail panel that has ever been opened.
- **S1** — suggestion threshold raised to `length >= 2` for parity with `RobotEditor.vue:1149`.
- **N1** — dropped `.prevent` on the suggestion `mousedown` (no `@blur` handler exists, so it was purely cosmetic and blocked text selection inside items).
- Two new Vitest cases (threshold + casing preservation), 13/13 pass.

## Deferred follow-ups (review nice-to-haves)
- **S2 — dropdown clipping**. CSS `overflow:auto` on the detail panel does clip absolutely-positioned descendants for low nodes. Mechanical fix: `<Teleport to="body">` around the dropdown + position from `getBoundingClientRect()`. Not done in this story; if a user reports it, file a follow-up that's <30 LOC.
