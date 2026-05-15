# Story HEAL-1: Per-step Self-Healing toggle in the Flow Editor

Status: review

Epic: HEAL — Self-Healing opt-in ergonomics
Story Key: `heal-1-flow-editor-per-step-toggle`

## Reasoning

Today the user has to leave the visual editor, switch to the Code tab,
manually rename `Click` to `Heal Click` (and 12 other variants), and
also remember to add `Library    RoboScopeHeal` to the Settings
section. This breaks the Flow Editor's "single-view editing" promise
for the one feature that benefits non-developers the most.

A per-step toggle in the detail panel makes the choice local,
reversible, and visible — the granularity that matches the design
invariant `explicit per-keyword opt-in (no monkey-patching the Browser
library globally)`. Each toggle click rewrites exactly one keyword
name in the source via the form path (`RobotStep.keyword`), never via
regex on raw text.

## Change

### New utility

`frontend/src/utils/healToggle.ts` — pure functions for the
Browser ↔ Heal keyword name mapping:

- `HEAL_VARIANTS: Readonly<Record<string, string>>` — 13 entries
  derived from `backend/src/recording/heal/library.py`
  (Click, Fill Text, Type Text, Hover, Press Keys, Wait For
  Elements State, Upload File, Check Checkbox, Uncheck Checkbox,
  Select Options By, Get Text, Get Element Count, Drag And Drop).
- `getHealVariant(keyword)` → `'Heal X'` or `null`.
- `getBaseKeyword(keyword)` → bare keyword name, or `null` for
  non-Heal inputs.
- `isHealableKeyword(keyword)` → `true` for bare or Heal* of any of
  the 13 supported names.
- `isHealedKeyword(keyword)` → `true` only for Heal* form.
- `ensureRoboScopeHealLibrary(settings)` /
  `removeRoboScopeHealLibraryIfUnused(settings, hasHealKeyword)` —
  add or remove `{ key: 'Library', value: 'RoboScopeHeal', args: [] }`
  in the form's Settings array, idempotent.

### UI

`frontend/src/components/editor/FlowEditor.vue` — detail panel
branch for a `keyword` (or `assignment`) step:

- A new checkbox `Self-Healing` is rendered **only** when the
  current step's keyword name (after stripping a possible `Heal `
  prefix) is in `HEAL_VARIANTS`. Hidden otherwise.
- The checkbox is bound to `isHealedKeyword(step.keyword)`. Toggling
  it:
  - On enable: rewrite the step's `keyword` from `Click` to
    `Heal Click`, and call `ensureRoboScopeHealLibrary` on the
    form's `settings`.
  - On disable: rewrite the step's `keyword` from `Heal Click` back
    to `Click`, and call `removeRoboScopeHealLibraryIfUnused` after
    a single pass that determines whether ANY step in the file
    (across all test cases + user keywords) still uses a Heal*
    keyword.
- Edits go through the existing `updateStepFromNode` /
  `rebuildAndReselect` path, so the standard unsaved-changes badge
  appears and the user saves explicitly (no runtime mutation).

### i18n

`flowEditor.heal.toggleLabel` and `flowEditor.heal.toggleHint` in
EN/DE/FR/ES.

## Out of scope

- Per-file batch toggle (covered by HEAL-2).
- A custom-Heal-keyword registry (only the 13 stock ones today).
- Touching steps that have a heal-able name but live inside an
  argument position (e.g., `Run Keyword    Click    selector`) —
  the form path only exposes the **step keyword** field, so this
  is structurally impossible to hit.

## Edge cases

