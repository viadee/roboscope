# Story HEAL-2: Suite-level Self-Healing toggle in the editor toolbar

Status: ready-for-dev

Epic: HEAL — Self-Healing opt-in ergonomics
Story Key: `heal-2-explorer-suite-level-toggle`

## Reasoning

HEAL-1 makes per-step opt-in easy, but most users will decide
"I want this whole flaky test suite to use healing" — switching 12
keywords by hand is still tedious. A single toolbar toggle in the
editor that promotes every heal-able keyword in the current
`.robot` file (and adds the library import) closes that loop while
still respecting the design invariants: **file is rewritten on disk
through the standard save path**, **per-keyword granularity is
preserved in the diff** (every Heal rewrite is one source line the
user sees in git), **runtime mutation is not introduced**.

## Change

### Reuse

The same `healToggle.ts` utility from HEAL-1, plus one extra:

- `applyHealToForm(form, mode: 'enable' | 'disable'): {
    form: RobotForm, changedKeywords: number
  }` — walks every step in `form.testCases[].steps` and
  `form.keywords[].steps`, applies `getHealVariant` /
  `getBaseKeyword` to each, returns a new form with the
  `Library    RoboScopeHeal` row added or removed via the same
  ensure / removeIfUnused helpers. Pure — does not mutate inputs.
  `changedKeywords` is the count of keyword renames (for the
  toast).

### UI

`frontend/src/components/editor/RobotEditor.vue` — toolbar:

- A new button `Self-Healing: Off / On` next to the existing tabs
  / save controls. Visible only on `.robot` files (current
  behaviour: the editor already gates by extension).
- The label reflects state: if **any** step in the parsed form
  uses a `Heal *` keyword, the toggle shows `On` (otherwise
  `Off`). Mixed state (some heal'd, some bare) still renders as
  `On` — clicking again to `Off` is the only consistent action
  (reverts everything to bare).
- Click → calls `applyHealToForm(form, mode)` with the inverse of
  current state, passes the new form back through the existing
  form-emit mechanism (so the standard unsaved-changes badge
  fires). Shows a toast: `n keywords switched to Self-Healing`
  (or back).
- The toggle is hidden when the form contains zero heal-able
  Browser keywords — there's nothing to toggle.

### i18n

`robotEditor.heal.toggleOn`, `robotEditor.heal.toggleOff`,
`robotEditor.heal.toastEnabled`,
`robotEditor.heal.toastDisabled`, all four locales.

## Out of scope

- Repo-wide bulk operation ("enable healing in every test under
  /flaky/"). Per-file is the right granularity for the trust
  invariants — bulk ops would lose the per-file review step.
- Suite-level *runtime* override via Robot tag. The existing
  `no-heal` tag is the per-test escape hatch (opposite direction
  — opt OUT of healing within a heal-enabled suite); we are NOT
  adding a `heal-suite` tag in this story.
- Library-argument config (budgets, confidence threshold). The
  toggle only adds the bare `Library    RoboScopeHeal` row;
  users who want config can add args manually.

## Edge cases

| Case | Behaviour |
|---|---|
| File with no Browser keywords at all | Toggle is hidden. |
| File with `Library    Browser` but every step is `Log` / `Run Keyword` (none heal-able) | Toggle hidden. |
| File has a step called `Click` but **no** `Library    Browser` import | Toggle hidden — the `Click` almost certainly resolves to a custom user keyword with the same name, and rewriting it to `Heal Click` would break the test rather than heal it. The gate (`hasBrowserLibraryImport \|\| hasRoboScopeHealImport`) is enforced by the new `healToggle.ts` helpers, with 11 unit tests pinning the matcher (canonical `Browser`, pip-name variants, case-insensitivity, the args-aware Library row, the no-Library negative path, …). |
| User invokes `enable` on a file already fully heal'd | No-op rewrite (changedKeywords = 0), no toast (suppress when 0). |
| User invokes `disable` on a file with mixed state | All Heal* rewritten to bare. Toast reports total switched. |
| User had a custom `Library    RoboScopeHeal    budget=3` row | Preserved on enable (no second row added). On disable, also preserved if it carries args, even when no Heal keyword is left — assume user knows why. |
| File has comments saying `# Click here` | Untouched — comment lines are not parsed as steps. |
| File uses `Run Keyword    Click    selector` (Click is an argument) | The argument value is in `step.args`, not `step.keyword`, so it is **not** rewritten. Test asserts this. |
| User has unsaved Code-tab edits, switches to Flow, clicks toggle | The form rebuild from the existing flow path already prompts a save first; no new dialog needed. |
| `.resource` file (not `.robot`) | Same logic applies — User Keywords in `.resource` files are valid. Toggle visible on both. |

## Verification

- Unit tests for `applyHealToForm`:
  - All-bare → all-heal'd in one pass (count + library import added).
  - All-heal'd → all-bare (count + library import removed when
    args empty).
  - Mixed → fully-heal'd or fully-bare based on mode.
  - File with zero heal-able keywords → no-op, no library import.
  - Custom-configured library row preserved across both directions.
  - User keywords (`form.keywords[].steps`) are walked too —
    pinned by a test where the only heal-able step lives in a
    user keyword.
- Component test: `RobotEditorHealToggle.spec.ts` mounts the
  editor with a fixture form, clicks the toggle, asserts the
  emitted form changed.
- i18n parity test (existing
  `locale-parity.spec.ts`) catches missing keys.

## Risk

- A user with the `no-heal` Robot tag on a specific test inside a
  fully-heal'd suite still gets the file rewritten on enable —
  the tag only suppresses runtime healing, not the source
  rewrite. This is the intended interaction (the tag is the
  per-test override layered on top of the file's keyword choice).
- If the user manually adds `Heal Foo` for a keyword that isn't
  in `HEAL_VARIANTS` (e.g., a custom Heal-prefixed user keyword
  they wrote themselves), `disable` will not touch it. Asserted
  by a test.
