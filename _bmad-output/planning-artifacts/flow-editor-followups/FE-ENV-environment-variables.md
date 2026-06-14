# Story FE-ENV: %{ENV} environment-variable awareness

- **Status:** Planned
- **Priority:** P2
- **Parent:** Flow Editor — Verification & Hardening (deferred item N4)

## Context
Robot Framework environment variables `%{NAME}` (and `%{NAME=default}`) are read
from the OS environment, distinct from suite `${}` variables. They round-trip
safely today (pinned in AC-C5) but get no special recognition: the user can't
tell at a glance which args read from the environment, and the Variables panel
only covers `${}`/`@{}`/`&{}` suite variables.

NOT in scope: writing OS env vars, or a `%{}` editor that persists values
(those live in the Environment's variables, managed elsewhere). This is
read-only **awareness**.

## Acceptance Criteria
- **AC1:** Pure helper `extractEnvVarRefs(text)` returns the `%{NAME}` /
  `%{NAME=default}` references in a string (name + optional default).
- **AC2:** A step whose args reference `%{...}` carries an `envRefs` flag in node
  data; the node shows a small `%{}` indicator with a tooltip listing the names
  (and defaults).
- **AC3:** The Variables panel gains a read-only "Environment variables used"
  section listing distinct `%{}` refs across the active item, each annotated
  with its default (or "no default") — purely informational.
- **AC4:** Round-trip unchanged; `%{X}` / `%{X=y}` survive verbatim.

## Tasks
- `robotTextIO.ts` or `envVars.ts`: `extractEnvVarRefs()`.
- `flowConverter.ts`: `envRefs` on node data.
- `FlowEditor.vue`: read-only env-vars section in the Variables panel.
- i18n keys EN/DE/FR/ES.

## Tests
- Unit `FlowEditorEnvVars.spec.ts`: extractEnvVarRefs matrix (none, single,
  with default, multiple, mixed with `${}`); round-trip preserves `%{}`.
- e2e `flow-editor-env-vars.spec.ts`: suite using `%{HOME=/tmp}` → Variables
  panel lists it with its default.
