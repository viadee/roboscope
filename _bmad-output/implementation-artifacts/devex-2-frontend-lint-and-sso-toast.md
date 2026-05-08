# Story DEVEX-2: Repair frontend `npm run lint` + fix silent SSO-toast bug

Status: done

Epic: SECURITY / REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `devex-2-frontend-lint-and-sso-toast`

## Reported

Continuing the close-look pass after DEVEX-1 (backend ruff config).
Two related findings on the frontend side:

### B1 — `npm run lint` is silently broken

`frontend/package.json` had:

```json
"lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx --fix"
```

Three problems:
1. `eslint` isn't a dependency — `grep eslint package.json` returns
   only the script line itself.
2. There's no `eslint.config.js` (ESLint v9+ requires the new flat
   format; the old `.eslintrc.*` is gone if it ever existed).
3. The `--ext` flag was removed in ESLint v9.

`npx eslint` therefore fails with `couldn't find an
eslint.config.(js|mjs|cjs) file`. Same shape as the backend ruff
bug DEVEX-1 fixed: a lint script in `package.json` is a
documentation lie.

### B2 — `SsoLinkConsentView` swallows error/cancel toasts

While running the (now-working) lint, vue-tsc surfaced this:

```
Property 'toast' does not exist on type 'Store<"ui", …>'.
Did you mean 'toasts'?
```

The view does:

```ts
ui.toast?.(t('welcome.toast.signInCancelled'))    // line 62
ui.toast?.(msg)                                    // line 70
```

The UI store exposes `success / error / info / warning / addToast`
— but **not** `toast`. The `?.` optional-chain hides the error at
runtime: the call evaluates to `undefined`, the toast never shows.

Real user-facing bug: when SSO sign-in is cancelled or errors out,
the user sees no feedback — they just get redirected to /login
and wonder what happened.

## Fix

### B1 fix

Replace the broken lint script with the existing working
`vue-tsc --noEmit`:

```diff
- "lint": "eslint . --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx --fix",
+ "lint": "vue-tsc --noEmit",
  "type-check": "vue-tsc --noEmit"
```

Two scripts now alias to the same command. A future story can add
proper ESLint v9 (eslint.config.js + plugin choices + dep installs)
under the `lint` slot without disturbing `type-check` callers.

### B2 fix

`SsoLinkConsentView.vue:62` and `:70` switched to the proper
typed API:

```ts
// cancelled path → informational
ui.info(t('welcome.toast.signInCancelled'), '')
// catch path → error toast with title + detail
ui.error(t('common.error'), msg)
```

## Verification

- `npm run lint` — runs (and exits non-zero with the pre-existing
  teams/sso TS errors that were always there but invisible
  through the broken eslint script).
- `vue-tsc --noEmit` — `SsoLinkConsentView` errors gone.
- `npm run test:unit` — 360/360 still green.
- `npm run build` — clean.

## Out of scope

- **Adding a real ESLint v9 config** — needs deciding on rules
  (eslint-plugin-vue, @typescript-eslint, formatting via prettier,
  etc.). Separate story.
- **Fixing the remaining pre-existing TS errors** in
  `teams.store.ts`, `TeamListView.vue`, `IdpProviderListView.vue`
  — they're mostly missing `Team` / `GroupMapping` / `SsoProviderPublic`
  exports from `@/types/domain.types`. Pre-existing for the entire
  loop session; the modules aren't in the critical path of any
  feature I shipped. Defer.
