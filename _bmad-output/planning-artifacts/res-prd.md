# Epic RES — Repository Resource Files — PRD

**Status**: Planning → ready for architecture
**Date**: 2026-06-18
**Owner / PM**: John
**Parent**: [presentation-feedback-epics.md](./presentation-feedback-epics.md)
**Epic**: RES

## 1. What already exists (do NOT rebuild)

- **Discovery**: `backend/src/explorer/service.py::parse_robot_keywords_in_repo` extracts every user-defined keyword (name + `[Arguments]`) from all `.robot`/`.resource` files in a repo. Exposed at `GET /explorer/{repo_id}/keywords`.
- **Surfacing**: `KeywordPalette.vue` loads them via `getProjectKeywords(repoId)`, groups them under `Project: <file>` categories, and lets the user insert them.
- **Signatures**: `useKeywordSignatures.ts` resolves project-keyword signatures with the RF-faithful order *project > libdoc(env) > bootstrap*.

So a `.resource` keyword is already **discoverable, searchable, and insertable**. RES-1 and RES-3 are effectively shipped.

## 2. The gap (the real problem)

When the user inserts a keyword that comes from a **`.resource` file**, RoboScope does **not** add the corresponding `Resource    <path>` import to the file's `*** Settings ***` — the code explicitly opts out (`KeywordPalette.vue:191-194`). Library keywords auto-import their `Library    X`; resource keywords do not.

Result: the inserted keyword **fails at runtime** — `No keyword with name '…' found` — because the resource was never imported. The user has to know to add `Resource    …/foo.resource` by hand. That is exactly Daniel's "make local/repository Resources loadable *and usable*": the loading works, the *usability* (run-without-manual-fixup) does not.

## 3. Users & JTBD

- **Test author** (EDITOR): *"When I drop a keyword from a shared `.resource` file into my test, I want RoboScope to wire up the `Resource` import for me, so the test actually runs without me hand-editing Settings."*

## 4. Goals / Non-goals

**Goals**
- Inserting a project keyword sourced from a `.resource` (or another `.robot`) file auto-adds `Resource    <repo-relative-or-file-relative path>` to the open file's settings, if not already present — mirroring the Library auto-import.
- The path is RF-valid (relative, forward slashes) and de-duplicated.
- Verify a run resolves the import (RES-4) and pin it.

**Non-goals (v1)**
- Import-graph scoping of the palette (showing only keywords reachable from the open file's existing imports) — the current "show all repo keywords" behavior is a convenience, not a bug; out of scope.
- A `*** Variables ***`-from-resource importer — variables aren't the reported pain; defer.
- Resolving keywords across repos / external resource paths.

## 5. Functional requirements

- **FR-1** When a keyword whose source file is a `.resource`/`.robot` (and not the currently-open file) is added from the palette, add `Resource    <path>` to the form's resource imports if absent.
- **FR-2** The path is computed relative to the open file (or repo-root-relative, whichever the existing Resource-import convention uses), normalized to forward slashes; adding the same resource twice is a no-op.
- **FR-3** Adding a keyword from the **same** file, a BuiltIn, or a Library keyword does NOT add a Resource import (no false imports).
- **FR-4** The auto-added import round-trips through the `.robot` text serializer unchanged (RES-4: a run resolves the keyword).

## 6. Stories

- **RES-2** Auto-import `Resource` on keyword insert (the core fix). FE: palette passes the source path; FlowEditor/RobotEditor adds the Resource import.
- **RES-4** Verify + pin execution honors the auto-added import (unit round-trip + real-UI E2E that inserts a resource keyword, saves, and confirms the `Resource` line is present in the saved `.robot`).

## 7. Success metrics

- A test author can insert a `.resource` keyword and the saved `.robot` contains a matching `Resource` import — verified by E2E. No manual Settings edit required.
- Zero false imports for BuiltIn/Library/same-file keywords (unit-pinned).

## 8. Acceptance (epic-level)

1. Inserting a `.resource` keyword adds exactly one correct, de-duplicated `Resource` import; pinned by unit + real-UI E2E.
2. No regression to Library auto-import or to BuiltIn/same-file inserts.
3. i18n unaffected (no new user-facing strings expected; if a toast is added, EN/DE/FR/ES/ZH).

## 9. Handoff

→ **Architecture (Winston)**: where the source path is threaded from `getProjectKeywords` → palette → `add-node` → FlowEditor; how `Resource` imports are represented in `RobotForm`/settings and how `addLibrary` works (to mirror it as `addResource`); path computation + dedupe. Then impl (Amelia) → review → E2E.
