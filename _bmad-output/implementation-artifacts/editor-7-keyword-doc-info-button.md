# Story EDITOR-7: Keyword documentation popup from the detail panel

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-7-keyword-doc-info-button`

## Reported

> Im Flow-Editor soll direkt im Detail-View ein kleiner i-Button (neben Hoch und Runter Buttons) sein, über den man die Dokumentation zum Keyword abrufen kann (als Dialog).

## Story

As an **Editor user**,
I want **a small "i" info button next to the up/down/delete buttons in the flow-editor detail panel**,
so that **I can read the keyword's documentation in a dialog without leaving the editor**.

## Change

1. New component `frontend/src/components/editor/flow/KeywordDocModal.vue` — wraps `BaseModal`, takes `keyword: string` + `library?: string` + `doc?: string` + `args?: string[]` props, renders a clean view of the keyword's signature + doc (or a "no documentation available" placeholder for static-fallback keywords).
2. `useKeywordSignatures()` gains a `getKeywordInfo(name)` accessor returning `{ display, library, doc, args } | null` from `useExplorerStore().keywords` (only dynamic kws have `doc`).
3. `FlowEditor.vue` detail-panel header gets an info button between "Move up/down" and "Delete":
   - Only rendered for `stepType === 'keyword' | 'assignment'` AND a non-empty `step.keyword`.
   - Click opens `KeywordDocModal` for the current `step.keyword`.
   - Tooltip: localised "Show documentation".

## Acceptance Criteria

1. **AC1** — info button rendered as `<button class="flow-action-btn">i</button>` in the detail-panel actions row, between the up/down arrow buttons and the delete `×`.
2. **AC2** — Hidden for control-flow / non-keyword node types (IF, FOR, comments, etc.) and for keyword/assignment steps with empty `step.keyword`.
3. **AC3** — Click opens a modal that shows: keyword display name (large), library tag (e.g. "Browser" / "BuiltIn"), arguments list (`ParsedArg` rendered as `name: type = default` lines), and the raw `doc` string in a `<pre>` block (or "No documentation available." when the doc is empty/unknown).
4. **AC4** — Modal is closeable via Esc, the backdrop click, or an explicit close button (BaseModal handles all three).
5. **AC5** — i18n: 3 keys in EN/DE/FR/ES — `flowEditor.docModal.title` ("Keyword documentation"), `flowEditor.docModal.noDoc` ("No documentation available."), `flowEditor.docModal.argsHeader` ("Arguments").
6. **AC6** — All existing tests still pass; new Vitest spec covers `getKeywordInfo` returning the doc for dynamic kws and `null` for unknown.

## Out of scope
- Markdown rendering of the doc string (RF library docs sometimes use a tiny subset of formatting). `<pre>` is enough for V1.
- Inline doc tooltip on hover (the explicit button + modal is what the user asked for).
- Linking to external library doc URLs.
