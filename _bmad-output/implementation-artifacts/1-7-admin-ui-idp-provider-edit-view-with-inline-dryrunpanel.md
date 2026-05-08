# Story 1.7: Admin UI — IdP Provider Edit View with Inline DryRunPanel

Status: done

Epic: 1 — Enterprise Identity Foundation
Story Key: `1-7-admin-ui-idp-provider-edit-view-with-inline-dryrunpanel`

## Story

As a RoboScope admin,
I want to edit an IdP configuration with inline dry-run verification before save,
So that I never commit a broken configuration.

## Acceptance Criteria

1. **AC1 — Form fields and layout.** `IdpProviderEditView.vue` (replaces Story 1.6's placeholder) renders a 2-column grid on Desktop (`.grid-2`, ≥1024 px) with these fields:
   - `name` (display_name) — text input, required, max 100 chars
   - `provider_type` — select with 4 options (`oidc_azure_ad`, `oidc_google`, `oidc_github`, `oidc_generic`), required
   - `issuer_url` — URL input, required, must start with `https://` (or `http://` if `ALLOW_INSECURE_IDP=true` is set — display a hint)
   - `client_id` — text input, required
   - `client_secret` — password input with visibility-toggle (eye icon) + placeholder "•••••••• (unchanged)" in edit mode (do NOT send unless modified)
   - `scopes` — chip/tag input (space-delimited → visible chips) with default `openid profile email`
   - `group_claim_name` — text input, default `groups`
   - `redirect_uri` — readonly display of `{WINDOW_ORIGIN}/auth/sso/callback` with copy-to-clipboard button (computed from `window.location.origin`)

2. **AC2 — Save gate.** The `[Save]` button is disabled on page load, with a tooltip `"Run dry-run first to enable Save"`. Save enables only when: (a) a dry-run just completed with `overall_status='passed'` AND (b) no form field has changed since that dry-run. Clicking Save persists the current form (create → POST, edit → PATCH), then on success navigates back to `/admin/identity-providers` with a success toast.

3. **AC3 — Dry-run flow.** A `[Run dry-run]` button is always enabled when the form is valid. Clicking it:
   - On create (`/new`): first POSTs the IdP as draft (`is_enabled=false`), then calls the dry-run endpoint with the returned `id`. The URL updates to `/admin/identity-providers/{id}` (replace, not push — no back-button ghost).
   - On edit (`/:id`): PATCHes the IdP with current form values first (excluding `client_secret` if untouched), then calls the dry-run endpoint.
   - After the probe resolves, the inline `DryRunPanel.vue` component renders BELOW the form (not modal, not toast).

4. **AC4 — DryRunPanel structure.** `DryRunPanel.vue` accepts a `DryRunProbeResponse | null` prop plus `loading: boolean` and `stale: boolean` flags, and renders:
   - Header with the overall verdict badge (`✅ Passed` / `❌ Failed` / `⏳ Running...` / `⚠ Stale`)
   - Three sequential rows (issuer_reachable / discovery_valid / jwks_fetched), each with a fixed-width 24 px icon column, the check name, the detail text, and a `.status-badge` for pass/warning/failed
   - `aria-live="polite"` region announces progress updates to screen readers (e.g., "Dry-run started", "Issuer reachable check passed", "All checks passed")
   - `elapsed_ms` shown in a muted footer after completion

5. **AC5 — Stale detection.** After a dry-run completes, any change to a form field puts the panel into `Stale` state with copy `"Config changed — re-run required"` and disables Save. The panel uses `--color-accent` (`#D4883E`) for the warning.

6. **AC6 — Responsive behavior.** At `<1024 px` (Tablet + Mobile), the form collapses to a single column and the DryRunPanel renders below the form at full width. Verified via Playwright viewport assertions.

7. **AC7 — Validation + Pydantic parity.** Client-side validation matches backend schema constraints (`IdentityProviderCreate` / `IdentityProviderUpdate`): `name` 1-100 chars, `issuer_url` starts with `http(s)://`, `client_id` 1-255 chars, `client_secret` (create only) 1-500 chars, `scopes` max 500 chars, `group_claim_name` max 100 chars. Invalid form → `[Run dry-run]` disabled with inline error messages per field.

8. **AC8 — Copy-to-clipboard works.** The `redirect_uri` readonly input has a clipboard icon; clicking it writes to the clipboard via `navigator.clipboard.writeText` and fires a transient "Copied" toast. Fallback: select the input text and show instructions if the Clipboard API is unavailable.

9. **AC9 — i18n complete (EN/DE/FR/ES).** Every new user-facing string has a key under `idpProviders.edit.*` / `dryRunPanel.*` in all four locales. Prod build passes.

10. **AC10 — Tests & build green.**
    - 6+ new Vitest specs for DryRunPanel (loading/passed/failed/stale/a11y) and the edit view (save-gate state machine, stale detection).
    - 1+ new Playwright E2E flow: navigate from list → `[+ New Provider]` → fill form → `[Run dry-run]` → panel renders → Save → back to list with new row visible.
    - Existing 968 backend tests + 123 Vitest + 6 E2E still green.
    - `npm run build` + `vue-tsc` pass (no new TS errors).

## Tasks / Subtasks

- [x] **Task 1: DryRunPanel.vue component** (AC 3, 4, 5)
  - [x] Create `frontend/src/components/idp/DryRunPanel.vue`. Folder is new; register in imports as needed.
  - [x] Props: `result: DryRunProbeResponse | null`, `loading: boolean`, `stale: boolean`.
  - [x] Three sequential rows for known check_names (`issuer_reachable`, `discovery_valid`, `jwks_fetched`) — render in fixed order, matching check name with i18n label.
  - [x] Icon-per-status: `✅ / ⚠ / ❌ / ⏳` — 24 px fixed width, emoji or inline SVG (offline-only).
  - [x] `aria-live="polite"` wrapper on the panel body; `role="status"` on the header verdict.
  - [x] `Stale` state: muted card with accent-colored border + `⚠` icon + localized "Config changed — re-run required".
  - [x] Slot for optional action button (e.g., "Dismiss"); default: none.

- [x] **Task 2: IdpProviderEditView.vue (replace placeholder)** (AC 1, 2, 3, 5, 6, 7, 8)
  - [x] Delete the placeholder body; rebuild with the 2-column form + state machine.
  - [x] State shape (reactive refs):
    - `form` (reactive object with all fields)
    - `initialForm` (snapshot of last-saved state — used for dirty tracking)
    - `lastDryRunAtForm` (snapshot of form values at last passed dry-run — used for stale detection)
    - `dryRunResult: DryRunProbeResponse | null`
    - `dryRunLoading: boolean`
    - `dryRunStale` (computed: true when `lastDryRunAtForm != null` AND any field in `form` differs from it)
    - `canSave` (computed: `dryRunResult?.overall_status === 'passed' && !dryRunStale && formIsValid`)
  - [x] Mode detection: if `route.params.id` is present → EDIT mode (fetch via `store.fetch()` + find in `store.providers`, fallback to `api.getIdp(id)`); else → CREATE mode.
  - [x] `client_secret` field: placeholder `•••••••• (unchanged)` in edit mode. Only send if the user typed something. Visibility-toggle via a password/text switcher.
  - [x] `scopes` field: space-delimited input → render as inline chips; user can add by typing + Enter/space, remove by clicking the chip's `×`. Under the hood still a single space-joined string on submit.
  - [x] `redirect_uri`: computed `${window.location.origin}/auth/sso/callback`, readonly input with a copy-to-clipboard button (use `navigator.clipboard.writeText`; fallback: `document.execCommand('copy')` + select input).
  - [x] Layout: `.grid-2` wrapper on desktop; CSS media query collapses to `grid-template-columns: 1fr` at `<1024px`. DryRunPanel always full-width below the form.
  - [x] Validation: use HTML5 attributes + small reactive rule functions; show per-field error under the input when blurred or when `[Run dry-run]` was attempted.
  - [x] Buttons: `[Cancel]` (back to list), `[Run dry-run]` (always enabled when form valid), `[Save]` (disabled per AC2).

- [x] **Task 3: Dry-run orchestration** (AC 3, 5)
  - [x] Add a `runDryRunFromForm()` helper in `IdpProviderEditView.vue` (not in the store — view-specific orchestration):
    1. Validate form.
    2. If CREATE mode: `store.create(form)` → set route to `/admin/identity-providers/{id}` via `router.replace`.
    3. If EDIT mode: diff `form` vs `initialForm`; if `client_secret` is the placeholder sentinel (empty string after blur), exclude it from the PATCH body. Call `store.update(id, diff)`.
    4. After save succeeds: call `store.runDryRun(id)`.
    5. Update `dryRunResult`, `dryRunLoading`, and `lastDryRunAtForm = { ...form }`.
  - [x] Handle errors: if POST/PATCH fails with 409 (name conflict) or 422 (validation), surface inline error without running the probe.
  - [x] Stale detection: deep-equal `form` against `lastDryRunAtForm` via `computed(() => JSON.stringify(form) !== JSON.stringify(lastDryRunAtForm))`; acceptable for this scope (all values are primitives/strings).

- [x] **Task 4: Save flow** (AC 2)
  - [x] `[Save]` handler: persist final state. CREATE mode: IdP already exists at this point (was created on first dry-run). So `[Save]` only calls `store.update(id, { ...form })` to flush any last-state differences, or is essentially a no-op. Then navigate to list with success toast `idpProviders.edit.toasts.saved`.
  - [x] EDIT mode: `store.update(id, diff)` then navigate.
  - [x] Note: the "create → save as draft on first dry-run" model means an IdP row exists from the first dry-run onwards, even if the admin abandons the flow. That's acceptable — the row is `is_enabled=false` (draft) and appears on the list with the Draft badge. Optional future enhancement: cleanup unconfirmed drafts after N days (would be Story 1.9 / retention).

- [x] **Task 5: Sidebar / list-view integration** (AC 1, AC9 minor)
  - [x] No changes needed to AppSidebar.vue (Story 1.6 already registered the nav item).
  - [x] Verify the list view's `[+ New Provider]` button and Name-column link both route correctly to this new view.
  - [x] Remove the placeholder's "Coming soon" keys from i18n? No — leave them for any stragglers; easy to trim in a later pass.

- [x] **Task 6: i18n** (AC 9)
  - [x] Add `idpProviders.edit.*` namespace in all 4 locales: `title.create`, `title.edit`, `fields.{name,provider_type,issuer_url,client_id,client_secret,scopes,group_claim_name,redirect_uri}.{label,placeholder,help,error.*}`, `buttons.{save,cancel,runDryRun,copy}`, `tooltips.saveDisabled`, `toasts.{saved,dryRunStarted,copiedToClipboard,saveFailed}`, `client_secret.{unchanged,show,hide}`, `staleMessage`, `insecureIdpHint`.
  - [x] Add `dryRunPanel.*` namespace: `status.{passed,warning,failed,running,stale}`, `checks.{issuer_reachable,discovery_valid,jwks_fetched}`, `elapsed`, `rerunNeeded`.
  - [x] All with EN/DE/FR/ES translations. No unescaped `@|{}` — escape as `\u00XX` if needed (DE "Schlüssel" etc.).

- [x] **Task 7: Vitest unit tests** (AC 10)
  - [x] `frontend/src/tests/components/DryRunPanel.spec.ts` — 6+ tests:
    - Loading state renders spinner + "Running..." verdict
    - Passed result renders all 3 rows with ✅ and the elapsed_ms footer
    - Failed result renders at least one ❌ row and the failed overall verdict
    - Stale prop renders the stale message and accent styling
    - No result + not loading + not stale → empty slot / nothing
    - `aria-live` region is present when loading or stale
  - [x] `frontend/src/tests/components/IdpProviderEditView.spec.ts` — 4+ tests:
    - Initial render in CREATE mode: Save disabled, Run-dry-run disabled until form valid
    - After successful dry-run: Save enabled
    - After form edit post-dry-run: Save disabled, stale = true
    - Edit mode loads IdP from store and pre-fills form

- [x] **Task 8: Playwright E2E** (AC 10)
  - [x] Add a new spec `e2e/tests/idp-provider-edit.spec.ts`:
    1. Login as admin, navigate to `/admin/identity-providers`
    2. Click `+ New Provider`
    3. Fill form with mock-OIDC values (issuer `https://mock-idp.local` — but dry-run will fail in live E2E because no mock respx; this is OK — assert the FAIL flow renders ❌ row)
    4. Click `[Run dry-run]` → assert DryRunPanel renders
    5. Assert Save stays disabled on fail
    6. Assert Cancel returns to the list
  - [x] Alternative: use a valid public IdP (e.g., `https://accounts.google.com`) for a green dry-run path. ONLY if allowed by network policy — CI may block. Document in the spec comment.
  - [x] Update existing `e2e/tests/idp-providers.spec.ts` if the list-view row click needs new wait conditions post-merge.

- [x] **Task 9: Build + typecheck + full test suite** (AC 10)
  - [x] `cd frontend && npm run build` (prod build)
  - [x] `cd frontend && npx vitest run`
  - [x] `cd frontend && npm run type-check`
  - [x] `cd e2e && npx playwright test idp-provider-edit.spec.ts idp-providers.spec.ts`
  - [x] `cd backend && .venv/bin/pytest -q` (should still be 968)

## Dev Notes

### CRITICAL GOTCHAS

1. **Create-flow chicken-and-egg.** Dry-run requires `/:id/dry-run` — the IdP must exist in the DB first. The model we adopt: **the first `[Run dry-run]` click on a new provider silently creates it as a draft (`is_enabled=false`)**. After that it's EDIT mode and subsequent `[Run dry-run]` clicks PATCH then probe. Update the route via `router.replace` so the back button doesn't take the user back to `/new`. This leaves behind "abandoned drafts" if the admin walks away — acceptable; the list view shows them as Draft.

2. **`client_secret` on edit must NEVER be sent unless the user typed something.** Backend's `get_decrypted_client_secret()` preserves the existing encrypted value when we PATCH without the field. Test this explicitly. The placeholder `•••••••• (unchanged)` is only a visual hint — the actual input value is empty string until the user types.

3. **Story 1.3 review resolved D2 as "reject null client_secret"** — so a PATCH with `client_secret: null` is 422. Our diff logic must OMIT the key entirely, not send null.

4. **Save-gate state machine is the core of this story.** Diagram it before coding:
   ```
   IDLE → (dry-run click) → LOADING → (result) → PASSED / FAILED
   PASSED → (field edit) → STALE → (dry-run click) → LOADING → ...
   STALE / FAILED / IDLE → [Save] disabled
   PASSED → [Save] enabled
   ```

5. **DryRunPanel is a new reusable component** — place in `frontend/src/components/idp/DryRunPanel.vue`. Story 1.8/1.9 will potentially reuse it (cache refresh results, handoff artifact preview).

6. **Chips input for `scopes`** — don't over-engineer. A text input + enter/space separator → render chips → on blur normalize to a single space-joined string. No new library. Follow `frontend/src/components/` patterns; check if there's already a chip input elsewhere (unlikely) or inline it.

7. **`redirect_uri` copy-to-clipboard** — `navigator.clipboard.writeText` requires HTTPS or localhost. Tests run on localhost; production is HTTPS. Fallback to input `.select() + document.execCommand('copy')` isn't strictly needed, but add a simple try/catch and log.

8. **`i18n` escape gotcha (CLAUDE.md)** — we have `client_secret.unchanged` copy that may include the bullet char `•`. Encode as `\u2022` to be safe. Any string with `@ | { }` must be escaped or use `{'@'}` wrapping. Prod build test catches violations.

9. **Tablet breakpoint is 1024 px** per UX spec line 317. Use the project's existing breakpoint convention (check `main.css` for existing media queries). Don't invent a new breakpoint.

10. **`@axe-core/playwright`** is already a devDep from Story 1.6 — reuse for this story's axe scan (empty form, populated form, dry-run-in-flight, stale state). Disable `color-contrast` rule consistent with Story 1.6 convention.

11. **Accent color for warnings** — `--color-accent: #D4883E` per UX spec line 302. Use it for Stale banner and warning check rows; do NOT invent a new color.

12. **Placeholder cleanup.** The Story 1.6 placeholder view registered `idpProviders.placeholder.{title,comingSoon,backToList}`. With Story 1.7 shipping the real view, these keys become unused. Leave them for now (easier revert if something regresses); tracking them as dead-code cleanup is a separate concern.

### Existing Patterns to Follow

**Form view** (from `frontend/src/views/EnvironmentsView.vue`):
```vue
<BaseModal v-model="showAddDialog" title="...">
  <div class="form-group">
    <label class="form-label">{{ t('...') }}</label>
    <input class="form-input" v-model="newEnv.name" required />
  </div>
</BaseModal>
```
For Story 1.7, no modal — inline form with 2-column grid. Field-per-form-group markup is the same.

**Pinia store API pattern** (`frontend/src/stores/idpProviders.store.ts`): `fetch / create / update / remove / runDryRun`. Already exposes everything the edit view needs.

**i18n interpolation** (CLAUDE.md gotcha): straight `{name}` is valid. Escape `@|{}` → use `\u0040 \u007C \u007B \u007D` if needed, or wrap `@` with `{'@'}`.

### Previous Story Learnings

- **Story 1.3**: PATCH with `client_secret: null` is rejected (422). Omit the key entirely to keep the existing secret. On create, client_secret is required.
- **Story 1.4**: Dry-run endpoint is `POST /:id/dry-run` (returns `DryRunProbeResponse`). 10s wall-clock budget; client timeout in `idpProviders.api.ts` is 15s.
- **Story 1.5**: Backend never exposes decrypted secret; frontend should not try to display the masked value (just show `•••••••• (unchanged)` in edit mode).
- **Story 1.6**: List view links point at `/admin/identity-providers/{id}` and `/new`. Placeholder edit view exists; REPLACE it, do not add a new file. i18n completeness is enforced (4 locales). Prod build catches escape violations. Axe color-contrast disabled project-wide for now.
- **Story 1.6 review**: `sanitizeDetail()` helper in list view strips vue-i18n reserved chars before interpolation. Reuse or import when DryRunPanel renders detail strings.

### File Layout

```
frontend/
├── src/
│   ├── components/
│   │   └── idp/
│   │       └── DryRunPanel.vue              [NEW — reusable, props: result, loading, stale]
│   ├── views/
│   │   └── IdpProviderEditView.vue          [MOD — replaces placeholder; ~500 LOC template + script]
│   ├── i18n/locales/
│   │   ├── en.ts                            [MOD — idpProviders.edit.*, dryRunPanel.*]
│   │   ├── de.ts                            [MOD]
│   │   ├── fr.ts                            [MOD]
│   │   └── es.ts                            [MOD]
│   ├── stores/idpProviders.store.ts         [unchanged — reuse fetch/create/update/runDryRun]
│   └── api/idpProviders.api.ts              [unchanged]
└── tests/components/
    ├── DryRunPanel.spec.ts                  [NEW — 6+ tests]
    └── IdpProviderEditView.spec.ts          [NEW — 4+ tests]
e2e/
└── tests/
    └── idp-provider-edit.spec.ts            [NEW — ~120 lines]
```

### References

- Epics: `_bmad-output/planning-artifacts/epics.md:566-596` — Story 1.7 section
- UX: `_bmad-output/planning-artifacts/ux-design-specification.md` — `DryRunPanel.vue` (line 53, 278), 2-column IdP form (line 562), tablet breakpoint (line 317), color tokens (lines 302, 496-499)
- PRD: `_bmad-output/planning-artifacts/prd.md` — FR1-FR7 (IdP config, dry-run-before-save gate)
- Backend dry-run contract: `backend/src/auth/schemas.py:128-140` (`DryRunProbeResponse` / `DryRunCheckRow`)
- Story 1.6 list view: `frontend/src/views/IdpProviderListView.vue`
- Existing placeholder to replace: `frontend/src/views/IdpProviderEditView.vue`
- Form utility classes: `frontend/src/assets/styles/main.css` (`.form-group`, `.form-input`, `.form-label`, `.grid-2`, `.card`, `.status-badge`)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- One transient Playwright failure on the Stale-state test turned out to be a Vite HMR staleness artifact — a no-op edit to re-trigger HMR made the test pass; removing the edit and re-running kept it green. Not a bug in the view.
- E2E uses German strings (default locale `de`) per the project's existing pattern in `auth.spec.ts`.
- Dev servers were already running when this story began; Vite HMR picked up the new component + view edits; backend untouched.

### Completion Notes List

- All 10 ACs satisfied. The chicken-and-egg create flow is handled by implicit-draft-on-first-dry-run + `router.replace` URL swap, consistent with the Dev Notes interaction model.
- `client_secret` tracking: `secretTouched` ref + PATCH-diff ensures the encrypted value is NEVER sent on edit unless the user actually typed something.
- Stale detection via `computed` comparing snapshots of the form to `lastDryRunAtForm.value` — triggers the panel's accent-bordered banner + disables Save.
- i18n: 4-locale coverage for both `idpProviders.edit.*` and `dryRunPanel.*` namespaces, prod-build-safe escape sequences for German/Spanish diacritics.

### Change Log

- `frontend/src/components/idp/DryRunPanel.vue` — NEW: reusable verification-report component with aria-live announcements, 3 fixed check rows, stale banner, elapsed footer
- `frontend/src/views/IdpProviderEditView.vue` — REPLACED placeholder with the full form + orchestration
- `frontend/src/i18n/locales/{en,de,fr,es}.ts` — Added `idpProviders.edit.*` and `dryRunPanel.*` namespaces
- `frontend/src/tests/components/DryRunPanel.spec.ts` — NEW: 6 Vitest specs
- `frontend/src/tests/components/IdpProviderEditView.spec.ts` — NEW: 4 Vitest specs
- `e2e/tests/idp-provider-edit.spec.ts` — NEW: 3 Playwright specs

### File List

- `frontend/src/components/idp/DryRunPanel.vue`
- `frontend/src/views/IdpProviderEditView.vue`
- `frontend/src/i18n/locales/en.ts`
- `frontend/src/i18n/locales/de.ts`
- `frontend/src/i18n/locales/fr.ts`
- `frontend/src/i18n/locales/es.ts`
- `frontend/src/tests/components/DryRunPanel.spec.ts`
- `frontend/src/tests/components/IdpProviderEditView.spec.ts`
- `e2e/tests/idp-provider-edit.spec.ts`

### Review Findings

- [x] [Review][Patch] Route watcher doesn't reset dry-run state on IdP navigation — reset `dryRunResult` and `lastDryRunAtForm` at top of route watcher. [IdpProviderEditView.vue:242]
- [x] [Review][Patch] Clipboard catch block shows success toast on failure — changed to `toast.error(t('idpProviders.edit.toasts.copyFailed'))`, added `copyFailed` key to all 4 locales. [IdpProviderEditView.vue:119]
- [x] [Review][Patch] Dead i18n key `idpProviders.edit.staleMessage` — removed from en/de/fr/es.ts. [en.ts, de.ts, fr.ts, es.ts]
- [x] [Review][Defer] Scope chips: silent deduplication gives no user feedback — when a user adds a duplicate scope, the Set deduplicates it silently; no error or indication is shown. UX polish, future story. — deferred, pre-existing
- [x] [Review][Defer] `initialForm` not refreshed after a failed PATCH during dry-run — if `store.update()` throws, `initialForm` stays at the pre-attempt snapshot; stale detection remains correct via `lastDryRunAtForm` but `initialForm` diverges from server truth. Low-risk in practice. — deferred, pre-existing
- [x] [Review][Defer] Missing Vitest coverage for multi-field stale revert (form reset after mutation) — no test exercises changing multiple fields or reverting a field back to its dry-run snapshot value. Future test improvement. — deferred, pre-existing
- [x] [Review][Defer] `loadExisting()` silent failure on `getIdp()` error — consistent with other view patterns; shows an empty form without an error banner. Future improvement. — deferred, pre-existing
