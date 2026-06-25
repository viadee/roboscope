# Epic RES — Architecture

**Status**: Planning → ready for implementation
**Date**: 2026-06-18
**Architect**: Winston
**Parent**: [res-prd.md](./res-prd.md)

## Guiding principle

Reuse, don't rebuild. `FlowEditor.vue::addLibrary(name)` already routes a name
ending in `.resource` or containing `/` to a `Resource` import (and dedupes,
and emits `libraries-changed`). `addNodeFromPalette(step, library)` already
calls `addLibrary(library)` when `library` is set. The entire fix is: **make
the palette pass the resource file path as `library` for project keywords that
live in a different file than the one being edited.**

## 1. Data we have

- `ProjectKeyword = { name, file_path, arguments }` (`api/explorer.api.ts`), `file_path` repo-relative (e.g. `resources/common.resource`).
- `KeywordPalette.vue` already has `props.filePath` (the open file, repo-relative) and `projectKeywords.value`.
- Project keywords are grouped into `Project: <basename>` categories, with the open file's category flagged `isCurrentFile`.

## 2. Changes

### a. Path util — `frontend/src/components/editor/flow/resourcePath.ts`
```
resourceImportPath(openFile: string, resourceFile: string): string
```
Both inputs repo-relative. Returns the path from the open file's **directory**
to `resourceFile`, POSIX separators (e.g. open `tests/login.robot`, resource
`resources/common.resource` → `../resources/common.resource`; same dir →
`common.resource`). Pure, unit-testable. (Mirrors RF's "Resource paths are
relative to the importing file".)

### b. Palette — thread the source path
- Build a `Map<string, string>` name → `file_path` from `projectKeywords` (when a name appears in multiple files, last wins — acceptable v1; the realistic case is unique keyword names across resources).
- Add a handler `addProjectKeyword(name)` used by the project-category items: if the keyword's source `file_path !== props.filePath`, compute `resourceImportPath(props.filePath, file_path)` and emit it as the `library` arg of `add-node`; otherwise emit no library (same-file keyword = already local).
- BuiltIn / Library / Control keyword paths are unchanged (`libraryHintFor` still returns the lib name or undefined). The current-file project category passes no import.

### c. FlowEditor / RobotEditor — no change
`addNodeFromPalette` → `addLibrary(path)` already produces `Resource    <path>`
in `*** Settings ***`, deduped, and triggers a palette refresh. The text
serializer already round-trips `Resource` imports (existing `robotTextIO`
contract).

## 3. Guards (FR-3)
- Source file == open file → no import (local keyword).
- BuiltIn / Library / Control keyword → existing behavior (lib name or none), never a Resource path.
- Dedupe is `addLibrary`'s existing responsibility.

## 4. Risks / decisions
- **Duplicate keyword names across resources**: the name→path map collapses them; v1 picks one. Low real-world risk; note it. (A future refinement could carry `file_path` on the palette item itself.)
- **Drag-and-drop path**: `makeStepFromDrag` doesn't carry a library/resource. v1 covers the click + "+" add path (the primary insert flow, same one GOV/control-structures use). Drag auto-import is a follow-up (noted).

## 5. Test strategy
- **Unit (util)**: `resourcePath.spec.ts` — same dir, parent dir, nested, identical file, Windows-style input tolerance.
- **Unit (palette/flow)**: a `.resource` keyword insert adds the `Resource` import; a same-file/BuiltIn/Library insert does NOT.
- **E2E (real UI)**: seed a repo with `resources/common.resource` (defining a keyword) + a test file; open the test in the Flow editor, insert the resource keyword from the palette, Save, and assert the saved `.robot` contains `Resource    ../resources/common.resource` and the keyword call.

## 6. Handoff
→ **Implementation (Amelia)**: the util + palette threading + tests. Then review + E2E.
