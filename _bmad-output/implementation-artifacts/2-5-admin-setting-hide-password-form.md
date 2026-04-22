# Story 2.5: Admin setting — hide password form (SSO-only enforcement)

Status: done

Epic: 2 — SSO User Access
Story Key: `2-5-admin-setting-hide-password-form`

## Story

As a Security admin,
I want to configure the installation so that only SSO login is visible to end-users,
so that password-based access is restricted for compliance reasons while
bootstrap admin access is preserved.

## Context

- Story 2-3 scaffolded `sso.store.hideLocalLoginForm` and the `LoginView`
  conditional that hides the `[Sign in with password]` toggle when the
  flag is true. The store's `loadSettings()` is a placeholder that
  always returns `false` (see `frontend/src/stores/sso.store.ts:33-37`).
- Backend `AppSetting` model is a generic key/value store. Admin
  PATCH `/api/v1/settings` already auto-audits via the middleware.
  There is **no public settings endpoint** yet — the existing admin
  endpoint is auth-gated.
- This story closes the loop: persist the flag, expose the subset
  the login page needs via a new PUBLIC endpoint, and add the
  `?bootstrap=1` query-param bypass.

## Acceptance Criteria

1. **AC1 — Setting persistence.** A new `AppSetting` row with
   `key="hide_local_login_form"`, `value_type="bool"`,
   `category="auth"` is seeded on first boot via
   `seed_default_settings()` with default value `"false"`. An admin
   PATCH to `/api/v1/settings` with this key updates the value, and
   the existing audit middleware writes an `AuditLog` row. Verified
   by pytest: seed idempotency + PATCH round-trip.

2. **AC2 — Public endpoint exposes the flag.** A new endpoint
   `GET /api/v1/auth/sso/public-settings` (no auth required) returns
   `{ "hide_local_login_form": bool, "admin_contact_email": str }`.
   The payload is intentionally minimal — only the keys the
   unauthenticated login page needs. Verified by pytest: response
   shape + unauthenticated access allowed.

3. **AC3 — Frontend honors the flag.** `sso.store.loadSettings()`
   fetches from `/auth/sso/public-settings` and populates
   `hideLocalLoginForm`. Failure is silent (`loaded=true`, default
   `false` — matches AC4 of Story 2-3). Verified by Vitest: success
   and silent-failure paths.

4. **AC4 — Bootstrap bypass.** When the URL contains `?bootstrap=1`
   (case-insensitive "1" or "true"), the password form is visible
   regardless of the `hide_local_login_form` setting. This is the
   break-glass path for the bootstrap admin. Verified by Vitest:
   `?bootstrap=1` with `hideLocalLoginForm=true` shows the password
   form; absent `bootstrap` query keeps the original AC4 of Story
   2-3 behavior.

5. **AC5 — Fail-safe (no regression of Story 2-3 AC4).** If the
   public-settings endpoint fails AND no IdP providers are
   configured, the login page still falls back to the password form
   (Story 2-3 `forcePasswordForm` logic). Verified by Vitest.

6. **AC6 — No regression.** All existing backend + frontend tests
   continue to pass.

## Tasks / Subtasks

### Task 1: Seed setting + public endpoint (AC1, AC2)

- [x] MOD `backend/src/settings/service.py` — append to
  `DEFAULT_SETTINGS`:
  ```python
  {"key": "hide_local_login_form", "value": "false",
   "value_type": "bool", "category": "auth",
   "description": "Hide local password login form when at least one IdP is configured."}
  ```

- [x] MOD `backend/src/auth/sso_router.py` — new endpoint:
  ```python
  @router.get("/public-settings")
  def public_sso_settings(db: Session = Depends(get_db)) -> dict:
      """Public (no-auth) subset of settings needed by the login page."""
      hide_raw = get_setting_value(db, "hide_local_login_form", "false")
      admin_contact = get_setting_value(db, "admin_contact_email", "")
      return {
          "hide_local_login_form": hide_raw.lower() == "true",
          "admin_contact_email": admin_contact,
      }
  ```
  Import `get_setting_value` from `src.settings.service`.

### Task 2: Frontend — store fetch + bootstrap bypass (AC3, AC4, AC5)

- [x] MOD `frontend/src/stores/sso.store.ts` — replace the placeholder
  `loadSettings()` with:
  ```ts
  async function loadSettings(): Promise<void> {
    try {
      const res = await fetch('/api/v1/auth/sso/public-settings', {
        signal: AbortSignal.timeout(5000),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json() as { hide_local_login_form?: boolean }
      hideLocalLoginForm.value = Boolean(data.hide_local_login_form)
    } catch (err) {
      hideLocalLoginForm.value = false  // fail-safe
      // eslint-disable-next-line no-console
      console.warn('[sso.store] public-settings fetch failed', err)
    }
  }
  ```

- [x] MOD `frontend/src/views/LoginView.vue` — extend the computed
  properties to honor `?bootstrap=1`:
  ```ts
  const bootstrapOverride = computed(() => {
    const v = (route.query.bootstrap as string | undefined)?.toLowerCase()
    return v === '1' || v === 'true'
  })
  const showPasswordToggle = computed(
    () => hasSsoProviders.value && !sso.hideLocalLoginForm && !bootstrapOverride.value,
  )
  const forcePasswordForm = computed(
    () => !hasSsoProviders.value || bootstrapOverride.value,
  )
  ```
  When `bootstrapOverride` is true, the password form is always
  rendered (via `forcePasswordForm`), and no toggle is shown.

### Task 3: Backend tests (AC1, AC2)

- [x] NEW `backend/tests/settings/test_hide_local_login_seed.py` —
  unit test that seeds defaults, asserts row present with default
  `false`, PATCHes it to `true`, asserts persisted and audited.

- [x] NEW `backend/tests/auth/test_public_settings.py` — pytest
  integration test that hits `GET /api/v1/auth/sso/public-settings`
  with no auth header, asserts `200` and response shape.

### Task 4: Frontend tests (AC3, AC4, AC5)

- [x] MOD `frontend/src/tests/stores/sso.store.spec.ts` — extend
  `loadSettings` describe block:
  - `loads hideLocalLoginForm=true from public-settings success`
  - `falls back to false on HTTP error`
  - `falls back to false on fetch timeout`

- [x] MOD `frontend/src/tests/components/LoginView.spec.ts` — extend
  `hide_local_login_form admin setting (AC4)` block:
  - `?bootstrap=1 shows password form even when hideLocalLoginForm=true`
  - `?bootstrap=1 hides the password toggle (password form is forced)`
  - `no bootstrap query preserves existing hideLocalLoginForm behavior`

### Task 5: Regression (AC6)

- [x] Run `pytest backend/tests/settings/ backend/tests/auth/` and
  `npx vitest run` — all green.

## Non-goals

- A dedicated "Security" tab in the SettingsView UI — the admin
  patches the setting via the generic settings endpoint. UI polish
  is out of scope.
- Bootstrap-user detection server-side — any user can visit
  `/login?bootstrap=1` to force the password form; the actual
  login still goes through the normal credentials check.
- Rate-limiting the bootstrap endpoint — covered by Story 2-8.
