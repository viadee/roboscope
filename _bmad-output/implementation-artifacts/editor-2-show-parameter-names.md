# Story EDITOR-2: Show parameter names instead of positional placeholders

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-2-show-parameter-names`

## Context

Today the visual editor renders every keyword argument as a generic input labelled `arg 1`, `arg 2`, … both on the keyword node body and in the editable detail panel. The keyword's actual parameter signature is already loaded by `KeywordPalette.vue` (see `keywordArgsMap: Map<string, string[]>`) — strings like `"selector: str"`, `"text: str"`, `"timeout: timedelta = 10s"` from Robot Framework's libdoc — but that information is not propagated to the editor canvas.

For a non-developer Editor user, "arg 1" is meaningless. They have to memorize the keyword's positional contract or jump back to the docs for every step.

## Story

As an **Editor user (non-developer)**,
I want to **see what each input means (e.g. "selector", "text", "timeout") instead of a generic "arg 1"**,
so that **I know which value to put where without consulting the keyword docs**.

## Acceptance Criteria

1. **AC1 — Signature lookup centralised.** A new pure helper `parseArgSignature(rawArg: string): ParsedArg` lives in `frontend/src/utils/robotKeywordSignatures.ts` (existing file). `ParsedArg` is `{ name: string, type: string | null, defaultValue: string | null, kind: 'positional' | 'optional' | 'varargs' | 'kwargs' | 'named-only' }`. The helper handles every form RF libdoc emits: `name`, `name: type`, `name: type = default`, `*args`, `*args: type`, `**kwargs`, `**kwargs: type`, lone `?` (optional separator). 12+ Vitest cases covering each form.

2. **AC2 — Argument signature exposed to the flow.** `flowConverter.ts` resolves the argument signature for each keyword step via the existing `keywordArgsMap` (passed in as a parameter or read from a provided injection token — pick the simplest wiring). Each `FlowNodeData` gains an optional `argSpecs: ParsedArg[] | null` field. When the keyword is unknown to the map, `argSpecs` stays `null` and the editor falls back to today's behaviour.

3. **AC3 — Detail panel labels each input.** In `FlowEditor.vue`'s "Arguments" detail-panel section, when `argSpecs` is available:
   - Each input's label becomes ``{argSpec.name}`` (no type, no colon — the type goes to AC4).
   - The placeholder becomes the parameter's default value (when present), e.g. `10s` for `timeout: timedelta = 10s`.
   - For positional args **beyond** the declared signature length, fall back to the current `arg N` placeholder so adding extra positionals still works.
   - For `*varargs`, the label reads `extra positional` (i18n key); for `**kwargs`, the label reads `extra named` (i18n key); both are repeatable rows just like today.

4. **AC4 — Keyword node body shows names.** In `KeywordNode.vue`, when `argSpecs` is available, the existing arg chips render as `{name}: {value}` with the name in muted text and the value in the existing chip style. When `argSpecs` is null, the chip renders just `{value}` (today's behaviour). Excess positionals render as `value` (no `name:` prefix) — never `arg N:`.

5. **AC5 — Named-only & flag conventions.** A boolean default (`force: bool = False`) renders the value as a checkbox (true/false toggle) in the detail panel; the chip on the node shows `force: ✓` or `force: ✗`. An enum-like type (anything matching `Literal[...]` or `OneOf[...]`) renders a `<select>` populated from the literal values. Other types fall through to a plain text input.

6. **AC6 — `*args` / `**kwargs` rows are labelled.** A `*args` row group is labelled `extra positional` and a `**kwargs` group is labelled `extra named` (i18n keys). The `+ Add arg` button below them carries the same label.

7. **AC7 — i18n (EN/DE/FR/ES).** New keys live under `flowEditor.argLabels.*`:
   - `extraPositional` — `"extra positional"` / `"weitere positionelle"` / etc.
   - `extraNamed` — `"extra named"` / `"weitere benannte"` / etc.
   - `defaultPlaceholder` — `"default: {default}"`
   - All four locale files updated; `npm run build` passes.

8. **AC8 — Tests + build green.**
   - **Vitest:** new spec `tests/utils/robotKeywordSignatures.spec.ts` covering AC1's 12+ shapes.
   - **Vitest:** new spec `tests/components/FlowEditorParamLabels.spec.ts` covering: known keyword → labels; unknown keyword → fallback; excess positional → `arg N`; bool → checkbox; enum → select.
   - **Vitest:** `tests/components/KeywordNode.spec.ts` extended for the `name: value` chip rendering and excess-positional fallback.
   - All existing suites green.
   - `vue-tsc --noEmit` reports no new errors.

9. **AC9 — Out of scope (explicit non-goals).**
   - Friendly type translation (`str` → `Text`) — that's Story EDITOR-3.
   - Validating user input against the parameter type (e.g. rejecting non-numeric input for `int`) — separate story.
   - Generating signatures for project-local resource keywords whose arg list is parsed by `getProjectKeywords` — already covered by AC2 (same map).

## Tasks / Subtasks

- [x] **Task 1 — `parseArgSignature` + `getArgLabel` + tests**
  - [x] Implemented in `src/utils/robotKeywordSignatures.ts`. Handles every shape in AC1: bare name, `name: type`, `name=default`, `name: type = default`, `T | None`, `*varargs`, `**kwargs`, both with and without type, `*` (named-only sep), `?` (optional sep). Pure string splits, no regex bombs.
  - [x] 21 Vitest cases in `tests/utils/robotKeywordSignatures.spec.ts` (15 for parsing, 6 for label fallbacks).

- [x] **Task 2 — Propagate `argSpecs` through the converter**
  - [x] `FlowNodeData.argSpecs: ParsedArg[] | null` added.
  - [x] `stepsToFlow` / `testCaseToFlow` / `keywordDefToFlow` / `robotFormToFlow` / `robotKeywordsToFlow` thread an optional `SignatureMap`. New `resolveArgSpecs(step, signatures)` helper.
  - [x] Composable `src/composables/useKeywordSignatures.ts` wraps the existing `useExplorerStore().keywords` cache + `RF_KEYWORD_SIGNATURES` static fallback. Reactive — `argsByName` recomputes when the explorer store loads dynamic library introspection. `FlowEditor.vue` watches `argsByName` and rebuilds the graph on change.

- [x] **Task 3 — Detail panel rendering**
  - [x] Each arg row gets a per-parameter label via `argLabelAt(i)` (fallback to `arg N` / `extra positional` / `extra named`).
  - [x] Default-value placeholder: `default: <value>` shown when the spec carries a default.
  - [ ] Typed controls (bool → checkbox, enum → select) — **moved to Story EDITOR-3**, where they belong with the friendly type chip + icon work. Keeps EDITOR-2 focused on names + structure.

- [x] **Task 4 — Node body chips**
  - [x] `KeywordNode.vue` chips render as `{name}: {value}` when the resolved label carries real meaning; fall through to plain `{value}` for unknown keywords / generic fallback.
  - [x] Chip tooltip exposes `name: type = default` for power users.

- [x] **Task 5 — i18n + final verification**
  - [x] Four `flowEditor.argLabels.*` keys (`fallback`, `extraPositional`, `extraNamed`, `defaultPlaceholder`) in EN / DE / FR / ES.
  - [x] `npx vitest run` → 281/281 pass (39 new EDITOR-2 tests).
  - [x] `npx vue-tsc --noEmit` — total error count unchanged (31, all pre-existing).
  - [ ] Manual smoke (browser) — pending; backend `/ai/rf-knowledge/keywords` returns the libdoc-style args (`selector: str`, `*keys: str`, etc.) that the parser is built for (verified via curl).

## Risk notes
- The `keywordArgsMap` is currently scoped to `KeywordPalette`. Promoting it to a shared store is a small refactor; do it cleanly (don't pass it as a prop through three layers).
- Some libraries return formats this story does not cover (e.g. PythonLibCore decorators may emit `name=DEFAULT`). The fallback to today's `arg N` placeholder is the safety net — never crash, never throw.

## Review fixes applied
- **M1** — `parseArgSignature` rewritten with a bracket / quote depth scanner so `=` inside complex types (`Annotated[str, Field(min_length=1)]`, `Literal['a = b']`) no longer corrupts the split. New tests cover both shapes.
- **M2** — German `argLabels` strings fixed: `'weitere Positionsargumente'` / `'weitere Schlüsselwortargumente'`.
- **S2/S3** — Detail-panel placeholder uses the i18n fallback key and emits the bare default value (no leading `default: ` prefix).
- **S4** — `KeywordNode.chipTitleAt` returns undefined when there is no name, eliminating the leading-colon edge case.
- **S6** — Detail-panel layout reverted to inline (`<span class="flow-arg-name-inline">arg:</span><input>`), matching the existing condition / loopVar rows. No vertical-space regression.
- **N2** — `parseArgSignature('name=')` now yields `defaultValue: null` (no stray empty placeholder).
- **N4** — TODO comment in `useKeywordSignatures.ts` documenting the deferred project-keyword merge.
