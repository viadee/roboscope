# Story EDITOR-6: Bugfix — flow editor misses test-case / file switch

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-6-flow-editor-misses-testcase-switch`

## Reported

> Wenn ich im Flow-Editor bin bekommt er manchmal nicht mit, wenn ich einen anderen Testfall auswähle und der Inhalt wechselt nicht.

## Root cause

Two compounding bugs in `RobotEditor.vue` + `FlowEditor.vue`:

1. **`RobotEditor.vue` only re-parses on the visual tab.** The `watch(() => props.content, ...)` block at line 1572 had `if (activeTab.value === 'visual')` as the gate for `parseRobotToForm(newContent)`. When the user was on the **flow** tab and the explorer fed a new file's content via the `props.content` prop, the form was never re-parsed — the flow editor kept rendering the previous file's `RobotForm` indefinitely.

2. **`FlowEditor.vue`'s `suppressFitView` flag could swallow the file-switch rebuild.** The watcher on `[() => props.form, activeSection]` did:

       if (suppressFitView) { suppressFitView = false; return }

   `suppressFitView = true` is set by every internal flow-editor mutation path (`rebuildAndReselect`, `deleteStep`, `insertStepAt`, `reorderStep`) — these mutate `props.form` and rely on the watcher to fire-and-skip so the canvas isn't re-fit on every keystroke. **Vue batches deep-watch fires.** If the watcher's microtask hadn't yet run when the user clicked another file in the explorer, the file-switch mutations got batched with the leftover internal mutation. The single batched fire saw `suppressFitView=true`, returned, and the rebuild was lost.

## Fix

**Patch 1 (`RobotEditor.vue:1577`)** — re-parse for both `visual` and `flow` tabs. Code-tab path is unchanged (CodeMirror handles its own content sync).

**Patch 2 (`FlowEditor.vue:137`)** — separate the "skip fitView" concern from the "skip rebuild" concern. The watcher now always rebuilds; only the `fitView` calls are gated on the flag. Also keeps the current selection / `activeItemIndex` when an internal edit triggered the watcher.

## Verification

- Manual: open `recording.robot` in flow tab → edit a step → switch to a different `.robot` file in the explorer → flow editor now shows the new file's first test case (regression reproduced before patch, gone after).
- Vitest: existing 284-case suite still green; the bug surface is the watcher gating, which is exercised indirectly by `FlowEditorSelectorPicker.spec.ts` and `FlowEditorParamLabels.spec.ts` (both verify `robotFormToFlow` produces correct nodes for arbitrary inputs).
- vue-tsc: no new errors.

## Out of scope

- Refactoring the form-mutation pattern in `RobotEditor.parseRobotToForm` (which assigns 5 top-level array fields one by one rather than swapping the form reference). That's a deeper architectural cleanup; the current fix removes the user-visible failure without that refactor.
