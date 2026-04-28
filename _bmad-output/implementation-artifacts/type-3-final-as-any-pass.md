# Story TYPE-3: Final mechanical `as any` pass

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `type-3-final-as-any-pass`

## Reported

Wraps up the multi-pass `as any` cleanup started in TYPE-1 (25 → 13)
and continued in TYPE-2 (13 → 9 in KeywordPalette). This pass
removes the four mechanical leftovers:

1. **`SettingsView.vue:469`** — `updateUser(id, { password: …​ } as any)`.
   `Partial<User>` doesn't include the optional `password` field the
   admin password-reset endpoint accepts. Fix: introduce
   `UserUpdatePayload = Partial<User> & { password?: string }` in
   `api/auth.api.ts` and update `updateUser`'s signature. The
   call site drops the cast.

2. **`ProviderConfig.vue:98`** — `provider_type: provider.provider_type as any`.
   Both `AiProvider.provider_type` and the form's
   `AiProviderCreateRequest.provider_type` are the same union
   (`'openai' | 'anthropic' | 'openrouter' | 'ollama'`), just spelled
   differently. TS structural typing accepts the assignment without
   the cast.

3. **`FlowEditor.vue:649`** — `type: control as any` where `control`
   came from `event.dataTransfer.getData('application/rf-control')`
   (always `string`). Real fix: a runtime type guard
   `isStepType(s: string): s is StepType` exported from
   `flowConverter.ts`. The guard backs `STEP_TYPE_VALUES` (a
   ReadonlySet of every literal in `StepType`). The drag handler
   now narrows: `if (control && isStepType(control)) { return { type: control, … } }`.

4. **`ExplorerView.vue:707`** — `createRun(runPayload as any)` where
   the payload was typed `Record<string, any>`. Fix: type
   `runPayload: RunCreateRequest` directly, drop the cast.

## Verification

```
$ grep -rn "as any" frontend/src/ --include="*.ts" --include="*.vue"
src/components/ai/SpecEditor.vue:410:    const parsed = yaml.load(yamlContent) as any
src/components/ai/SpecEditor.vue:778:    (step as any)[field] = value
src/tests/stores/ui.store.spec.ts:62:      ;(store as any).windowWidth = 500
```

3 remaining, all defensible:
- 2× `SpecEditor.vue` — yaml.load returns `unknown` by design;
  proper fix is a Zod / io-ts schema, scoped as TYPE-4.
- 1× `ui.store.spec.ts` — test asserting via private state, idiomatic.

Cumulative across the three TYPE-* passes: **25 → 3** real casts
(–88%). Type-checker (`vue-tsc --noEmit`) clean on every touched
file. 358/358 vitest still green. Production build clean.

## Out of scope

- **TYPE-4**: yaml.load schema validation in SpecEditor. Needs a
  Zod schema modelling the BMAD spec format. Modest size; pull in
  `zod` if not already a dep.
- **The acceptable test cast** stays.
