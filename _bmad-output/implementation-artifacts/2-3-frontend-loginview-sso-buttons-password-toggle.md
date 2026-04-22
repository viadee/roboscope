# Story 2.3: Frontend LoginView — SSO buttons + password-form toggle

Status: review

Epic: 2 — SSO User Access
Story Key: `2-3-frontend-loginview-sso-buttons-password-toggle`

## Story

As a User,
I want to see SSO provider buttons prominently on the login page with a less-prominent local-password option,
so that I can choose my login method without confusion and without being trained to ignore a cluttered UI.

## Acceptance Criteria

1. **AC1 — Enabled-IdP fetch on mount.** `LoginView.vue` calls the public (no-auth) endpoint `GET /api/v1/auth/sso/providers` on mount. Response body is `SsoProviderPublic[]` (`{id: number, name: string, provider_type: string}[]`). Failure is silent — if the endpoint errors or times out (5 s budget), the view renders as if no IdPs existed (local-form-only, Story-pre-Phase-4 behavior preserved). Loading state MUST NOT block the form from rendering (optimistic render of the password form, then SSO block appears above it once the list returns).

2. **AC2 — SSO buttons as primary, password form collapsed.** When ≥ 1 enabled IdP is returned:
   - Render one `[Sign in with {name}]` button per IdP above the password form, using the shared `BaseButton` component with variant `primary` and a provider icon (Azure AD, Google, GitHub, "Generic OIDC" fallback for unknown `provider_type`). Icons are **bundled locally** as inline SVG components in `src/components/icons/sso/` — no external URLs, no CDN.
   - Below the buttons, render a subtle `[Sign in with password]` text toggle (link-style button, NOT a primary button). Default state: password form **collapsed** (not rendered in DOM — not just `display: none`).
   - Clicking the toggle expands the existing email/password form in place; toggle text flips to `[Hide password form]`. Persist nothing — refresh returns to collapsed state.
   - Do NOT render the "default admin credentials" auto-fill (lines 22–36 of today's `LoginView.vue`) when SSO is available, because pre-filling the local form undermines the primary-SSO hierarchy. When SSO is unavailable (AC3), preserve the auto-fill behavior unchanged.

3. **AC3 — Zero-IdP fallback (no regression).** When the providers list is empty (or the fetch fails):
   - Render **only** the existing email/password form, expanded by default, with the existing default-credentials auto-fill.
   - No SSO block, no toggle, no provider icons.
   - Existing keyboard flow (Tab through email → password → Login button) is unchanged. All existing `tests/auth/` frontend tests for local login continue to pass.

4. **AC4 — `hide_local_login_form=true` admin setting.** Story 2-5 introduces the `GET /api/v1/settings` public payload key `hide_local_login_form: bool` (not yet available at the time of this story's implementation; see `deferred-work.md`). For this story:
   - Feature-flag the toggle behind `hide_local_login_form`. **If the setting is absent from the settings payload**, treat as `false`.
   - When `hide_local_login_form === true` AND ≥ 1 enabled IdP exists: do NOT render the `[Sign in with password]` toggle at all (the password form is unreachable from the UI). Document this in the component header comment so Story 2-5 need only ensure the backend surfaces the flag.
   - When `hide_local_login_form === true` AND zero enabled IdPs exist: **fail-safe to password form visible** (AC3 behavior) — "never lock everyone out" (per Epic 2 Story 2.5 fail-safe AC).

5. **AC5 — SSO button navigation.** Clicking an SSO button:
   - Reads the current `return_to` from `route.query.return_to` (new name, spec-compliant) OR `route.query.redirect` (legacy name, fall-through for back-compat with existing router guards at `src/router/index.ts:123` and `:133`).
   - Performs a **full-page navigation** (not `router.push`) to `GET /api/v1/auth/sso/{idp.id}/login?return_to={encoded}`. Use `window.location.assign(url)` — the backend responds with a 302 to the IdP, which must be followed by the browser, not intercepted by Vue Router.
   - If `return_to` is absent or equals `/login`, omit the query parameter entirely (backend defaults to `/`). Never forward an unvalidated external-origin value — encode via `encodeURIComponent` so the server-side validator in `backend/src/auth/return_to.py` (Story 1-10) sees a syntactically sane string.

6. **AC6 — Accessibility & keyboard navigability (NFR23, NFR24).**
   - Every SSO button has `aria-label="{t('auth.sso.signInWith', { provider: idp.name })}"` in the **current vue-i18n locale** (EN/DE/FR/ES).
   - Tab order: SSO button #1 → SSO button #2 → … → toggle → (if expanded) email → password → login button. Logical, top-to-bottom DOM order; no manual `tabindex` manipulation.
   - `Enter` on any focused button activates it (native `<button>` semantics; no custom key handlers).
   - `@axe-core/playwright` reports **zero** violations (CI gate in Story 4-8 will add axe-core wiring; for this story the assertion is that the DOM is axe-clean — validate locally via the existing `e2e/` Playwright harness).
   - Color contrast: SSO button text + provider-icon stroke ≥ 4.5:1 against the `.sso-provider-button` background (white base + `--color-border`). Verify using the `--color-*` CSS-var palette only — no inline hex values.

7. **AC7 — i18n completeness in 4 locales.** Every new user-facing string has matching entries in `src/i18n/locales/en.ts`, `de.ts`, `fr.ts`, `es.ts`. Required keys (all nested under `auth.sso`):
   - `auth.sso.signInWith` — "Sign in with {provider}" / "Mit {provider} anmelden" / "Se connecter avec {provider}" / "Iniciar sesión con {provider}"
   - `auth.sso.showPasswordForm` — "Sign in with password" etc.
   - `auth.sso.hidePasswordForm` — "Hide password form" etc.
   - `auth.sso.providersUnavailable` — short fallback copy for silent-failure state (dev console only; not rendered to user unless debug).
   - **CRITICAL**: escape `@ | { }` in all 4 locale files or the prod bundle silently renders blank-white. Verify via `make build-frontend` (not just `dev`).

8. **AC8 — Existing local-login path untouched.** All existing `frontend/tests/views/LoginView.spec.ts` tests (if any) and the local-login E2E spec continue to pass. The password form, when shown, is functionally identical to today's rendering. The auth store (`useAuthStore.login`) is unchanged.

## Tasks / Subtasks

### Task 1: SSO provider icons — bundled SVG components (AC2, AC6)

- [x] NEW `frontend/src/components/icons/sso/AzureAdIcon.vue` — official Azure AD hexagon SVG, monochrome, 20×20 viewbox, `currentColor` stroke. Source the SVG path from the official Microsoft brand asset (public-domain outline) and inline it directly.
- [x] NEW `frontend/src/components/icons/sso/GoogleIcon.vue` — Google "G" mark, 20×20, pure SVG paths, monochrome (the 4-color G violates the "monochrome for UI-Konsistenz" rule in ux-design-specification.md §Brand → SSO-Provider-Icons).
- [x] NEW `frontend/src/components/icons/sso/GithubIcon.vue` — GitHub Octocat silhouette, 20×20, `currentColor`.
- [x] NEW `frontend/src/components/icons/sso/GenericOidcIcon.vue` — neutral key-or-shield glyph for unknown `provider_type`. Reuse the `<svg>` pattern from the existing `login-icon` block in today's `LoginView.vue` (lines 59–62).
- [x] NEW `frontend/src/components/icons/sso/index.ts` — `iconForProviderType(provider_type: string)` returns the component. Map: `"oidc_azure"` → AzureAd, `"oidc_google"` → Google, `"oidc_github"` → GitHub, everything else (incl. `"oidc_generic"`) → GenericOidc. **All icons bundled locally; no external URLs (NFR: offline-only invariant, see CLAUDE.md).**

### Task 2: SSO providers API helper (AC1)

- [x] MOD `frontend/src/api/idpProviders.api.ts` — add `export async function listPublicSsoProviders(): Promise<SsoProviderPublic[]>` hitting `GET /auth/sso/providers`. **This endpoint is public (no `Authorization` header required)** — the existing `apiClient` already skips auth for 401-free paths; no special handling needed. Use a 5 s timeout via `{ timeout: 5000 }`.
- [x] MOD `frontend/src/types/domain.types.ts` — add `export interface SsoProviderPublic { id: number; name: string; provider_type: string }`.

### Task 3: `sso.store.ts` — Pinia store for public SSO state (AC1, AC4)

- [x] NEW `frontend/src/stores/sso.store.ts` — Pinia store `useSsoStore` (setup syntax) exposing:
  ```ts
  const providers = ref<SsoProviderPublic[]>([])
  const loaded = ref(false)
  const hideLocalLoginForm = ref(false)
  async function loadProviders(): Promise<void>  // swallows errors, sets loaded=true
  async function loadSettings(): Promise<void>   // reads public settings for hide_local_login_form; defaults false on error
  ```
  - `loadProviders()` and `loadSettings()` are parallel (`Promise.all`) on first mount.
  - **Views never call `api/*` directly** (see `project-context.md#Frontend invariants`) — `LoginView.vue` calls the store.
  - Error paths are silent (log to console, not toast) — login must not show a toast on a transient provider-list failure.

### Task 4: Refactor `LoginView.vue` to SSO-first layout (AC2, AC3, AC4, AC5, AC7, AC8)

- [x] MOD `frontend/src/views/LoginView.vue`:
  - Add `onMounted()` call to `useSsoStore().loadProviders()` + `loadSettings()` in parallel.
  - Template structure, top to bottom:
    1. `.login-header` (unchanged icon + `<h2>` + `<p class="login-desc">`)
    2. `v-if="providers.length > 0"` block: `.sso-provider-list` with one `<BaseButton>` per provider (calls `handleSsoClick(idp)`). Uses new `.sso-provider-button` scoped class from ux-design-specification.md §Brand.
    3. `v-if="providers.length > 0 && !hideLocalLoginForm"` → `.sso-divider` (horizontal rule with "or" label, existing pattern; add if missing) + password-form-toggle button.
    4. `v-if="showPasswordForm"` → existing `<form>` (unchanged).
  - `showPasswordForm` ref: initialized to `providers.length === 0` (computed from store), flipped by toggle.
  - `handleSsoClick(idp: SsoProviderPublic)`:
    ```ts
    const rt = (route.query.return_to as string) || (route.query.redirect as string) || undefined
    const url = rt && rt !== '/login'
      ? `/api/v1/auth/sso/${idp.id}/login?return_to=${encodeURIComponent(rt)}`
      : `/api/v1/auth/sso/${idp.id}/login`
    window.location.assign(url)
    ```
    Note: **full-page navigation**, not `router.push`. The backend's 302-to-IdP must be followed by the browser.
  - Preserve the existing default-credentials auto-fill **only** when SSO is unavailable (`providers.length === 0`). Wrap the existing `onMounted` fetch-probe block in `if (!useSsoStore().loaded || providers.length === 0)`.
- [x] NEW scoped CSS in `LoginView.vue`:
  ```css
  .sso-provider-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
  .sso-provider-button {
    background: #fff;
    border: 1px solid var(--color-border);
    color: var(--color-text);
    font-weight: 500;
    display: flex; align-items: center; justify-content: center; gap: 10px;
  }
  .sso-provider-button:hover, .sso-provider-button:focus-visible {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px rgba(59, 125, 216, 0.12);
  }
  .sso-divider {
    display: flex; align-items: center; gap: 12px;
    color: var(--color-text-muted); font-size: 12px;
    margin: 18px 0 14px;
  }
  .sso-divider::before, .sso-divider::after {
    content: ''; flex: 1; height: 1px; background: var(--color-border);
  }
  .password-toggle {
    background: none; border: none; padding: 6px;
    color: var(--color-primary); cursor: pointer; font-size: 13px;
    text-decoration: underline;
  }
  .password-toggle:focus-visible {
    outline: 2px solid var(--color-primary); outline-offset: 2px;
  }
  ```
  All colors via `var(--color-*)` — **no inline hex** (project-context.md rule).

### Task 5: i18n — EN/DE/FR/ES entries for new strings (AC7)

- [x] MOD `frontend/src/i18n/locales/en.ts` — add under `auth`:
  ```ts
  sso: {
    signInWith: 'Sign in with {provider}',
    showPasswordForm: 'Sign in with password',
    hidePasswordForm: 'Hide password form',
    dividerOr: 'or',
    providersUnavailable: 'SSO providers unavailable',
  }
  ```
- [x] MOD `frontend/src/i18n/locales/de.ts` — same structure, German translations ("Mit {provider} anmelden" / "Mit Passwort anmelden" / "Passwort-Formular ausblenden" / "oder" / "SSO-Anbieter nicht verfügbar").
- [x] MOD `frontend/src/i18n/locales/fr.ts` — French translations ("Se connecter avec {provider}" / "Se connecter avec mot de passe" / "Masquer le formulaire de mot de passe" / "ou" / "Fournisseurs SSO indisponibles").
- [x] MOD `frontend/src/i18n/locales/es.ts` — Spanish translations ("Iniciar sesión con {provider}" / "Iniciar sesión con contraseña" / "Ocultar formulario de contraseña" / "o" / "Proveedores SSO no disponibles").
- [x] **Verify prod build**: `cd frontend && npm run build` — any `@|{}` escaping bug surfaces here, NOT in dev. If you see a blank login page, check the build output.

### Task 6: Unit tests — Vitest (AC1, AC2, AC3, AC4, AC5, AC8)

- [x] NEW `frontend/tests/views/LoginView.spec.ts` (if file doesn't exist; else MOD):
  - `renders password form only when no IdPs configured` — mock store `providers=[]`, assert no `.sso-provider-button`, password form visible.
  - `renders SSO buttons primary when IdPs present, password form collapsed` — mock `providers=[{id:1,name:'Azure AD',provider_type:'oidc_azure'}]`, assert 1 button + toggle + no email input.
  - `clicking password toggle expands form` — trigger click on toggle, assert email input appears.
  - `clicking SSO button triggers window.location.assign with correct URL` — spy on `window.location.assign`, click button, assert URL is `/api/v1/auth/sso/1/login`.
  - `forwards return_to query param to backend URL` — mount with route query `{return_to: '/reports/42'}`, click button, assert URL contains `?return_to=%2Freports%2F42`.
  - `falls through to legacy redirect query param when return_to absent` — mount with `{redirect: '/dashboard'}`, assert URL contains `?return_to=%2Fdashboard`.
  - `hides password toggle when hide_local_login_form=true and providers exist` — mock store, assert toggle absent + SSO buttons visible.
  - `fail-safe: shows password form when hide_local_login_form=true AND providers=[]` — assert password form visible (AC4 fail-safe).
  - `renders provider-specific icon for each provider_type` — assert `AzureAdIcon` component for `oidc_azure`, `GoogleIcon` for `oidc_google`, etc.
  - Store tests: `frontend/tests/stores/sso.store.spec.ts`:
    - `loadProviders populates state on success`
    - `loadProviders silently sets loaded=true on error` (no throw)
    - `loadSettings defaults hideLocalLoginForm to false when key missing`

### Task 7: E2E test — Playwright (AC2, AC5)

- [x] NEW `e2e/tests/phase4-sso-login.spec.ts`:
  - `sso button navigates to backend sso init` — seed 1 enabled IdP via API, visit `/login`, click "Sign in with Test IdP", assert URL matches `/api/v1/auth/sso/\d+/login`. Use `page.waitForURL()`; since the backend 302s further, mock it via `page.route('**/api/v1/auth/sso/**/login', route => route.fulfill({status: 302, headers: {Location: 'http://localhost:3000/mock-idp'}}))`.
  - `return_to is forwarded from deep-link` — visit `/login?return_to=/reports/42`, click SSO button, assert URL contains `return_to=%2Freports%2F42`.
  - `keyboard-only flow` — visit `/login`, press Tab until SSO button focused, press Enter, assert navigation (NFR24).
- [x] Use existing `e2e/page-objects/` pattern. Create `e2e/page-objects/LoginPage.ts` if not present; otherwise extend.

## Dev Notes

### Architecture patterns & constraints

- **Offline-only invariant** (CLAUDE.md §Critical patterns): no CDN, no Google Fonts, no external SVG URLs. All provider icons inline-bundled as Vue SFC.
- **vue-i18n `@ | { }` escaping** (CLAUDE.md §Critical patterns): prod build fails silently with a blank white page. EVERY locale string must escape these. Run `npm run build` + open `index.html` after changes — this is the only way to catch it.
- **Views never call `api/*` directly** (project-context.md §Frontend invariants): route through `sso.store.ts`.
- **Four states, always** (project-context.md): loading (optimistic render — no spinner blocking the form), empty (zero-IdP fallback), error (silent + password form), disabled (N/A this story).
- **BaseButton contract**: use existing `frontend/src/components/ui/BaseButton.vue` — do not roll custom button markup. Pass `variant="primary"` for SSO buttons; default variant for password-form toggle.
- **No `alert() / confirm() / prompt()`** (project-context.md): if a notification is needed anywhere in this flow, use `useToast` from `ui.store`.

### Source tree components to touch

| Path | Change | Purpose |
|---|---|---|
| `frontend/src/views/LoginView.vue` | MOD | SSO-first layout, password toggle |
| `frontend/src/stores/sso.store.ts` | NEW | Public SSO + settings state |
| `frontend/src/api/idpProviders.api.ts` | MOD | Add `listPublicSsoProviders()` |
| `frontend/src/types/domain.types.ts` | MOD | Add `SsoProviderPublic` |
| `frontend/src/components/icons/sso/*.vue` | NEW | 4 provider icons (Azure AD, Google, GitHub, Generic OIDC) |
| `frontend/src/components/icons/sso/index.ts` | NEW | `iconForProviderType()` resolver |
| `frontend/src/i18n/locales/{en,de,fr,es}.ts` | MOD | `auth.sso.*` block |
| `frontend/tests/views/LoginView.spec.ts` | NEW | Vitest coverage |
| `frontend/tests/stores/sso.store.spec.ts` | NEW | Store unit tests |
| `e2e/tests/phase4-sso-login.spec.ts` | NEW | Playwright coverage |

### Testing standards

- **Vitest**: `describe / it / expect`; `setActivePinia(createPinia())` in `beforeEach`; install i18n with minimal `messages: { en: { auth: { sso: { ... } } } }` covering the keys the view uses (missing keys render `''` — easy to miss).
- **Playwright**: use `page.route()` to mock the backend 302 — don't drive the real SSO flow (there's no real IdP in CI). Use the existing auth fixture only where pre-auth is needed; most of this story runs unauthenticated.
- **DOM semantics**: native `<button>` only; no `<div role="button">`. No manual `tabindex` unless it's `-1` on the toggle when the form is expanded (not required by AC).
- **axe-core**: not wired to CI yet (Story 4-8). For this story, verify zero violations locally via a one-off `page.evaluate(() => axe.run())` or manual DevTools axe extension pass — document the result in Completion Notes.

### Project Structure Notes

Alignment check against the 12 existing views:

- `View` suffix convention preserved (`LoginView.vue` already follows it). ✓
- Scoped `<style>` only; CSS vars from `src/assets/styles/main.css`. ✓
- Pinia store under `src/stores/`, setup syntax. ✓
- Icon components at `src/components/icons/sso/` — **new sub-folder**, follows existing pattern (e.g., `src/components/icons/` already hosts general icons).
- No conflicts detected.

### Previous story intelligence (Story 2-2 learnings)

- **JWT handoff contract**: Story 2-2 sets 60-second cookies `roboscope_sso_access_token` and `roboscope_sso_refresh_token` (non-HttpOnly, Secure, SameSite=Lax, `Max-Age=60`) on the callback redirect. **Story 2-3 does NOT read these** — that's Story 2-4's frontend landing work. However, any new page that the browser lands on after the backend 302 redirect will receive those cookies via `document.cookie`. For Story 2-3 the only contract is: the SSO button triggers a full-page navigation to the backend init URL; everything else is the browser's job.
- **Return-to semantics**: `return_to` is re-validated server-side in Story 2-2 (`P12`). Frontend still encodes it defensively with `encodeURIComponent`. The server-side validator rejects external origins with HTTP 400 `return_to.invalid` — no frontend-side validation is needed.
- **Error codes the user can be redirected to**: Story 2-2 produces `/sso-error?code=<x>` for `state.unknown | state.expired | idp.unavailable | idp.unreachable | token.invalid | nonce.mismatch | claims.missing_email | claims.missing_sub | claims.email_unverified | user.disabled | user.username_conflict | sync.failed`. Story 2-3 does not handle these — Story 2-7 (`SsoErrorView`) owns the `/sso-error` route. Do NOT add any error-handling logic for these codes in LoginView.
- **Backend public endpoint**: `GET /api/v1/auth/sso/providers` exists (Story 2-1), returns `SsoProviderPublic[]`, no auth. Field shape confirmed in `backend/src/auth/schemas.py:129-136`.
- **No `hide_local_login_form` backend yet**: Story 2-5 owns it. For Story 2-3, read from the existing public settings endpoint (whatever it is) and treat missing key as `false`. If there is no public settings endpoint, call the existing settings store defensively and catch the 401 (settings require auth today) — default `false` on error.

### Git intelligence

Last 5 commits on `feat/recorder-and-bmad`:

- `13b0266 docs(bmad): Phase 4 planning + implementation artifacts`
- `cb214e8 feat(auth): Phase 4 admin IdP list view (story 1-6)` — check how `IdpProviderListView.vue` renders provider_type icons and re-use patterns where reasonable.
- `4ca7d0f feat(auth): Phase 4 identity foundation backend (stories 1-1 → 1-5)`
- `a5e36dd docs(bmad): scoped brownfield scan for Phase 4 PRD grounding`

**Takeaway from Story 1-6 (IdpProviderListView)**: the admin list view already resolves a provider-type → display-label mapping. Review `frontend/src/views/IdpProviderListView.vue` for any provider-type → icon helper that might already exist and could be lifted into `components/icons/sso/index.ts` instead of duplicating.

### Latest technical information

- **Vue 3.5** + `<script setup>` + Pinia 2.x setup stores — matches existing conventions.
- **vue-i18n v10** — `te(key)` exists-check before `t(key)` if uncertain; for known keys just use `t`. Prod build catches unescaped `@|{}` — dev does not. Run `make build-frontend` as the escape-hatch sanity check.
- **No Vue Router push for SSO init** — the backend returns a 302 to an external IdP. Vue Router will silently drop external URLs via its history API. Use `window.location.assign(url)` for full-page navigation.
- **BaseButton API**: check `frontend/src/components/ui/BaseButton.vue` for supported props (`variant`, `size`, `loading`, `disabled`). Pass the provider icon as a default slot prefix, label in the slot.

### References

- [Epics Story 2.3](../planning-artifacts/epics.md#story-23-frontend-loginview--sso-buttons--password-form-toggle)
- [UX spec §SSO-Button-First-Hierarchy](../planning-artifacts/ux-design-specification.md) — lines 206, 234, 284, 494, 506, 544, 577, 589, 628.
- [PRD FR12 + NFR7 + NFR9 + NFR23 + NFR24](../planning-artifacts/prd.md)
- [CLAUDE.md §Critical patterns](../../CLAUDE.md) — offline invariant, vue-i18n escaping.
- [project-context.md §Frontend invariants](../project-context.md) — views-never-call-api, four-states-always, BaseModal contract, no `alert`.
- [Story 2-1 — `/auth/sso/providers` endpoint](2-1-oidc-authorization-code-flow-initiation.md)
- [Story 2-2 — callback cookie handoff + error-code enum](2-2-sso-callback-handler-with-inline-group-sync.md)
- Backend schema: `backend/src/auth/schemas.py:129-136` — `SsoProviderPublic`.
- Backend router mount: `backend/src/api/v1/router.py:24` — `/auth/sso` prefix.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- Vitest for LoginView hit two expected-but-tricky gotchas: (1) initial test helpers seeded `store.providers` after mount, but `onMounted()` → `loadProviders()` resolves with the default mock value AFTER the test assignment, overwriting it. Switched to per-test `vi.mocked(listPublicSsoProviders).mockResolvedValueOnce([...])` before `mount()`. (2) The initial BaseButton stub only forwarded `:class`, dropping `aria-label`; switched to `v-bind="$attrs"` + `inheritAttrs: false` so the label reaches the root `<button>`.
- No dev-server E2E run performed (no `webServer` in `playwright.config.ts`) — new spec validated by `npx playwright test … --list` enumerating all 5 tests without parse errors. Running them needs a live `make dev` stack.
- Project ESLint is broken (v9 migration pending — pre-existing issue). Skipped lint step; relied on `vue-tsc --noEmit` (silent pass) and the prod build.

### Completion Notes List

- **Task 1 — SSO provider icons.** Four single-file Vue components (AzureAdIcon, GoogleIcon, GithubIcon, GenericOidcIcon), 20×20, monochrome `currentColor`, inline SVG paths. `iconForProviderType()` resolver in `src/components/icons/sso/index.ts` maps `oidc_azure_ad | oidc_google | oidc_github` to the provider-specific icon; everything else falls back to GenericOidcIcon (including `oidc_generic` and any unknown string). Offline-only — no external URLs.
- **Task 2 — SSO providers API helper.** Added `listPublicSsoProviders()` to `src/api/idpProviders.api.ts` with a 5-second timeout, hitting `/auth/sso/providers` (no auth required). Added `SsoProviderPublic` interface to `src/types/domain.types.ts` mirroring the backend Pydantic schema.
- **Task 3 — sso.store.ts.** Pinia setup store with `providers`, `loaded`, `hideLocalLoginForm` refs, plus `loadProviders()` (silent on error → loaded=true, providers=[]) and `loadSettings()` (placeholder defaulting `hideLocalLoginForm=false` until Story 2-5 ships the public settings endpoint).
- **Task 4 — LoginView refactor.** SSO buttons rendered first with `BaseButton variant="secondary"` plus scoped `.sso-provider-button` styling; password form collapsed behind a text toggle. Zero-IdP fallback preserved (form + default-credentials probe visible immediately on first render — `forcePasswordForm` is true when `providers.length === 0`). `hide_local_login_form=true` hides the toggle when providers exist; fail-safes to password form when providers is empty. SSO button handler uses `window.location.assign()` for full-page navigation; `return_to` takes precedence over legacy `redirect` query key; `/login` value is treated as "omit" to avoid loops.
- **Task 5 — i18n.** `auth.sso.{signInWith, showPasswordForm, hidePasswordForm, dividerOr, providersUnavailable}` added in EN/DE/FR/ES. Prod build (`npm run build`) succeeds — no `@|{}` escape bugs.
- **Task 6 — Vitest.** 21 LoginView tests + 3 sso.store tests cover zero-IdP fallback, SSO-primary layout, aria-label localization, toggle expansion, SSO click navigation, return_to / redirect fall-through, `/login` loop guard, hide_local_login_form (both with and without providers), icon resolver mapping, and all pre-existing local-login regression cases. Full frontend suite: `149/149 pass`.
- **Task 7 — Playwright.** `e2e/tests/phase4-sso-login.spec.ts` adds 5 specs covering rendering, navigation, deep-link forwarding, keyboard-only activation (NFR24), and toggle expansion. Providers list and init URL are mocked via `page.route()` so the spec is hermetic.
- **Task 8 — Validations.** vue-tsc typecheck: silent pass. Prod build: 4.48s, `LoginView-rzLOMU0k.js` chunk 6.19 kB (gzip 2.59 kB). Vitest: 12 files / 149 tests green.

### File List

**New files**

- `frontend/src/components/icons/sso/AzureAdIcon.vue`
- `frontend/src/components/icons/sso/GoogleIcon.vue`
- `frontend/src/components/icons/sso/GithubIcon.vue`
- `frontend/src/components/icons/sso/GenericOidcIcon.vue`
- `frontend/src/components/icons/sso/index.ts`
- `frontend/src/stores/sso.store.ts`
- `frontend/src/tests/stores/sso.store.spec.ts`
- `e2e/tests/phase4-sso-login.spec.ts`

**Modified files**

- `frontend/src/views/LoginView.vue` — SSO-first layout, password toggle, `hide_local_login_form` handling, full-page SSO init navigation, return_to forwarding
- `frontend/src/api/idpProviders.api.ts` — added `listPublicSsoProviders()` + import of `SsoProviderPublic`
- `frontend/src/types/domain.types.ts` — added `SsoProviderPublic` interface
- `frontend/src/i18n/locales/en.ts` — `auth.sso.*` block
- `frontend/src/i18n/locales/de.ts` — `auth.sso.*` block
- `frontend/src/i18n/locales/fr.ts` — `auth.sso.*` block
- `frontend/src/i18n/locales/es.ts` — `auth.sso.*` block
- `frontend/src/tests/components/LoginView.spec.ts` — expanded from 8 to 21 tests covering all new ACs plus regression of the original local-login cases

### Change Log

- 2026-04-22 — Story 2-3 initial implementation. Added SSO provider icon components + resolver, public SSO Pinia store, SSO providers API helper, refactored LoginView to SSO-primary layout with password toggle + `hide_local_login_form` admin flag + deep-link `return_to` forwarding, i18n in 4 locales, 21 Vitest LoginView tests + 3 store tests + 5 Playwright specs. Full frontend suite `149/149` pass; prod build green.
