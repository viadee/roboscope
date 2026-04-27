# Story EDITOR-9: Named-parameter picker on "+ Add argument"

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-9-named-param-picker`

## Reported

> Im Flow-Editor möchte ich die Möglichkeit haben, wenn ich ein Argument hinzufüge, dass ich auswählen kann welchen Parameter ich hinzufügen möchte (bei Evaluate z.B. "modules" oder "namespace" etc.).

## Story

As an **Editor user**,
I want **the "+ Add argument" button to let me pick from the keyword's unused parameters**,
so that **I don't have to know the positional order or hand-type `name=value`**.

## Behavior

1. The "+ Add argument" button opens a small popover next to itself.
2. The popover lists the keyword's unused parameters in signature order, each row showing the parameter name + its default value (if any).
3. Clicking a parameter:
   - If it's the **next positional** in order (its spec index == current `args.length`): a positional slot is appended with the parameter's default value (or empty).
   - Otherwise: a **named slot** is appended as `name=`. Robot Framework reads named args anywhere after the last positional, so no positional padding is required.
4. A **"Custom value"** row at the bottom appends an empty positional slot for keywords with no signature (or for power users who want a free-form value).
5. The picker closes on selection, on click-outside, and on Esc.
6. If the keyword has no signature **and** no unused params, the popover skips straight to the "Custom value" path (single click — no menu).

## Per-slot label / type resolution

`argLabelAt(i)` and `argTypeAt(i)` now detect the `name=...` named-arg form: when `step.args[i]` matches `^[A-Za-z_]\w*\s*=` and the captured name is one of the keyword's `argSpecs`, that spec's name + type is used to label the slot. Falls back to positional spec lookup otherwise.

This means a step like `Evaluate    1+1    namespace=${vars}` shows two arg rows labelled `expression: …` and `namespace: …` — even though `namespace` is positionally `argSpecs[2]`, not `[1]`.

## Acceptance Criteria

- AC1: Picker UI rendered as a small `<ul>` popover anchored to the "+" button.
- AC2: Lists unused params (skipped names already used positionally OR as `name=` in another slot) in signature order.
- AC3: Picking the immediate next positional appends a positional slot.
- AC4: Picking any other named param appends `name=`.
- AC5: "Custom value" row always present, appends an empty positional slot.
- AC6: Closes on Esc / click-outside / pick.
- AC7: `argLabelAt` / `argTypeAt` detect `name=...` and resolve the spec by name; positional fallback unchanged.
- AC8: Existing `addArg()` behavior preserved as the "Custom value" path so no test regression.
- AC9: `*args` / `**kwargs` rows excluded from the named picker for V1 (always reachable via "Custom value"). Documented as a follow-up.
- AC10: i18n keys `flowEditor.addArgPicker.{title,custom,noUnused,namedHint}` in EN/DE/FR/ES.

## Out of scope

- Bulk add of multiple params in one go.
- Reordering existing positional args.
- Validating that named args don't clash with positional slots already filled.
- `*args` / `**kwargs` quick-add buttons (use Custom value).
