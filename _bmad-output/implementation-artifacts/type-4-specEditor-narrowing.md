# Story TYPE-4: SpecEditor narrowing — last 2 real `as any` casts

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `type-4-spec-editor-narrowing`

## Reported

Final pass on the `as any` cleanup arc:
- TYPE-1: 25 → 13
- TYPE-2: 13 → 9 (KeywordPalette discriminated union)
- TYPE-3: 9 → 3 (mechanical leftovers)

This pass closes the last two real casts in `SpecEditor.vue`.

## What was done

**Cast 1 — `(step as any)[field] = value`** (line 778 in
`updateStructuredStep`).

`isStructuredStep` is already a proper TS type predicate
(`step is StructuredStep`). After the predicate `step` is narrowed
to `StructuredStep` and `field` is the union
`'action' | 'data' | 'expected_result'` — all fields of type
`string`. The assignment is statically checkable. The cast was
just leftover. Dropped.

**Cast 2 — `yaml.load(yamlContent) as any`** (line 410 in
`parseYamlToForm`).

`yaml.load` returns `unknown` by design (the YAML can contain
anything). The downstream code does field-level defensive reads
(`m.title || ''`, `m.libraries || []`, …) so an `unknown` annotation
would force a cascade of nested casts at every read site.

Switched to `Record<string, any> | null | undefined`. This:
- documents intent (we *know* it's a parsed object, not "anything
  goes"),
- keeps the nested field access compiling without per-line casts,
- doesn't lose static checking elsewhere — every parsed value is
  still defensively coerced before reaching `form.*`.

A proper Zod schema is the next-step refactor (TYPE-5 candidate);
deferred because it adds a new dep and the current defensive reads
already cover the parse-failure modes.

## Verification

```
$ grep -rn "as any" frontend/src/ --include="*.ts" --include="*.vue"
src/tests/stores/ui.store.spec.ts:62:      ;(store as any).windowWidth = 500
src/components/report/ReportXmlView.vue:100:// Check if a suite has any matching tests (recursively)
src/components/editor/flow/KeywordPalette.vue:15:// `as any`.
```

Three hits remain, **none are real source-code casts**:
- the test file's idiomatic private-state assertion,
- a code comment containing "any matching tests" (false-positive),
- the type-block doc comment introduced by TYPE-2.

Cumulative across TYPE-1..TYPE-4: **25 → 0** real casts.

`npx vue-tsc --noEmit` produces zero new errors on touched files.
`npx vitest run` 358/358 still green. `npx vite build` clean.

## Out of scope

- **Zod schema for the .roboscope spec** (TYPE-5): would replace
  the `Record<string, any>` annotation with a parsed, validated
  schema. Adds `~6 KB gzipped` `zod` dep; defer until a use-case
  beyond editor-internal parsing emerges (e.g. server-side
  validation or AI-tool guardrails).
