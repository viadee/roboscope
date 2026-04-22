# Story 2.7: Frontend SsoErrorView with localized outage copy

Status: done

Epic: 2 — SSO User Access
Story Key: `2-7-frontend-ssoerrorview-with-localized-outage-copy`

## Story

As a User,
I want to see a non-technical, actionable error message when SSO login fails,
so that I know whether to retry, contact someone, or try something else.

## Context

- Backend SSO callback (Story 2-2) redirects failed attempts to
  `/sso-error?code=<reason>` (`backend/src/auth/sso_router.py:127`).
- Known failure codes (from `SsoCallbackError.code` in
  `oidc_callback_service.py`): `state.expired`,
  `state.not_found`, `return_to.invalid`, `token_exchange.failed`,
  `claims.email_unverified`, `claims.azp_missing`, `user.disabled`,
  `idp.not_found`, `sync.failed`, and generic `idp.unreachable`.
- Backend public-settings endpoint (Story 2-5) exposes
  `admin_contact_email` for the error-page admin-contact line.
- No `SsoErrorView` component exists yet; no `/sso-error` route.

## Acceptance Criteria

1. **AC1 — Route + view.** `GET /sso-error` (public, no auth)
   renders `SsoErrorView.vue`. The route reads `code` from query;
   if absent, treat as generic `idp.unreachable`.

2. **AC2 — Code-specific localized copy.** Each known error code
   maps to a **specific** i18n key under `auth.ssoError.<code>`.
   The catch-all for unknown codes is `auth.ssoError.generic`.
   No OAuth codes are ever rendered to the end user.

3. **AC3 — Admin contact dynamically populated.** The
   `admin_contact_email` from `/auth/sso/public-settings` is shown
   inline in the message body (fallback: hide the line gracefully
   if the settings endpoint errors). Populated via the SSO store
   `loadSettings()` on mount.

4. **AC4 — `[Try again]` button re-initiates the SSO flow.**
   Clicking the button navigates to `/login` (full router push;
   the user picks their IdP again). If `return_to` was in the
   URL of the failure redirect, forward it to `/login?return_to=…`.

5. **AC5 — Accessibility (NFR23, NFR24).**
   - `role="alert"` + `aria-live="assertive"` on the error
     container so screen readers announce immediately.
   - Keyboard: `Tab` to the `[Try again]` button → `Enter`
     activates.
   - Full-page keyboard navigation with no traps; no mouse-only
     hit-targets.
   - All copy available in EN/DE/FR/ES — vue-i18n prod-build
     test passes (escape `@`, `|`, `{`, `}` where needed).

6. **AC6 — No regression.** All existing frontend tests still
   pass. New Vitest tests cover: rendering for each known code,
   fallback to generic, `Try again` navigation, `return_to`
   forwarding, admin-contact fallback.

## Tasks / Subtasks

### Task 1: Route + view (AC1, AC3, AC4)

- [x] NEW `frontend/src/views/SsoErrorView.vue`:
  - Reads `route.query.code` (default `'idp.unreachable'`) and
    `route.query.return_to`.
  - On mount, calls `sso.loadSettings()` (idempotent — already
    wired in Story 2-5) so `sso.adminContactEmail` is available.
  - Renders a `role="alert"` `aria-live="assertive"` container
    with: heading, localized message, admin-contact line (only
    if `adminContactEmail` non-empty), and a `[Try again]`
    `BaseButton` that navigates to `/login?return_to=<fwd>` if
    present else `/login`.
  - Uses existing styling tokens (CSS vars) — no inline hex.

- [x] MOD `frontend/src/stores/sso.store.ts` — extend the store
  to also expose `adminContactEmail` (already set in the public
  settings endpoint but not stored today):
  ```ts
  const adminContactEmail = ref('')
  // in loadSettings() try-branch:
  adminContactEmail.value = data.admin_contact_email ?? ''
  // in the catch branch:
  adminContactEmail.value = ''
  ```

- [x] MOD `frontend/src/router/index.ts` — new route:
  ```ts
  {
    path: '/sso-error',
    name: 'sso-error',
    component: () => import('@/views/SsoErrorView.vue'),
    meta: { layout: 'auth', requiresAuth: false },
  },
  ```

### Task 2: i18n copy (AC2)

- [x] MOD `frontend/src/i18n/locales/{en,de,fr,es}.ts` — add
  `auth.ssoError` namespace with the following keys. Copy style:
  user-facing, actionable, no OAuth jargon.
  - `heading` — "We couldn't sign you in" / "Anmeldung nicht möglich" /
    "Connexion impossible" / "No pudimos iniciarte sesión"
  - `tryAgain` — "Try again" / "Erneut versuchen" / "Réessayer" / "Reintentar"
  - `contactAdmin` — "If this keeps happening, contact your admin: {email}"
    (+ DE/FR/ES) — escape `{` and `}` so the i18n prod build doesn't
    break; the `{email}` placeholder is the substitution target.
  - `generic` — "Something went wrong during sign-in. Please try again."
  - `idp.unreachable` — "We couldn't reach your identity provider.
    Try again in a few minutes."
  - `state.expired` — "Your sign-in session timed out. Please try again."
  - `state.not_found` — same copy as `state.expired` (user-facing
    equivalence — both mean "start over").
  - `return_to.invalid` — "The link you used is no longer valid.
    Please start over from the login page."
  - `token_exchange.failed` — "The identity provider rejected the
    sign-in. Please try again or contact your admin."
  - `claims.email_unverified` — "Please verify your email with your
    identity provider before signing in."
  - `claims.azp_missing` — "The identity provider returned an
    unexpected response. Please try again or contact your admin."
  - `user.disabled` — "Your account is disabled. Contact your admin
    to regain access."
  - `idp.not_found` — "The configured identity provider is no longer
    available. Contact your admin."
  - `sync.failed` — "We signed you in but couldn't load your teams.
    Please try again in a minute."

### Task 3: Tests (AC1–AC6)

- [x] NEW `frontend/src/tests/components/SsoErrorView.spec.ts`:
  - `renders with role=alert + aria-live=assertive`
  - `renders code-specific copy for idp.unreachable`
  - `renders code-specific copy for state.expired`
  - `renders code-specific copy for user.disabled`
  - `falls back to generic for unknown code`
  - `reads code=idp.unreachable when query is missing`
  - `renders admin-contact line when adminContactEmail is set`
  - `hides admin-contact line when adminContactEmail is empty`
  - `Try again button navigates to /login without return_to`
  - `Try again forwards return_to when present in failure URL`

### Task 4: Regression (AC6)

- [x] Run `npx vitest run` — all green.

## Non-goals

- A detailed per-error contact form. Admin contact is a mailto-
  style line only.
- Retrying with the SAME IdP automatically — the `[Try again]`
  button navigates back to `/login` so the user consciously
  re-chooses. This simpler UX avoids bouncing the user
  immediately back into a broken flow.
- Any change to the backend error-code vocabulary. The frontend
  maps codes into user copy; backend codes remain
  programmer-facing.

## Dev Notes

- vue-i18n prod-build **will fail silently** if `{email}` is not
  correctly placed — use the `.raw` interpolation approach:
  `{{ t('auth.ssoError.contactAdmin', { email: adminContactEmail }) }}`.
- `role="alert"` applied to a static DOM node announces only when
  the element is inserted. Our SPA route-change inserts the new
  view, so screen readers will announce on navigation.
- `@axe-core/playwright` CI wiring is Story 4-8; for this story
  the assertion is that the DOM is axe-clean by construction.
