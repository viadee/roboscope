# Epic EXEC — RF Execution Configuration — PRD + scope

**Status**: EXEC-1/EXEC-3 shipped; EXEC-2/4/5/6/7 deferred (backlog)
**Date**: 2026-06-18
**PM/Architect**: John / Winston
**Parent**: [presentation-feedback-epics.md](./presentation-feedback-epics.md)

## What already existed (discovery)

The execution pipeline already modeled and applied tags + variables:
`RunCreate`/`ExecutionRun` carry `tags_include`, `tags_exclude`, `variables`, and
`subprocess_runner.py` (and the Docker runner) already build
`robot --include/--exclude/--variable` from them. **But the run dialog never
exposed them** — so users couldn't actually use the capability. That was the gap.

## Shipped this iteration

- **EXEC-1 / EXEC-3 — tag selection in the run dialog**: the New Run dialog now has **Include tags** and **Exclude tags** inputs (comma-separated), threaded through `runForm` → `RunCreateRequest` (already typed) → the existing backend that converts them to `robot --include/--exclude`. i18n in EN/DE/FR/ES/ZH. Real-UI E2E (`e2e/tests/run-tags.spec.ts`) asserts the create-run request carries `tags_include`; the runner application is covered by existing backend tests.

This is the migration-free, backend-ready slice that delivers the most-requested
"manage what robot runs" capability (tag-based selection) end to end.

## Deferred to backlog (each its own future cycle)

These are larger initiatives, intentionally not built in this iteration:

- **EXEC-1b — free-form `robot` args + `--variable` UI**: a guarded "advanced args" field (and a variables key/value editor) needs a new `ExecutionRun` column + Alembic migration + runner arg-merge + injection-safe parsing. (Variables are already modeled/applied; only the UI is missing.)
- **EXEC-2 — PreRunModifiers** (`--prerunmodifier`): config + project-provided module resolution; security note (arbitrary code in the env).
- **EXEC-4 — Long Name / unique ID surfacing → Jira association** (feeds the Phase-6 Jira plugin).
- **EXEC-5 — `__init__.robot`** suite-init editing in Explorer/Flow.
- **EXEC-6 — DataDriver / dynamic test generation** (spike-first).
- **EXEC-7 — RF best-practices research spike** → UI-surfacing backlog (RF Certified Professional rubric).

## Acceptance (shipped scope)

1. The run dialog exposes Include/Exclude tags; submitting a run sends `tags_include`/`tags_exclude` — pinned by real-UI E2E.
2. No regression to the existing runner tag/variable handling (existing backend tests green).
3. i18n complete in all 5 locales (Gate 8 green).