| Case | Behaviour |
|---|---|
| Step keyword is unknown to the heal map | Checkbox is hidden. |
| Step keyword IS in the heal map but the file does **not** import `Library    Browser` or `Library    RoboScopeHeal` | Checkbox is hidden. Same gate as HEAL-2: a step called `Click` in a file without Browser library import is almost certainly a custom user keyword, and rewriting it to `Heal Click` would break the test. |
| Step is in a User Keyword (`*** Keywords ***`), not Test Case | Checkbox is shown — `Heal Click` is a valid keyword in any context. |
| Step is `assignment` (`${var}=    Click    selector`) | Checkbox is shown; the keyword name still rewrites. The return-var list is untouched. |
| User already added `Library    RoboScopeHeal` manually with extra args (e.g., budget config) | `ensureRoboScopeHealLibrary` is a no-op when a `Library` row with `value === 'RoboScopeHeal'` already exists. `removeRoboScopeHealLibraryIfUnused` only removes when `args.length === 0` — the user's configured row is preserved. |
| Last Heal* keyword on the file is disabled | Library import auto-removes (only if it was the default zero-args form, see above). |
| Two test cases each have one heal'd keyword, user disables one | Library import stays — the other test case still needs it. |
| Keyword name parsed with extra whitespace (`"  Click  "`) | The map lookup uses `.trim()`. Save round-trip normalises whitespace anyway. |

## Verification

- New unit tests: `frontend/src/tests/utils/healToggle.spec.ts`
  covering the map, `getHealVariant`, `getBaseKeyword`,
  `isHealableKeyword`, `isHealedKeyword`,
  `ensureRoboScopeHealLibrary` (3 idempotency paths),
  `removeRoboScopeHealLibraryIfUnused` (preserve-when-configured,
  preserve-when-still-used, remove-when-orphan).
- New component test:
  `frontend/src/tests/components/FlowEditorHealToggle.spec.ts`
  asserting the checkbox is hidden on a non-heal-able step,
  visible on a heal-able step, and that toggling it rewrites the
  step's keyword in the emitted form.
- vitest stays at 100 %; vue-tsc + prod build clean.

## Dev Agent Record

### Completion Notes (2026-05-15)

Implementation was already complete on `feat/heal-toggle`. The following were present and verified:

- `frontend/src/utils/healToggle.ts` — 13-entry `HEAL_VARIANTS` map, `getHealVariant`, `getBaseKeyword`, `isHealableKeyword`, `isHealedKeyword`, `ensureRoboScopeHealLibrary`, `removeRoboScopeHealLibraryIfUnused`, `countHealedSteps`, `hasBrowserLibraryImport`, `hasRoboScopeHealImport`.
- `frontend/src/components/editor/FlowEditor.vue` — `selectedStepHealMode` computed + `onStepHealToggle` handler + checkbox UI in detail panel with `data-testid="flow-step-heal-toggle"`.
- i18n `flowEditor.heal.toggleLabel` / `toggleHint` in EN/DE/FR/ES — locale parity test passes.
- `frontend/src/tests/utils/healToggle.spec.ts` — 53 tests covering map, classifiers, library import add/remove, `applyHealToForm`, immutability.
- `frontend/src/tests/components/FlowEditorHealToggle.spec.ts` — 28 tests (created this session) mirroring `selectedStepHealMode` and `computeNextKeyword` logic: hidden for non-keyword steps / non-heal-able keywords / missing library import; off/on classification; rewrite roundtrip for all 13 variants.

vitest full suite: 717 passed, 0 failed.

### File List

- `frontend/src/utils/healToggle.ts` (new)
- `frontend/src/tests/utils/healToggle.spec.ts` (new)
- `frontend/src/tests/components/FlowEditorHealToggle.spec.ts` (new)
- `frontend/src/components/editor/FlowEditor.vue` (modified — HEAL-1 toggle)
- `frontend/src/i18n/locales/en.ts` (modified — `flowEditor.heal.*`)
- `frontend/src/i18n/locales/de.ts` (modified — `flowEditor.heal.*`)
- `frontend/src/i18n/locales/fr.ts` (modified — `flowEditor.heal.*`)
- `frontend/src/i18n/locales/es.ts` (modified — `flowEditor.heal.*`)
