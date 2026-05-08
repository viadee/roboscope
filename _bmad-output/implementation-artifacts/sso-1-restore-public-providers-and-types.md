# Story SSO-1: Restore the public-providers API + the Phase-4 types

Status: done

Epic: SECURITY / REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `sso-1-restore-public-providers-and-types`

## Reported

Once `npm run lint` was repaired in DEVEX-2 and started actually running
`vue-tsc`, it surfaced **24 pre-existing type errors** all rooted in
two missing things:

1. **Missing types in `domain.types.ts`**: `Team`, `TeamCreate`,
   `TeamDetail`, `TeamUpdate`, `TeamMemberDetail`, `GroupMapping`,
   `GroupMappingCreate`, `SsoProviderPublic`. Imported by
   `teams.api.ts`, `teams.store.ts`, `TeamListView.vue`,
   `TeamDetailView.vue`, `GroupMappingRow.vue`, `sso.store.ts` —
   never declared.

2. **Missing API function `listPublicSsoProviders`** in
   `idpProviders.api.ts`. Imported and *called* by `sso.store.ts:23`,
   but the function was never defined.

The second one is a **real production bug**:

```ts
async function loadProviders(): Promise<void> {
    try {
      providers.value = await listPublicSsoProviders()  // ← TypeError
    } catch (err) {
      providers.value = []
      console.warn('[sso.store] listPublicSsoProviders failed, falling back to local login only', err)
    } …
}
```

`listPublicSsoProviders` is `undefined` at runtime → calling it throws
`TypeError: listPublicSsoProviders is not a function` → caught by the
try/catch → console.warn fires → **the SSO provider list silently
falls back to "local login only" mode for every visitor**.

The login form has been hiding configured SSO providers from users
for as long as this code shipped. The unit tests didn't catch it
because they mock `listPublicSsoProviders` via `vi.fn()`.

## Fix

### 1. Define the missing types

Added to `src/types/domain.types.ts`, mirroring
`backend/src/teams/schemas.py` and the `SsoProviderPublic` shape from
`backend/src/auth/schemas.py`:

- `Team`, `TeamCreate`, `TeamUpdate`, `TeamDetail` (extends Team
  with `members`)
- `TeamMemberDetail`
- `GroupMapping`, `GroupMappingCreate`
- `SsoProviderPublic`

### 2. Add the API function

```ts
export async function listPublicSsoProviders(): Promise<SsoProviderPublic[]> {
  const response = await apiClient.get<SsoProviderPublic[]>('/auth/sso/providers')
  return response.data
}
```

Maps to the existing backend `GET /auth/sso/providers` endpoint at
`backend/src/auth/sso_router.py:103`.

## Verification

- `npx vue-tsc --noEmit` — was 24 errors, now 0.
- `npm run lint` — clean exit (validating DEVEX-2's fix at the
  same time).
- `npx vitest run` — 360/360 still green.
- `npx vite build` — clean.

## Out of scope

- **Adding a vitest test that exercises the real
  `listPublicSsoProviders`** (not the mocked version). The current
  `sso.store.spec.ts` mocks it; without the mock the test would have
  caught the missing function. Adding such a test is a follow-up
  hardening story.
- **Auditing other "imported but never defined" patterns**. The TS
  errors caught these specifically; future regressions would
  surface immediately now that `npm run lint` actually runs.
