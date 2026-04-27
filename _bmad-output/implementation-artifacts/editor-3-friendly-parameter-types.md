# Story EDITOR-3: Friendly parameter-type display in the Visual Flow Editor

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-3-friendly-parameter-types`

## Context

After Story EDITOR-2, each argument input is labelled with the parameter name. The raw type string from Robot Framework's libdoc is still developer-facing jargon: `str`, `int`, `bool`, `float`, `?`, `Any`, `Path`, `timedelta`, `AssertionOperator | None`, `*args`, `**kwargs`, `dict[str, str]`. A non-developer Editor user does not know that `?` means "optional" or that `timedelta` accepts `5s` / `00:00:05`.

The keyword signature is already available (Story EDITOR-2's `ParsedArg.type`). This story adds a translation layer + lightweight typed inputs.

## Story

As an **Editor user (non-developer)**,
I want to **see a human-friendly type hint instead of `str` / `?`**,
so that **I understand what kind of value the parameter expects (text, number, on/off, …)**.

## Acceptance Criteria

1. **AC1 — Type-mapping table.** A pure function `friendlyType(rawType: string | null): { icon: string, label: string, control: 'text' | 'number' | 'checkbox' | 'select' | 'duration' }` lives in `src/utils/robotKeywordSignatures.ts`. The mapping is i18n-driven (returns an i18n key, not the localised string). Required mappings:

   | Raw                           | Icon  | Label key                    | Control     |
   |-------------------------------|-------|------------------------------|-------------|
   | `str`                         | `Aa`  | `argTypes.text`              | `text`      |
   | `int`                         | `123` | `argTypes.integer`           | `number`    |
   | `float`                       | `1.0` | `argTypes.number`            | `number`    |
   | `bool`                        | `✓`   | `argTypes.yesNo`             | `checkbox`  |
   | `timedelta`                   | `⏱`  | `argTypes.duration`          | `duration`  |
   | `Path` / `pathlib.Path`       | `📁`  | `argTypes.path`              | `text`      |
   | `Any`                         | `*`   | `argTypes.any`               | `text`      |
   | `?` (lone optional separator) | `–`   | `argTypes.optional`          | `text`      |
   | `*args` / `*args: T`          | `…`   | `argTypes.extraPositional`   | `text`      |
   | `**kwargs` / `**kwargs: T`    | `…=`  | `argTypes.extraNamed`        | `text`      |
   | `Literal[...]` / `Enum`       | `▼`   | `argTypes.choice`            | `select`    |
   | `T | None` (any T)            | `?T`  | reuses `T`'s key + `optional`| same as `T` |
   | `dict[...]` / `list[...]`     | `[ ]` | `argTypes.collection`        | `text`      |
   | unknown / null                | `?`   | `argTypes.unknown`           | `text`      |

2. **AC2 — Detail panel uses friendly label + control.** In `FlowEditor.vue`'s detail panel, each argument row shows a small **type chip** next to the parameter name (icon + localised label, e.g. `Aa Text` / `123 Number` / `✓ On / Off`). The input control matches AC1's `control` field:
   - `text` → `<input type="text">` (today's behaviour)
   - `number` → `<input type="number">` (with `step="1"` for `int`, `step="any"` for `float`)
   - `checkbox` → `<input type="checkbox">` rendering the value as `True` / `False` strings (round-trips losslessly to `.robot` source).
   - `duration` → `<input type="text">` with placeholder `e.g. 5s, 1min, 00:00:05` and a small inline hint.
   - `select` → `<select>` populated from the `Literal[...]` / `OneOf[...]` values.

3. **AC3 — Power-user tooltip.** The friendly type chip has a tooltip that exposes the **original raw type string** (e.g. `str`, `AssertionOperator | None`). Power users still see what RF reports.

4. **AC4 — Optional combinator.** `T | None` types render the type chip with a small `?` decorator and the input is **not** marked as required. Pure `?` (lone optional separator from RF positional-only marker) renders the `optional` chip with no input control change.

5. **AC5 — Keyword node body shows the icon.** When `KeywordNode.vue` renders the chip `{name}: {value}` (Story EDITOR-2), an additional small icon prefix from AC1 appears: `Aa selector: text=…` / `✓ wait: True`. The icon stays inside the existing chip; no layout regression.

6. **AC6 — Default-value display.** When the parameter has a default and the user has not entered anything, the input shows the default as a placeholder (already from EDITOR-2 AC3). This story adds: for `bool` + `checkbox`, the **uncontrolled state** of the checkbox reflects the default (e.g. `force: bool = False` → checkbox unchecked by default).

7. **AC7 — i18n (EN/DE/FR/ES).** All `argTypes.*` keys from AC1 exist in all four locales. EN copy is friendly and short (≤ 16 chars per label). DE/FR/ES translations follow the existing tone. `npm run build` passes.

8. **AC8 — Tests + build green.**
   - **Vitest:** `tests/utils/friendlyType.spec.ts` — 14+ cases covering every row in AC1's table plus the `T | None` combinator.
   - **Vitest:** `tests/components/FlowEditorTypedControls.spec.ts` — `bool` → checkbox round-trip, `int` → number input, `Literal[...]` → select with options.
   - **Vitest:** `tests/components/KeywordNode.spec.ts` extended for the icon prefix.
   - All existing suites green.
   - `vue-tsc --noEmit` reports no new errors.

9. **AC9 — Out of scope.**
   - **Type validation that blocks save** — out of scope. We render typed controls but do not block save when the user types `abc` into a number input. (Robot Framework will reject it at runtime, the editor stays permissive.)
   - **Custom-type catalogues per library** (e.g. Browser-specific `SelectionStrategy`) — out of scope; they'll fall through the unknown bucket. Could be a follow-up if friction emerges.
   - **Translating type strings of project-local resource keywords** whose libdoc-style typing is freeform — out of scope; today they have no type info anyway.

## Tasks / Subtasks

- [x] **Task 1 — `friendlyType` + bool round-trip helpers + tests**
  - [x] Implemented in `src/utils/robotKeywordSignatures.ts`. Handles `str`, `int`, `float`, `bool`, `timedelta`, `Path`, `Any`, `Literal[...]`, `OneOf[...]`, `T | None`, `dict/list/tuple`, unknown bucket.
  - [x] 19 new Vitest cases (15 for `friendlyType`, 4 for `readBoolValue` / `writeBoolValue`).

- [x] **Task 2 — Render type chip in detail panel**
  - [x] Inline `<span class="flow-arg-type-chip">` per arg row carries icon + localised label + raw-type tooltip + optional `?` decorator.
  - [x] Hidden for the first-arg selector slot when the SelectorPicker is rendered (already carries its own visual context).

- [x] **Task 3 — Typed input controls**
  - [x] Detail panel switches input element by `friendlyType().control`: `checkbox` (bool, round-trips True/False), `select` (Literal/OneOf with parsed choices), `number` (int with `step="1"`, float with `step="any"`), `duration` (text + localised hint), text fallback.
  - [x] `readBoolValue` accepts True/true/yes/on/1; `writeBoolValue` always emits canonical `True` / `False`.

- [x] **Task 4 — Node body icon prefix**
  - [x] `KeywordNode.vue` adds a small icon prefix inside each chip (`Aa selector: text=...`, `123 timeout: 10`, `✓ wait: True`, `▼ button: left`). Unknown-type chips skip the prefix to avoid noise.

- [x] **Task 5 — i18n + verification**
  - [x] 12 `argTypes.*` keys + `optionalSuffix` + `durationHint` in EN / DE / FR / ES.
  - [x] `npx vitest run` → 320/320 pass (19 new EDITOR-3 tests + 3 KeywordNode icon-prefix cases).
  - [ ] Manual smoke (browser) — pending; the existing `recording.robot` example renders `selector` (`Aa Text`), `button` (`▼ Choice`), `*keys` ((extra positional)) and bool/numeric Browser-keyword args with their typed controls.

## Risk notes
- **Don't over-translate.** Resist the urge to translate `JsonReply` / `BrowserContext` / library-specific types. They land in the `argTypes.unknown` bucket with the raw type in the tooltip — that's the right answer.
- **Boolean round-tripping.** Robot Framework accepts `True`/`False`/`yes`/`no`/`on`/`off`. We pick `True`/`False` as the canonical write form because it is the most common and reads cleanly in the source. Reading existing `.robot` files needs to handle the others as truthy/falsy when populating the checkbox initial state — add 4-5 cases for that.

## Review fixes applied
- **M1** — `select` control prepends an extra "(custom)" option when `args[i]` already holds a value not in `Literal[...]` choices, so legacy values stay visible and aren't silently overwritten.
- **M2** — typed inputs (`checkbox`, `select`, `number`, `duration`) fall back to plain text whenever `args[i]` is a Robot Framework variable reference (`${VAR}`, `@{LIST}`, `&{DICT}`). New `isVariableRef()` helper. Prevents `${TRUE}` getting nuked to literal `False` on the first checkbox toggle.
- **M3** — `friendlyType` now handles `Optional[T]` (PEP 484 spelling) and arbitrary unions (3-way `int | None | str`, `None | T`, etc.). New `splitTopLevel(body, sep)` helper for bracket-aware splitting.
- **S2** — `parseLiteralChoices` upgraded: outer regex captures up to the LAST `]` (so nested brackets in choice values work), state machine honours `\\` escapes, and a depth counter ignores commas inside nested brackets.
- **S3** — `argTypes` is now a `computed` so each render resolves once per row instead of 6-8× from inline template usages.
- **N3** — chip guard tightened to mirror the picker guard (`!(i === 0 && selectorPickerVisible && selectedNodeData.recording)`).
- **N4** — select-placeholder option is now `disabled hidden` so users can't accidentally clear via keyboard nav.
- 6 new test cases (3 `friendlyType` review-fix cases + 2 `isVariableRef` + 1 already counted in the original commit's 19); full suite 325/325.
