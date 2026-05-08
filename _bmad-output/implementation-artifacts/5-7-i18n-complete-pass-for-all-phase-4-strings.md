# Story 5-7: i18n-complete pass for all Phase-4 strings

Status: done (shipped inline with Phase 4 Epic 2)

## Story

As a Tech Writer,
I want all Phase-4 user-facing strings reviewed and present in EN/DE/FR/ES at end of Sprint 2,
so that Sprint 3 does not introduce late translation regressions.

## Acceptance Criteria

1. Every user-facing string in Phase 4 views/components has a corresponding key in all four locale files (`frontend/src/i18n/locales/{en,de,fr,es}.ts`).
2. vue-i18n v10 reserved characters (`@ | { }`) are escaped in string values so the production build (`npm run build`) does not throw SyntaxError.
3. Frontend test suite (`make test-frontend`) is green including the locale-pinned assertions on `TeamListView`, `GroupMappingRow`, `SsoErrorView` (DE) and `DryRunPanel`, `IdpProviderEditView`, `TeamDetailView` (EN).
4. No Phase 4 view renders a literal key fallback (`teams.list.title`, `auth.ssoError.heading`, etc.) at runtime.

## Implementation

Shipped in commit `c8c171b` (Phase 4 Epic 2+3). Approximately 115 keys added to each of the four locale files:

- `auth.ssoError.*` — 14 keys (heading, tryAgain, contactAdmin, 10 failure-code messages, generic fallback).
- `idpProviders.staleCacheBadge`, `idpProviders.neverCached`, and the remaining `idpProviders.edit.*` fields, buttons, tooltips, toasts, errors and handoff block (~40 keys).
- `teams.list.*` + `teams.detail.*` including tabs, members, mappings (with `editRoleAriaLabel`), repos note (~40 keys).
- `dryRunPanel.*` — title, rerunNeeded, elapsed, a11y started/finished, status including `warning` and `default`, 3 check labels.

Test-pinned strings locked at the EN and DE ends:
- DE: `"Teams"`, `"Neues Team"`, `"Mitglieder"`, `"Speichern"`, `"Abbrechen"`, `"Anmeldung nicht möglich"`, `"Erneut versuchen"`.
- EN: `"No teams yet"`, `"New Team"`, `"Import from IdP groups"`, `"Edit role viewer for group engineering"`, `"Dry-Run Report"`, `"re-run required"`, `"Running"/"Passed"/"Failed"/"Stale"/"Not run"`, `"Dry-run started"`, `"valid user ID"`, `"already mapped"`, `"New Identity Provider"`, `"Edit Identity Provider"`, plus SSO failure-code substrings.

## Verification

- Vitest: 191/191 pass (17 files), including the six locale-assertion specs (`TeamListView`, `TeamDetailView`, `GroupMappingRow`, `SsoErrorView`, `DryRunPanel`, `IdpProviderEditView`).
- Production build: `npm run build` passes the esbuild + i18n SyntaxError guard (reserved `@ | { }` escaped where needed, e.g. `admin{'@'}roboscope.local`).

## Notes

- The pass was executed by a single delegated subagent that scanned all six views + their test expectations, then wrote the missing keys into all four locale files in one atomic pass. This kept the four locales in lock-step and avoided the partial-translation drift that would have made Sprint 3 painful.
- Typing tightness (TS2305 etc.) in `stores/teams.store.ts` / `api/teams.api.ts` surfaced during the build but is pre-existing, unrelated to locale data, and tracked separately.
- Remaining backend error-code strings (e.g. `"Repository not found"`) are intentionally not translated — they travel through error responses that the frontend maps to localized keys.
