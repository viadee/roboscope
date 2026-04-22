# Story 2.4: Deep-link preservation through SSO redirect

Status: done

Epic: 2 — SSO User Access
Story Key: `2-4-deep-link-preservation-through-sso-redirect`

## Story

As a User with a bookmarked RoboScope URL,
I want to be returned to the exact bookmarked URL after SSO login,
so that my session expiry never loses my navigation context.

## Context

- Backend-side `return_to` origin validation shipped in Story 1.10
  (`backend/src/auth/return_to.py`). External-domain URLs are rejected
  with HTTP 400 `return_to.invalid`.
- Backend-side `return_to` persistence in `OidcLoginAttempt` shipped in
  Story 2.1; forwarded from the callback in Story 2.2.
- SSO button in `LoginView.vue` forwards `return_to` (Story 2.3, AC5).
- **Gap**: the Vue-Router navigation guard at
  `frontend/src/router/index.ts:122-124` still writes the legacy
  `redirect` query key (pre-Phase-4 convention). Similarly,
  `LoginView.handleLogin` reads `route.query.redirect` only. As a
  result, a user visiting `/reports/42` while unauthenticated is sent
  to `/login?redirect=/reports/42`, which the SSO button path
  tolerates (AC5 fall-through), but the **local-password-login
  branch** of that page pushes back to `route.query.redirect`, not
  `return_to`. The plumbing is inconsistent and the spec-compliant
  query key never reaches the backend from the guard.

## Acceptance Criteria

1. **AC1 — Router guard emits `return_to` (not legacy `redirect`).**
   When `to.meta.requiresAuth && !auth.isAuthenticated`, the guard
   redirects to `/login` with query `{ return_to: to.fullPath }`.
   Verified by a unit test on the router that mounts the auth store
   in an unauthenticated state and asserts the resolved `Location`.

2. **AC2 — Session-invalidation redirect preserves current path.**
   When `auth.fetchCurrentUser()` fails mid-navigation (token stale),
   the guard redirects to `/login?return_to=<to.fullPath>` instead of
   a bare `/login`. Verified by a unit test that mocks
   `fetchCurrentUser` to reject and asserts the guard's final
   destination includes the encoded `return_to` query.

3. **AC3 — Local-password login reads `return_to` with legacy
   fall-through.** `LoginView.handleLogin` uses
   `route.query.return_to ?? route.query.redirect ?? '/dashboard'`
   as the post-login navigation target. **Legacy key is read-only**
   — no code path writes `redirect` any more. Verified by 2 unit
   tests: one with `?return_to=/reports/42`, one with legacy
   `?redirect=/dashboard`.

4. **AC4 — `return_to` is never forwarded to an external origin.**
   The router guard only ever sets `return_to = to.fullPath`, which
   `vue-router` guarantees to be an app-relative path
   (`/foo?bar=baz#frag`). No change needed beyond the guarantee —
   AC4 is covered by type contract. Verified in the story via a
   unit test that attempts to craft a malicious pre-populated
   location and confirms the guard does **not** echo an absolute URL
   into `return_to`.

5. **AC5 — `/login?return_to=/login` loop-guard.** If the current
   path is `/login` itself (e.g., an explicit visit to the login
   page), the guard MUST NOT add a self-referential `return_to`.
   The existing `to.path === from.path` early-return line 120
   already partially covers this; AC5 additionally asserts that
   a first-time visit to `/login` (from `from.path = '/'`) does
   NOT carry `return_to=/login`.

6. **AC6 — No regression of existing tests.** All existing
   `frontend/src/tests/` tests continue to pass, including the
   LoginView tests from Story 2-3 (which already assert
   `return_to` forwarding via the SSO button path).

## Tasks / Subtasks

### Task 1: Router guard uses `return_to` (AC1, AC2, AC5)

- [x] MOD `frontend/src/router/index.ts`:
  - Line ~123: `return { path: '/login', query: { redirect: to.fullPath } }`
    → `return { path: '/login', query: { return_to: to.fullPath } }`.
  - Line ~133: `return { path: '/login' }` when navigating from a
    non-`/login` path → `return { path: '/login', query: { return_to: from.fullPath || to.fullPath } }`.
    Do **not** add `return_to` when the current `to.path` is already
    `/login` (loop guard).
  - Keep the `to.path === from.path` early-return line 120 unchanged.

### Task 2: LoginView reads new key with legacy fall-through (AC3)

- [x] MOD `frontend/src/views/LoginView.vue` — inside `handleLogin`:
  - Replace `const redirect = (route.query.redirect as string) || '/dashboard'`
    with
    `const target = (route.query.return_to as string) ?? (route.query.redirect as string) ?? '/dashboard'`
    and push `target`.
  - Keep the SSO-button path (`ssoInitUrl()`) unchanged — it already
    prefers `return_to` over `redirect` (Story 2-3 AC5).

### Task 3: Tests (AC1, AC2, AC3, AC5, AC6)

- [x] NEW `frontend/src/tests/router/guards.spec.ts` — Vitest specs
  for the router guard:
  - `test_unauthenticated_redirects_to_login_with_return_to`
  - `test_session_invalidation_preserves_from_path`
  - `test_login_path_visit_does_not_add_return_to`
  - `test_login_loopguard_when_to_equals_from`
  - Mount `createRouter()` with `createMemoryHistory()` and a tiny
    fake auth store; assert the resolved `Location` emitted by the
    guard.

- [x] MOD `frontend/src/tests/components/LoginView.spec.ts` — add to
  the existing `local-login regression (AC8)` block:
  - `test_local_login_success_navigates_to_return_to_when_present`
    — sets `_routeQuery = { return_to: '/reports/42' }`, submits the
    form, asserts `router.push` called with `/reports/42`.
  - `test_local_login_success_falls_through_to_legacy_redirect`
    — sets `_routeQuery = { redirect: '/stats' }`, asserts
    `router.push('/stats')`.
  - `test_local_login_defaults_to_dashboard_when_no_query`
    — asserts `router.push('/dashboard')`.

### Task 4: Regression (AC6)

- [x] Run `npx vitest run src/tests/` — all tests green.

## Non-goals

- Changing the backend contract — `return_to` origin validation is
  already shipped (Story 1.10).
- Deep-linking for Chrome-extension deep-link flows (the extension
  does its own navigation; it is not affected by this story).
- External-origin URL support — forbidden by NFR7.

## Dev Notes

- The `redirect` query key stays **readable** for 2 reasons:
  1. Existing bookmarks/links in user workflows that still carry
     `?redirect=...` must keep working.
  2. The type contract for `to.fullPath` in vue-router 4 is
     always app-relative, so a forced migration is not urgent.
- The loop-guard (`/login → /login`) is already covered by the
  `to.path === from.path` check — AC5 only codifies that a
  first-time visit to `/login` from `/` does not emit
  `return_to=/login`.
