# Story TYPE-1: First-pass `as any` cleanup

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `type-1-as-any-cleanup-pass-1`

## Reported

CLAUDE.md "Known open issues":

> ~55 `as any` casts

The actual count today (after prior incremental cleanups) was 25. This
pass removes 12 of them — the mechanical wins where the cast was
either:
- a leftover from before a real type existed, or
- papering over a missing exported union type that's easy to add.

## What was done

| Cast | File | Fix |
|---|---|---|
| `{ auto_sync: enabled } as any` | views/ReposView.vue:159 | Drop the cast — `Partial<Repository>` already permits this since REPO-3 |
| `{ pre_run_sync: enabled } as any` | views/ReposView.vue:168 | Drop |
| `{ environment_id: envId } as any` | views/ReposView.vue:386 | Drop |
| `{ environment_id: env.id } as any` | views/ExplorerView.vue:194 | Drop |
| `(env as any).python_version_warning` | views/EnvironmentsView.vue:76,77 | Field already on `Environment` — drop the cast |
| `(envs.environments[idx] as any)[field]` | views/EnvironmentsView.vue:287 | Replace with `Object.assign(env, { [field]: value })` |
| `status: status as any` | stores/execution.store.ts:79 | Type the param as `RunStatus` (already exported) |
| `status: status as any` | stores/recorder.store.ts:127 | Type the param as `RecordingStatus` (already exported) |
| `status: status as any` (×2) | stores/stats.store.ts:128,131 | Add `AnalysisStatus` union, type the param |
| `install_status: status as any` | stores/environments.store.ts:84 | Add `PackageInstallStatus` union, type the param |

Two new exported unions in `types/domain.types.ts`:
- `AnalysisStatus = 'pending' | 'running' | 'completed' | 'error'`
  (extracted from inline `AnalysisReport.status`)
- `PackageInstallStatus = 'pending' | 'installing' | 'initializing' | 'installed' | 'failed'`
  (extracted from inline `EnvironmentPackage.install_status`)

## Verification

- `grep -rn "as any" src/` — went from **25 → 13** (12 removed).
- `npx vue-tsc --noEmit` — touched files produce zero new errors;
  pre-existing teams/sso errors are unchanged.
- `npx vitest run` — 358/358 still green.
- `npx vite build` — clean prod build.

## Out of scope (future passes)

The 13 remaining are higher-leverage refactors, not mechanical:

- **`SpecEditor.vue`** uses `yaml.load(...) as any` — yaml IS untyped
  by design; needs a Zod or io-ts schema to narrow.
- **`KeywordPalette.vue`** has 5 casts driving a heterogeneous
  category list — needs a discriminated-union refactor.
- **`SettingsView.vue:469`** passes `password` to `updateUser`
  which doesn't include it in `Partial<User>` — needs a separate
  `ChangeUserPasswordRequest` type.
- **`FlowEditor.vue:649`** — control-type narrowing.
- **`ProviderConfig.vue:98`** — provider_type union narrowing.
- **A handful of one-offs** in tests / dynamic dispatch sites.

## Risk notes

- The dropped repository-update casts were redundant *because*
  REPO-3 had already added every field they were trying to bypass.
  Anyone who reverts REPO-3 (which would also delete the
  `pre_run_sync` field) would break this commit too — defensible:
  the cleanup follows the schema.
- The new union exports widen `domain.types.ts`'s public surface —
  callers can now narrow using these unions directly. Backwards-
  compatible: the existing inline literals on the interfaces still
  resolve identically.
