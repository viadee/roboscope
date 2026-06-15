# Story FE-TPL: [Template] data-driven rows as an editable table

- **Status:** Planned
- **Priority:** P1
- **Parent:** Flow Editor — Verification & Hardening (deferred item N2)

## Context
A data-driven test uses `[Template]    <Keyword>` and then BODY ROWS where each
row is one set of arguments passed to the template keyword:

```
*** Test Cases ***
Addition
    [Template]    Add Should Be
    1    2    3
    5    7    12
```

Today the parser treats each data row as a regular keyword step (`1` becomes the
"keyword", `2 3` its args) — semantically wrong and uneditable as data. This is
the one deferred item that is currently **mis-modelled**, not merely un-pretty,
so it is P1.

## Acceptance Criteria
- **AC1:** When a test case has a `[Template]` setting, its body rows parse as
  **data rows** (a list of cell-arrays), NOT as keyword steps.
- **AC2:** Such a test renders a **table node**: columns are positional args,
  rows are datasets; add row / remove row / edit cell / add column.
- **AC3:** Round-trip: parse → serialize reproduces the template keyword + data
  rows (RF-equivalent whitespace). A test WITHOUT `[Template]` is unaffected.
- **AC4:** Editing the `[Template]` keyword name still works via the existing
  setting-meta side note; clearing it converts rows back to plain steps safely
  (or leaves them as data with an empty template — documented).
- **AC5:** Draft-buffer discipline for cell edits (no `selectedNode` teardown).

## Tasks
- `robotTextIO.ts`: add `templateRows?: string[][]` to `RobotTestCase`; parser
  routes body rows into `templateRows` when `template` is set; serializer emits
  them. Round-trip fixtures.
- `flowConverter.ts`: emit a `template-table` node when `templateRows` present.
- `FlowEditor.vue`: table editor (rows/cols, add/remove/edit on blur).
- i18n EN/DE/FR/ES.

## Tests
- Unit `robotTextIO` template round-trip (rows preserved, non-template
  unaffected); `FlowEditorTemplateTable.spec.ts` for the converter node.
- e2e `flow-editor-template.spec.ts`: load data-driven suite → table node shows
  N rows × M cols; add a row → code round-trip shows the new data row.

## Risk
Parser ambiguity: only route rows to `templateRows` when `[Template]` is present
on the test; otherwise keep current keyword-step parsing. Control structures
inside a templated test are rare/invalid — treat a row starting with FOR/IF/etc.
as a normal step (don't force it into the table).
