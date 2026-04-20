---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
status: 'complete'
completedAt: '2026-04-15'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/project-context.md
  - CLAUDE.md
workflowType: 'epics-and-stories'
project_name: 'roboscope'
scope: 'phase-4-auth-sso-teams'
---

# roboscope — Epic Breakdown (Phase 4: Auth / SSO + Teams)

## Overview

This document provides the complete epic and story breakdown for **RoboScope Phase 4** (OAuth2/OIDC SSO + Teams/Org Model), decomposing the requirements from the PRD, UX Design Specification, and Architecture document into implementable stories.

Scope boundary: this breakdown covers Phase 4 v1 only. SAML (Phase 4.5), SCIM (Phase 5), silent token renewal, per-user local-login override, and multi-team-per-repo are explicit non-goals and do not receive stories here.

## Requirements Inventory

### Functional Requirements (from PRD)

**Identity Provider Configuration:**

- FR1: An Admin can create, view, update, and delete OIDC identity-provider configurations for at least Azure AD, Google, and GitHub.
- FR2: An Admin can store an identity provider's client secret encrypted at rest; secret is never returned in any API response.
- FR3: An Admin can validate an identity-provider configuration via a dry-run that checks issuer reachability and key-material availability, without committing the configuration.
- FR4: An Admin cannot enable an identity-provider configuration until its dry-run has succeeded at least once.
- FR5: An Admin can download a localized handoff artifact (PDF + markdown) containing the information needed by the customer-org's IdP admin.
- FR6: The system caches identity-provider discovery metadata per-IdP and refreshes it on a schedule; no outbound network call is required at application boot.

**SSO Authentication (end-user):**

- FR7: An unauthenticated user can initiate sign-in with any enabled identity provider from the login page.
- FR8: An unauthenticated user can still sign in with a local password as a separate, always-available path, independent of identity-provider state.
- FR9: When single sign-on is configured, the local-password form is visually de-emphasized (not removed) on the login page.
- FR10: An Admin can configure the system to hide the local-password form entirely from the login page while preserving bootstrap-admin access.
- FR11: After successful SSO authentication, the system issues a session credential whose shape is identical to the existing local-login session credential.
- FR12: A user landing on the login page via a deep link to a protected resource is returned to that exact resource after successful authentication.
- FR13: The system validates the post-authentication redirect target against the application's own origin and rejects any redirect to an external URL.

**Teams & Membership:**

- FR14: An Admin can create, rename, and delete Teams.
- FR15: An Admin can assign a repository to at most one Team and can reassign or unassign it later.
- FR16: An Admin can add and remove users as Team members, and can assign each Team member a role from the existing role hierarchy.
- FR17: An Admin can map an identity-provider group claim value to a Team plus role, causing users whose tokens carry that group to gain that Team membership on login.
- FR18: An Admin can bulk-create Teams by importing the list of groups the identity provider returned during its most recent successful dry-run or login.
- FR19: A user's Team membership is synchronized with the groups reported by the identity provider at each login.
- FR20: Team memberships created by IdP-group synchronization are distinguishable from memberships created manually.
- FR21: A user can view the list of Teams they belong to.
- FR22: An Admin or Team member can view the full member roster of any Team they belong to; non-members cannot.

**Access Control & Role Resolution:**

- FR23: The system computes a user's effective role on a given repository as the MAX of the user's global role, the user's Team role on the Team that owns the repository, and the user's direct project-member role.
- FR24: The effective-role rule is the single source of truth for all permission checks on repository-scoped actions.
- FR25: A user with VIEWER effective role can read repository content and reports, and cannot edit or run.
- FR26: A user with RUNNER effective role can additionally execute tests on that repository.
- FR27: A user with EDITOR effective role can additionally modify repository content on that repository.
- FR28: A user with ADMIN role (global or via any layer) retains existing ADMIN capabilities unchanged.
- FR29: A repository not assigned to any Team continues to apply global-role-plus-project-member resolution, identical to pre-Phase-4 behavior.
- FR30: Existing long-lived API tokens continue to authenticate and authorize exactly as before Phase 4; effective role remains capped at the owner's global role at token creation.

**First-Login & Onboarding Experience:**

- FR31: A user signing in via SSO for the first time is presented with a welcome experience that surfaces which Teams they belong to and why.
- FR32: The welcome experience directs the user to a single primary starting point — the most-active repository in their default Team — rather than a dashboard.
- FR33: A user belonging to more than one Team can select and change their default Team from the application header.
- FR34: A user whose Teams contain no repositories is shown a non-dead-end state: a request-access action, and where configured, a read-only demonstration repository.
- FR35: A user opening a read-only view of editable content is shown an explicit read-only indicator that explains why editing is unavailable.
- FR36: A user whose SSO-derived identity matches an existing local-account email is given an explicit consent dialog before the accounts are linked.

**Resilience & Outage Handling:**

- FR37: A user whose session credential is still valid remains authenticated even when the identity provider is unreachable.
- FR38: A user whose SSO sign-in fails because the identity provider is unreachable is shown a localized, non-technical error message that surfaces the administrator's contact address.
- FR39: An Admin can activate a time-bounded emergency bypass that allows local-password sign-in on an installation configured as SSO-only.
- FR40: An emergency bypass automatically deactivates after a configurable expiry, with a system-enforced maximum duration.
- FR41: Exactly one emergency-bypass mechanism exists at installation scope; there is no per-user bypass.

**Deprovisioning & Offboarding:**

- FR42: An Admin can deactivate a user such that the user's existing sessions are rejected on the next request and all of the user's API tokens are revoked.
- FR43: The system retains removed Team-membership records for a configurable retention window before deletion.
- FR44: An Admin can reassign ownership of an API token from a deactivated user to an active user.
- FR45: The system documents and enforces that IdP-group removal does not take effect on an existing RoboScope session until the user's next login.

**Audit & Compliance:**

- FR46: Every identity-provider configuration change, emergency-bypass activation and expiry, Team change, Team-membership change, and API-token reassignment is recorded in the audit log.
- FR47: Every SSO sign-in attempt (successful and failed) that reaches the RoboScope server is recorded in the audit log.
- FR48: The audit log is exportable in the existing formats without modification required by Phase 4.
- FR49: The audit retention scheduler applies to all new Phase 4 audit events using the existing retention configuration.

**Localization:**

- FR50: Every user-facing string introduced by Phase 4 is available in the four supported application languages (EN, DE, FR, ES).

### Non-Functional Requirements (from PRD)

**Performance:**

- NFR1: An interactive SSO sign-in round-trip completes in under 5 seconds on a healthy IdP connection.
- NFR2: The IdP dry-run completes within 10 seconds or returns a specific timeout error identifying the failing phase.
- NFR3: Login-time group-to-Team synchronization adds no more than 500 ms of latency for a user belonging to up to 50 IdP groups.
- NFR4: Existing ~555 backend tests and 217 Playwright tests retain execution time within ±10 % after Phase 4 changes.

**Security:**

- NFR5: OIDC client secrets are Fernet-encrypted at rest, never logged, never returned in API responses.
- NFR6: All OIDC state, nonce, and PKCE verifier values are cryptographically random (≥128 bits entropy), single-use, expire within 10 minutes.
- NFR7: The post-authentication redirect target (`return_to`) is validated against the application's own origin.
- NFR8: OIDC `id_token`s are discarded immediately after claim extraction.
- NFR9: Session credentials issued after SSO carry no identity-provider claims.
- NFR10: Failed SSO authentication attempts are rate-limited per source IP.
- NFR11: Emergency-bypass toggle requires ADMIN role, records activation/expiry in audit, maximum duration 24 hours.
- NFR12: Bootstrap admin access cannot be disabled, deleted, or locked out.
- NFR13: All HTTPS termination uses TLS 1.2 or newer; outbound calls to IdPs require TLS 1.2+.

**Reliability & Operability:**

- NFR14: Identity-provider outage does not invalidate existing session credentials.
- NFR15: Application boot makes zero outbound network calls; discovery is fetched lazily and cached per-IdP for 24 hours.
- NFR16: Discovery-cache refresh is best-effort; failure does not block sign-in.
- NFR17: Phase 4 migrations are forward-and-backward compatible within the milestone.
- NFR18: SQLite (dev) and PostgreSQL (prod) pass the identical Phase 4 test suite with no DB-specific skips.

**Deployability & Environment:**

- NFR19: No new static asset is loaded from external CDN, Google Fonts, or third-party host.
- NFR20: `authlib` is added via `uv` pinned, included in Windows offline-ZIP build.
- NFR21: No new dependency introduces a C-extension requiring `xmlsec` or components incompatible with slim Docker / Windows.
- NFR22: Existing Docker Compose production configuration boots successfully with Phase 4 changes.

**Accessibility:**

- NFR23: All new UI surfaces meet WCAG 2.1 AA for color contrast, keyboard navigability, focus visibility, screen-reader labeling.
- NFR24: Login page fully operable by keyboard with no mouse interaction.
- NFR25: Every new interactive element has a translated `aria-label` in all four supported languages.

**Integration:**

- NFR26: System interoperates with identity providers compliant with OpenID Connect Core 1.0 supporting `authorization_code` flow with PKCE.
- NFR27: Group-claim extraction supports string-array and JSON-path group claims, covering Azure AD (`groups`), Google (Workspace `groups` scope), GitHub (org/team membership via scope).
- NFR28: Existing `rbs_…` API tokens continue to authenticate against all endpoints exactly as before; no CI/CD client requires modification.

**Auditability:**

- NFR29: Every Phase 4 audit event includes structured, machine-parseable detail (event type, actor, target, timestamp, IP, detail JSON) for SIEM ingest.
- NFR30: Phase 4 audit events increase audit-log storage growth by less than 5 % vs existing Phase 2 baseline in normal operation.

### Additional Requirements (from Architecture)

**Data-Model:**

- AR1: New models: `IdentityProvider`, `Team`, `TeamMember`, `IdPGroupMapping`, `OidcLoginAttempt`, `RateLimitCounter`.
- AR2: `Repository.team_id: int | None` FK (nullable, ON DELETE SET NULL).
- AR3: `User.first_login_complete: bool` (default False), `User.is_active` already exists but needs recheck-on-every-request in `get_current_user`.
- AR4: `Settings` extension: `sso_emergency_bypass`, `sso_emergency_bypass_expires_at`, `deprovision_retention_days` (default 90), `admin_contact_email` (default `admin@roboscope.local`).
- AR5: `Team` and `TeamMember` carry `external_id: str | None` reserved for future SCIM (not exposed in v1).
- AR6: `TeamMember.source` enum: `manual` / `idp_group_sync`.

**Auth-Flow:**

- AR7: OIDC library: `authlib`, pinned via `uv add`, must build on Windows offline-ZIP.
- AR8: Authorization Code Flow with mandatory PKCE; state/nonce/pkce_verifier stored in `OidcLoginAttempt` with 10-min TTL, single-use (row deleted on callback).
- AR9: One shared callback URL `GET /auth/sso/callback` — IdP identified via `state` lookup.
- AR10: JWT shape unchanged from Phase 3; id_token discarded after claim extraction.
- AR11: `effective_role()` in `src/auth/permissions.py` uses MAX semantics; additive (Grant-only), no Deny.
- AR12: Step-by-step migration from `require_role` to `require_effective_role` across all repo-scoped endpoints (per-endpoint sub-stories, documented exceptions in `project-context.md`).
- AR13: `get_current_user` performs `User.is_active` re-check on every request.
- AR14: Client secret Fernet-encrypted via existing `is_secret=True` pattern in `src/encryption.py`.
- AR15: Rate-limiting via DB-counter (not `slowapi`), cleanup via APScheduler hourly.

**Infrastructure:**

- AR16: APScheduler-Jobs (piggyback 24 h scheduler): IdP-discovery-cache refresh, Emergency-Bypass auto-expire, `OidcLoginAttempt` TTL cleanup, `TeamMember` retention cleanup (90 d), Rate-Limit-Counter cleanup (hourly).
- AR17: Nginx config update: TLS 1.2+ minimum; conservative cipher-suite profile; CSP header for login page (`default-src 'self'; frame-ancestors 'none'`).
- AR18: New environment variables: `SSO_EMERGENCY_BYPASS_MAX_HOURS` (default 24), `DEPROVISION_RETENTION_DAYS` (default 90).

**Testing:**

- AR19: Mock-OIDC fixture in `backend/tests/fixtures/mock_oidc.py` using `respx` (mocks `httpx`-transport of `authlib`).
- AR20: Target test surface: ~35 new pytest tests + ~7 new Playwright specs.
- AR21: New CI gates: (a) Prod-Frontend-Build-Test (vue-i18n escape regression), (b) Offline-Boot-Network-Isolation smoke test, (c) Windows offline-ZIP build, (d) Mock-OIDC integration tests.

**PDF/Handoff:**

- AR22: Handoff artifact generated via `reportlab` (pure Python, no C-deps). Markdown + PDF output. Localized in 4 locales.

**Non-Goals (explicit):**

- AR23: SAML 2.0 (Phase 4.5) — `xmlsec` incompatibility with `uv`/Windows/slim Docker.
- AR24: SCIM 2.0 (Phase 5) — schema-forward-compat via `external_id` fields only.
- AR25: Silent token renewal via iframe or refresh tokens — deleted from scope.
- AR26: Per-user local-login override — deleted from scope.
- AR27: Multi-team-per-repository — one team per repo in v1.
- AR28: Real-time deprovisioning / webhook-driven IdP-group sync — login-time sync only.

### UX Design Requirements (from UX Design Specification)

**Views (new or modified):**

- UX-DR1: `LoginView.vue` — extend with SSO-provider buttons (primary) + "Sign in with password" toggle; existing dev-credential prefill preserved.
- UX-DR2: `FirstLoginView.vue` — new 3-section welcome card (`/welcome` route): Your Teams / Start Here / Tour; max-width 480 px; hierarchy 1 > 2 >> 3.
- UX-DR3: `SsoErrorView.vue` — new view for IdP-outage, `.error-card--outage`, `admin_contact_email` prominent, localized in 4 locales.
- UX-DR4: `IdpProviderListView.vue` — new admin list view with status badges (Enabled/Draft/Disabled), search + status filter.
- UX-DR5: `IdpProviderEditView.vue` — new dedicated edit view (not modal) with 2-column form + inline `DryRunPanel`.
- UX-DR6: `TeamListView.vue` — new list view with 2-CTA empty state ("Create first Team" + "Import from IdP groups").
- UX-DR7: `TeamDetailView.vue` — new detail view with 3 tabs (Members / Group Mappings / Repositories).

**Components (new):**

- UX-DR8: `DryRunPanel.vue` — structured verification report with sequential ✅/⚠️/❌ rows, inline placement (not modal, not toast), states: Empty/Loading/Complete-All-Green/With-Warnings/With-Failures/Stale.
- UX-DR9: `TeamSwitcher.vue` — header chip-style dropdown; single-team = static label; multi-team = dropdown with role badges; `aria-*` for keyboard navigation.
- UX-DR10: `WelcomeCard.vue` — 3-section component with prose-ton, conditional section rendering based on teams.length and tour_completed.
- UX-DR11: `IdpProviderForm.vue` — embedded in IdpProviderEditView, client_secret visibility-toggle, Save disabled until dry-run green.
- UX-DR12: `GroupMappingRow.vue` — row component with Display/Edit-Role modes, Enter/Escape keyboard.

**Composables (new):**

- UX-DR13: `useCanEdit(repoId)` — returns `{ canEdit, canRun, role, readOnlyReason }` from `authStore.effective_roles_by_repo`.
- UX-DR14: `useSsoProviders()` — returns `{ providers, loading, error, refresh }`, cached in Pinia store `sso.ts`.

**Utility classes & styles (new):**

- UX-DR15: `.sso-provider-button` scoped style for SSO login buttons.
- UX-DR16: `.welcome-card` variant of `.login-card` with Amber left-border accent.
- UX-DR17: `.read-only-banner` utility class with variants `--viewer`, `--role-changed`, `--team-removed`; `position: sticky; top: 0;`.
- UX-DR18: `.error-card--outage` variant for SSO-outage screens.
- UX-DR19: `.bypass-banner` for emergency-bypass-active header indicator with Amber background and countdown.
- UX-DR20: `.skip-link` for keyboard-navigation accessibility (shown only on focus).

**Assets (new):**

- UX-DR21: SSO-provider SVG icons (Azure AD, Google, GitHub) — inline, offline-bundled, monochrome or brand-consistent.

**Accessibility deliverables:**

- UX-DR22: Color-contrast fix: `--color-accent` `#D4883E` restricted to Large Text / Icons / Badges / Borders; for Body text on white use `--color-accent-dark` `#A66A2E`.
- UX-DR23: `@axe-core/playwright` integrated into existing Playwright test suite; one axe-check per new view as acceptance gate.
- UX-DR24: Manual screenreader smoke test (VoiceOver + NVDA) as release-gate checklist item (not CI).
- UX-DR25: All Icon-only buttons have `aria-label` + visible Tooltip; localized in 4 locales (NFR25).
- UX-DR26: `role="alert"` + `aria-live="assertive"` on login-errors and dry-run-failures; `aria-live="polite"` on dry-run-progress updates.
- UX-DR27: Focus management: after Route-change, focus lands on new View's `<h1>`.
- UX-DR28: `prefers-reduced-motion` respected — transitions become instant.

**Copy & i18n:**

- UX-DR29: Welcome-Card microcopy locked in EN/DE/FR/ES in Sprint 1 before implementation: statement + labeled metadata line structure (not embedded participle-clause); dynamic values (group name, repo name, email) rendered via `<i18n-t>` slots, not inside `$t()` templates.
- UX-DR30: Outage-error copy localized in 4 locales: "We couldn't reach your identity provider. Try again in a few minutes. If this keeps happening, contact your admin: {admin_contact_email}".
- UX-DR31: Read-Only banner copy localized: "You have read-only access on this repository."
- UX-DR32: Handoff-artifact markdown + PDF localized in 4 locales.
- UX-DR33: Glossary: 12 locked terms (IdP, OIDC, SSO, Claim, Issuer URL, Redirect URI, Discovery URL, Team, Project/Repository, Role inheritance, Break-glass/Notfallzugang, Group mapping) in all 4 locales; used consistently in in-app docs.

**Responsive & Patterns:**

- UX-DR34: 9 empty/error states designed per PRD Journey Requirements Summary (Zero-Teams, Multi-Team-no-default, 4 dry-run error states, Team-empty, Group-mapping-empty, Existing-user-link-consent, Bookmark-expired, VIEWER-flow-editor, IdP-outage). Each: icon/illustration + explanation + CTA.
- UX-DR35: Loading-state thresholds: <100 ms no indicator, 100–500 ms button spinner, 500 ms–3 s skeleton, >3 s skeleton + progress narration, >10 s skeleton + abort-CTA.
- UX-DR36: Feedback hierarchy: Toast for transient unkritisch (3 s), Toast + persistent indicator for kritisch (8 s), inline for form validation, `DryRunPanel` for verifications.
- UX-DR37: Button hierarchy: primary (max 1 per section), secondary (ghost), tertiary (text-link), destructive (always in confirm-modal-footer), disabled-with-explanation (never hidden).
- UX-DR38: First-Login-Landing triggers `driver.js`-tour (existing `.roboscope-tour-popover` styling) when `tour_completed=false`, skipped otherwise.
- UX-DR39: Responsive breakpoints (1024 px / 768 px) applied to all Phase-4 views per Responsive-Matrix table in UX-Spec.

**Header & Navigation:**

- UX-DR40: Header-Right-layout: `[TeamSwitcher] [EmergencyBypass-Indicator if active] [NotificationBell] [UserMenu]`.
- UX-DR41: Admin-Sub-Navigation extended: Identity Providers / Teams / Emergency Bypass / Audit Retention (existing) — horizontal tabs in SettingsView.

### FR Coverage Map

| FR | Epic | Kurzbeschreibung |
|---|---|---|
| FR1 | Epic 1 | IdP-CRUD (Azure AD, Google, GitHub) |
| FR2 | Epic 1 | Client-Secret Fernet-encrypted, never returned |
| FR3 | Epic 1 | Dry-Run: issuer + JWKS probe |
| FR4 | Epic 1 | Save gated by successful dry-run |
| FR5 | Epic 1 | Handoff artifact (PDF + Markdown, localized) |
| FR6 | Epic 1 | Discovery metadata cached per-IdP, lazy refresh |
| FR7 | Epic 2 | SSO sign-in from login page |
| FR8 | Epic 2 | Local-password path always available |
| FR9 | Epic 2 | Password form de-emphasized when SSO configured |
| FR10 | Epic 2 | Admin can hide password form (bootstrap-admin preserved) |
| FR11 | Epic 2 | Session credential shape unchanged post-SSO |
| FR12 | Epic 2 | Deep-link preserved through auth redirect |
| FR13 | Epic 1 | `return_to` origin validation |
| FR14 | Epic 3 | Team CRUD |
| FR15 | Epic 3 | Repository-to-Team assignment (one team per repo) |
| FR16 | Epic 3 | Manual Team membership CRUD + role assignment |
| FR17 | Epic 3 | IdP group-to-Team mapping |
| FR18 | Epic 3 | Bulk-create Teams via Import-from-IdP-groups |
| FR19 | Epic 3 | Login-time group sync |
| FR20 | Epic 3 | `source` discriminator (manual vs idp_group_sync) |
| FR21 | Epic 3 | User sees own Team list |
| FR22 | Epic 3 | Team-member roster visible to members/admin |
| FR23 | Epic 3 | `effective_role = MAX(global, team, project)` |
| FR24 | Epic 3 | Effective-role rule is SSOT |
| FR25 | Epic 3 | VIEWER semantics |
| FR26 | Epic 3 | RUNNER semantics |
| FR27 | Epic 3 | EDITOR semantics |
| FR28 | Epic 3 | ADMIN semantics unchanged |
| FR29 | Epic 3 | Repo without Team falls back to pre-Phase-4 resolution |
| FR30 | Epic 3 | API-Token role capped at User.role global |
| FR31 | Epic 4 | First-Login welcome with "Why you have access" |
| FR32 | Epic 4 | Welcome primary-CTA is one most-active repo |
| FR33 | Epic 4 | Team-Switcher for multi-team users |
| FR34 | Epic 4 | Zero-Teams / Zero-Repos non-dead-end state |
| FR35 | Epic 4 | Read-Only indicator in editor for VIEWER |
| FR36 | Epic 4 | Existing-local-account link-consent dialog |
| FR37 | Epic 2 | Existing sessions survive IdP outage |
| FR38 | Epic 2 | Localized non-technical outage error with admin contact |
| FR39 | Epic 5 | Time-bounded emergency-bypass toggle |
| FR40 | Epic 5 | Bypass auto-deactivates at expiry |
| FR41 | Epic 5 | Single installation-scope bypass (no per-user) |
| FR42 | Epic 5 | Admin deactivates user → sessions/tokens revoked |
| FR43 | Epic 5 | Removed Team-memberships retained for window |
| FR44 | Epic 5 | API-Token reassignment for offboarding |
| FR45 | Epic 5 | IdP-group removal applies at next login (documented) |
| FR46 | Epic 5 | Phase-4 events captured in AuditLog |
| FR47 | Epic 5 | SSO attempts (ok/fail) captured |
| FR48 | Epic 5 | AuditLog export works unchanged |
| FR49 | Epic 5 | Retention scheduler applies to new events |
| FR50 | Epic 5 | 4-locale coverage (EN/DE/FR/ES) |

**Coverage-Vollständigkeit:** 50/50 FRs zu Epics gemappt.

## Epic List

### Epic 1: Enterprise Identity Foundation

**Goal:** Admin konfiguriert OIDC-IdPs mit vollständiger Verifikation, sodass Enterprise-Deployments ohne Procurement-Ausnahme freigegeben werden können.

**User Outcome:**
- Sarah (RoboScope-Admin) kann OIDC-Konfigurationen für Azure AD / Google / GitHub anlegen, per Dry-Run verifizieren und enablen.
- Sarah kann ein Handoff-Artefakt an Ingrid (customer-org IdP admin) übergeben.
- TLS-1.2+-Enforcement und Offline-First-Boot-Invariante sind gewahrt.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR13

### Epic 2: SSO User Access

**Goal:** End-User melden sich via SSO an, behalten stabile Sessions und sehen nicht-technische Fehler bei IdP-Problemen.

**User Outcome:**
- Maya klickt "Sign in with Azure AD", bekommt eine Session in unter 5 Sekunden.
- Lokale Password-Login bleibt als separater, immer-verfügbarer Pfad.
- Bei IdP-Ausfall behalten bestehende Sessions Gültigkeit; neue Logins zeigen lokalisierte, nicht-technische Fehlermeldung mit Admin-Kontakt.
- Existierende CI/CD-API-Tokens funktionieren unverändert.

**FRs covered:** FR7, FR8, FR9, FR10, FR11, FR12, FR37, FR38

### Epic 3: Teams & Role Resolution

**Goal:** QA Leads und Admins organisieren User und Repos in Teams; das System berechnet effektive Rollen konsistent über 3 Layer.

**User Outcome:**
- Anita (QA Lead) erstellt Teams via "Import from IdP groups", weist Repos zu, managed Memberships täglich ohne Tickets.
- HR-Deaktivierungen in Azure AD propagieren automatisch beim nächsten Login.
- Permission-Checks auf allen Repo-scoped Endpoints nutzen `effective_role(user, repo) = MAX(global, team, project)`.
- VIEWER/RUNNER/EDITOR/ADMIN-Rollen verhalten sich konsistent in UI und API.

**FRs covered:** FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR29, FR30

### Epic 4: First-Login & Inclusion Experience

**Goal:** Neue User (insbesondere non-technische) landen in einer selbsterklärenden Welcome-Experience, die Zugang begründet und zum ersten sinnvollen Klick führt.

**User Outcome:**
- Maya sieht nach SSO-Callback eine 3-Card-Welcome mit "Why you have access"-Microcopy, primärem Open-Repo-CTA und optionaler 60-Sekunden-Tour.
- VIEWER-User im FlowEditor sehen expliziten Read-Only-Banner mit Erklärung.
- Multi-Team-User haben einen Team-Switcher im Header.
- User ohne Teams oder ohne Repos landen auf nicht-Dead-End-States mit konkreter Next-Action.
- Existing-User-mit-matching-Email-SSO-Login bekommt Link-Consent-Dialog.

**FRs covered:** FR31, FR32, FR33, FR34, FR35, FR36

### Epic 5: Operational Resilience, Offboarding, Compliance & Release Readiness

**Goal:** Admins haben die Werkzeuge für Outages, Offboarding und SIEM-Integration; Release erfüllt alle Enterprise-Procurement-Anforderungen.

**User Outcome:**
- Sarah aktiviert bei extended IdP-Ausfall einen Emergency-Bypass (max 24 h, auto-expire).
- HR-getriebenes Offboarding invalidiert Sessions und API-Tokens; Team-Memberships 90 d aufbewahrt; CI-Tokens an active User reassignable.
- Alle Phase-4-Events landen strukturiert in `AuditLog`, SIEM-tauglich.
- Audit-Export funktioniert ohne Phase-4-Änderungen weiter.
- Prozess-Deliverables: Procurement-Checklist-Response, IdP-Admin-Handoff-Artefakt (EN/DE/FR/ES), 4-Locale-i18n-Abdeckung, Release-Gate-Checklist mit CI-Gates (Offline-Boot, Windows-ZIP, Prod-i18n-Build, Mock-OIDC-Tests).
- Regression-Schutz: ±10 % Testlaufzeit, 0 neue Fehlschläge bei 555 Backend-Tests und 217 Playwright-Tests.
- **Chrome Recorder Extension Boundary dokumentiert:** Release Notes + in-app Docs klären, dass die Extension in Phase 4 unverändert bleibt; Team-Grants erhöhen `effective_role` für User, **nicht** für `ApiToken`-basierte Clients wie den Recorder. Recorder-Users müssen ihre Tokens weiterhin in RoboScope erstellen; Team-scoped API-Tokens sind Phase-5-Kandidat.

**FRs covered:** FR39, FR40, FR41, FR42, FR43, FR44, FR45, FR46, FR47, FR48, FR49, FR50

**Additional deliverable (out-of-band, no FR):** *Chrome Recorder Phase-4 Impact Documentation* — reine Doku-Story, keine Code-Änderung. Begründet den bewussten Nicht-Support der Recorder-Extension in Phase 4 und surface-ed die Team-vs-ApiToken-Semantik-Konsequenz an Endnutzer (Release Notes EN/DE/FR/ES + in-app Docs-Page).

### Epic Dependency Graph

```
Epic 1 (IdP Foundation)
    ↓
Epic 2 (SSO User Access) ← depends on Epic 1
    ↓
Epic 3 (Teams & Role Resolution) ← depends on Epic 2
    ↓
Epic 4 (First-Login Experience) ← depends on Epic 2 + Epic 3
    ↓
Epic 5 (Resilience, Offboarding, Compliance) ← depends on all previous
```

Sequential dependencies. Epic 5 konsolidiert cross-cutting Deliverables (Audit-Events, Release-Gates, i18n-Pass, Recorder-Boundary-Docs), die während aller vorherigen Epics produziert und in Epic 5 verifiziert werden.

## Epic 1: Enterprise Identity Foundation

Admin konfiguriert OIDC-IdPs mit vollständiger Verifikation, sodass Enterprise-Deployments ohne Procurement-Ausnahme freigegeben werden können.

### Story 1.1: Database migration for Phase-4 models

As a Platform engineer,
I want a single Alembic migration to add all Phase-4 tables and columns,
So that the database schema is ready for Phase-4 features without partial-deploy states.

**Acceptance Criteria:**

**Given** the database is at the pre-Phase-4 Alembic revision
**When** `make db-upgrade` is executed
**Then** the following new tables exist: `identity_providers`, `teams`, `team_members`, `idp_group_mappings`, `oidc_login_attempts`, `rate_limit_counters`
**And** `repositories` has a new nullable `team_id` column (FK to `teams(id)`, `ON DELETE SET NULL`)
**And** `users` has a new `first_login_complete` boolean column (default `false`)
**And** `settings` has new columns `sso_emergency_bypass` (bool), `sso_emergency_bypass_expires_at` (datetime nullable), `deprovision_retention_days` (int default 90), `admin_contact_email` (string default `admin@roboscope.local`)
**And** `teams`/`team_members` have nullable `external_id` columns reserved for future SCIM

**Given** the database is at the Phase-4 Alembic revision
**When** `make db-downgrade` is executed
**Then** all new tables are dropped and added columns removed without error
**And** existing `users`, `api_tokens`, `repositories`, `audit_logs` data is preserved unchanged

**Given** the Phase-4 migration is applied
**When** existing pytest suite runs
**Then** all ~555 backend tests remain green on both SQLite and PostgreSQL

### Story 1.2: Mock OIDC test fixture

As a Backend engineer,
I want a shared `respx`-based mock OIDC provider fixture,
So that SSO-related tests run in CI without depending on live IdP endpoints.

**Acceptance Criteria:**

**Given** a pytest test imports the `mock_oidc` fixture from `backend/tests/fixtures/mock_oidc.py`
**When** the fixture is activated
**Then** HTTP calls to `{issuer}/.well-known/openid-configuration`, `{issuer}/jwks`, and `{issuer}/token` return deterministic stub responses
**And** the fixture supports injection of custom claims (groups, email, sub) per test

**Given** a test requests a token exchange via authlib
**When** the mock fixture is active
**Then** the token exchange succeeds with a valid id_token signed by the fixture's test key
**And** the test can assert on the extracted claims

**Given** CI runs with the network-isolation smoke test enabled
**When** the fixture is used in any test
**Then** no outbound network call is attempted

### Story 1.3: Identity-Provider CRUD API

As a RoboScope admin,
I want to create, view, update, and delete OIDC identity-provider configurations via API,
So that I can configure the system to accept SSO from Azure AD, Google, or GitHub.

**Acceptance Criteria:**

**Given** I have the ADMIN role
**When** I POST to `/api/v1/auth/idp-providers` with a valid IdP config (name, type, issuer_url, client_id, client_secret, scopes, group_claim_name)
**Then** a new IdentityProvider record is created with `is_enabled=false` (draft state)
**And** the response contains the new IdP's id and all fields *except* `client_secret`
**And** an `idp.created` audit event is written

**Given** I have an existing IdP
**When** I GET `/api/v1/auth/idp-providers/{id}` or list via `/api/v1/auth/idp-providers`
**Then** the response never contains `client_secret` in plaintext or encrypted form

**Given** I have the ADMIN role
**When** I PUT or DELETE an IdP
**Then** the change is applied and an `idp.updated` / `idp.deleted` audit event is written

**Given** I have a role less than ADMIN
**When** I attempt any CRUD operation on `/api/v1/auth/idp-providers`
**Then** the response is 403 Forbidden

### Story 1.4: Dry-run probe endpoint

As a RoboScope admin,
I want to validate an IdP configuration via a dry-run probe before saving,
So that I know the configuration works before committing it.

**Acceptance Criteria:**

**Given** I have the ADMIN role and a draft IdP configuration
**When** I POST to `/api/v1/auth/idp-providers/{id}/dry-run`
**Then** the backend fetches the `/.well-known/openid-configuration`, validates it contains `authorization_endpoint`, `token_endpoint`, `jwks_uri`, and fetches the JWKS
**And** the response returns a structured report with rows: `issuer_reachable`, `discovery_valid`, `jwks_fetched`, each with status `passed`/`warning`/`failed` and detail message
**And** the entire probe completes within 10 seconds or returns a specific timeout error naming the failing phase

**Given** the issuer URL is unreachable
**When** I run dry-run
**Then** the response includes `issuer_reachable: failed` with error code `idp.unreachable` and copy "Can RoboScope reach `{issuer_url}`? Check firewall/egress."

**Given** I have a role less than ADMIN
**When** I attempt to run dry-run
**Then** the response is 403 Forbidden

**Given** a dry-run has completed with all rows passed
**Then** the IdP configuration is eligible to be enabled (see Story 1.7)

### Story 1.5: Encrypted client-secret storage

As a Security engineer,
I want OIDC client secrets stored encrypted at rest using Fernet via the existing `is_secret=True` pattern,
So that a database dump does not expose plaintext IdP credentials.

**Acceptance Criteria:**

**Given** I create or update an IdP configuration with a `client_secret`
**When** the record is persisted
**Then** the `identity_providers.client_secret_encrypted` column contains the Fernet-encrypted value (binary/LargeBinary)
**And** the plaintext value is never written to the database, any log file, or any API response

**Given** the backend needs to perform a token exchange
**When** it loads the IdP configuration
**Then** the client_secret is decrypted in-memory via `src/encryption.py`
**And** the plaintext is used only for the outbound HTTPS request, never logged

**Given** `SECRET_KEY` is rotated (operator-initiated)
**When** an IdP is read from the DB
**Then** the existing legacy-plaintext graceful-decrypt fallback is preserved (consistent with Phase-2 secret handling)

### Story 1.6: Admin UI — IdP Provider list view

As a RoboScope admin,
I want to see all configured identity providers in a list view,
So that I can get an overview and navigate to edit/run-dry-run/delete actions.

**Acceptance Criteria:**

**Given** I have the ADMIN role and navigate to `/admin/identity-providers`
**When** no IdPs exist yet
**Then** I see an empty-state with illustration, explanation "Add your first identity provider to enable SSO", and CTA `[+ New Provider]`

**Given** one or more IdPs exist
**When** I view the list
**Then** I see a `.data-table` with columns: Name, Type, Status (badge: Enabled / Draft / Disabled), Last dry-run
**And** each row has actions: View/Edit, Run dry-run, Delete
**And** a header action `[+ New Provider]` is visible

**Given** I am a non-admin user
**When** I attempt to access `/admin/identity-providers`
**Then** I am redirected and the navigation item is not visible

**Given** the view is rendered
**When** I run `@axe-core/playwright` against it
**Then** no WCAG 2.1 AA violations are reported

### Story 1.7: Admin UI — IdP Provider edit view with inline DryRunPanel

As a RoboScope admin,
I want to edit an IdP configuration with inline dry-run verification before save,
So that I never commit a broken configuration.

**Acceptance Criteria:**

**Given** I am editing an IdP config
**When** the view renders
**Then** I see a 2-column form (Desktop) with fields: display_name, provider_type (select), issuer_url, client_id, client_secret (visibility-toggle), scopes (tags), group_claim_name, redirect_uri (readonly copy-to-clipboard)
**And** the `[Save]` button is disabled with tooltip "Run dry-run first to enable Save"

**Given** I click `[Run dry-run]`
**When** the probe executes
**Then** the inline `DryRunPanel.vue` component renders below the form (not modal, not toast) and shows sequential rows with ✅/⚠️/❌ icons, `aria-live="polite"` announces progress to screen readers

**Given** all dry-run rows are ✅
**When** the panel settles
**Then** the `[Save]` button becomes enabled

**Given** the form is modified after a successful dry-run
**When** any field changes
**Then** the DryRunPanel enters `Stale` state ("Config changed — re-run required") and Save disables again

**Given** I am on Tablet (768–1023 px)
**When** the view renders
**Then** form collapses to single column and DryRunPanel renders below form

**Given** all new strings render
**Then** EN/DE/FR/ES translation entries exist and the vue-i18n prod-build test passes

### Story 1.8: Handoff artifact generator (reportlab)

As a RoboScope admin,
I want to download a localized handoff artifact (Markdown + PDF) for the customer-org IdP admin,
So that I can delegate the IdP-side configuration without a written instruction round-trip.

**Acceptance Criteria:**

**Given** I am viewing an IdP configuration
**When** I click `[Download handoff artifact]`
**Then** the backend generates a PDF (via `reportlab`) and a Markdown file containing: callback URL, required redirect URIs, required OIDC scopes, the configured group_claim_name, recommended IdP group naming conventions, and a test-login procedure
**And** the content is rendered in the current application locale (EN/DE/FR/ES)

**Given** the PDF generation
**When** packaged
**Then** no C-extension dependency is introduced (reportlab is pure Python, verified via `uv tree`)

**Given** the handoff PDF is opened in a standard PDF viewer
**Then** all text is selectable (not rasterized), dynamic values (callback URL) are accurate, and a Mermaid OIDC-flow diagram is embedded as SVG or pre-rendered PNG

### Story 1.9: Discovery-cache refresh APScheduler job

As a Platform engineer,
I want IdP discovery metadata cached in DB for 24 hours and refreshed lazily via APScheduler,
So that the application boots with zero outbound calls and tolerates transient IdP unreachability.

**Acceptance Criteria:**

**Given** the application starts up
**When** the boot sequence completes
**Then** no outbound HTTP request is made to any IdP endpoint (validated by CI network-isolation smoke test)

**Given** an admin has configured an enabled IdP
**When** 24 hours pass since `discovery_cached_at`
**Then** an APScheduler job refreshes the cache in the background, updating `discovery_cache_json` and `discovery_cached_at`

**Given** the cache refresh fails (IdP unreachable)
**When** a user attempts to log in
**Then** the existing cached metadata is used with an admin-UI warning "Cache expired, last fetched X ago" using `--color-accent` badge

**Given** the cache has never been populated and a user attempts login
**When** the OIDC flow is initiated
**Then** the cache is populated lazily (first-use) before the redirect to IdP

### Story 1.10: TLS 1.2+ Nginx config + CSP header + return_to origin validation

As a Security engineer,
I want the shipping Nginx config to enforce TLS 1.2+ and set a strict CSP for the login page, plus backend return_to validation against the app's own origin,
So that Phase 4 does not introduce common auth-flow vulnerabilities.

**Acceptance Criteria:**

**Given** the shipped `docker/nginx.conf` is loaded
**When** a TLS 1.0 or 1.1 client attempts a handshake
**Then** the connection is refused

**Given** the login page is served
**When** the response is inspected
**Then** a `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` header is present

**Given** a request is made to `/api/v1/auth/sso/{idp_id}/login` with a `return_to` query parameter
**When** the return_to host does not match the application's own origin
**Then** the backend rejects the request with HTTP 400 and error code `return_to.invalid`

**Given** a request is made with `return_to` matching the app origin (including subpaths and query strings)
**When** the OIDC flow completes
**Then** the final redirect navigates to the exact return_to URL

**Given** the backend HTTP client makes an outbound call to an IdP
**When** the connection is established
**Then** TLS 1.2 or newer is negotiated; attempts at older versions fail at the client

## Epic 2: SSO User Access

End-User melden sich via SSO an, behalten stabile Sessions und sehen nicht-technische Fehler bei IdP-Problemen.

### Story 2.1: OIDC Authorization Code Flow initiation

As a User,
I want to click an SSO button and be redirected to my identity provider with a secure authorization request,
So that I can authenticate with my corporate credentials.

**Acceptance Criteria:**

**Given** an enabled IdP exists
**When** I GET `/api/v1/auth/sso/providers`
**Then** the response lists the IdP display_name and type (not client_secret or issuer_url internals)

**Given** I GET `/api/v1/auth/sso/{idp_id}/login?return_to=/reports/42`
**When** the handler executes
**Then** a new `OidcLoginAttempt` row is inserted with cryptographically random `state`, `nonce`, `pkce_verifier` (≥128 bits entropy each) and a 10-minute TTL
**And** the response is a 302 redirect to the IdP's authorization endpoint with query parameters `client_id`, `redirect_uri`, `scope`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256`

**Given** `return_to` is omitted or invalid
**When** the login is initiated
**Then** `return_to` defaults to `/` (application root)

**Given** the endpoint is called
**Then** no audit log is written (authorization-start is non-auditable pre-user-identity)

### Story 2.2: SSO callback handler with inline group sync

As a User,
I want the post-IdP redirect to complete my login and land me in RoboScope with a valid session and up-to-date team membership,
So that I am immediately usable without a second request.

**Acceptance Criteria:**

**Given** the IdP redirects back to `/api/v1/auth/sso/callback?code=…&state=…`
**When** the handler executes
**Then** it looks up the `OidcLoginAttempt` by `state`, validates it is not expired and not already consumed
**And** it exchanges the code for an id_token via `authlib` (with PKCE verifier)
**And** it validates the id_token signature against the cached JWKS and verifies `nonce` matches

**Given** the id_token is valid
**When** claim extraction runs
**Then** `sub`, `email`, and the configured group claim are extracted; the id_token is immediately discarded after extraction

**Given** claims are extracted
**When** the user is upserted
**Then** the `User` record is created or updated by email; `last_login_at` is set; existing user's role is preserved

**Given** the IdP returned a group claim array
**When** inline sync runs in the same transaction
**Then** `TeamMember` rows with `source='idp_group_sync'` for this user are diffed against the IdP-reported groups via `IdPGroupMapping`; new memberships are inserted, stale ones deleted; all changes commit before JWT issuance
**And** the sync adds ≤ 500 ms for a user with up to 50 groups

**Given** the sync and upsert complete successfully
**When** the JWT is issued
**Then** the JWT shape is identical to an existing local-login JWT (same claims, no IdP metadata)
**And** the `OidcLoginAttempt` row is deleted (single-use)
**And** an `sso.login.success` audit event with structured detail is written
**And** the response is a 302 redirect to the attempt's stored `return_to`

**Given** any step fails (invalid state, expired attempt, token-exchange error, sync error)
**When** the error path executes
**Then** an `sso.login.failure` audit event is written with the specific reason
**And** the user is redirected to `/sso-error` with a machine-readable error code

### Story 2.3: Frontend LoginView — SSO buttons + password-form toggle

As a User,
I want to see SSO provider buttons prominently on the login page with a less-prominent local-password option,
So that I can choose my login method without confusion.

**Acceptance Criteria:**

**Given** the LoginView is rendered and at least one enabled IdP exists
**When** the view loads
**Then** I see one `[Sign in with {provider_name}]` button per enabled IdP as primary actions with provider icons (Azure AD, Google, GitHub SVG bundled offline)
**And** a less-prominent `[Sign in with password]` toggle below; clicking expands the existing email/password form

**Given** no enabled IdP exists
**When** the view loads
**Then** the local-password form is shown directly (existing behavior preserved, no regression)

**Given** an admin has set `hide_local_login_form=true` AND at least one enabled IdP exists
**When** the view loads
**Then** the password-form toggle is hidden (bootstrap admin can still log in via direct URL path, see Story 2.5)

**Given** I click an SSO provider button
**When** the navigation triggers
**Then** I am redirected to the backend SSO init endpoint with `return_to` set to my current deep-link (if present)

**Given** the page renders
**When** `@axe-core/playwright` runs
**Then** no WCAG 2.1 AA violations are reported; full keyboard navigation works (Tab through all buttons, Enter to activate)
**And** each button has `aria-label` in the current locale

### Story 2.4: Deep-link preservation through SSO redirect

As a User with a bookmarked RoboScope URL,
I want to be returned to the exact bookmarked URL after SSO login,
So that my session expiry never loses my navigation context.

**Acceptance Criteria:**

**Given** I visit `/reports/1234` while unauthenticated
**When** the frontend detects no session
**Then** I am redirected to `/login?return_to=/reports/1234`

**Given** I click an SSO button on that login page
**When** the flow completes
**Then** `return_to` is forwarded through `/auth/sso/{idp_id}/login?return_to=/reports/1234` and persisted in the `OidcLoginAttempt`
**And** after the callback, I land on `/reports/1234`

**Given** my session expires mid-navigation while I have bookmarks open
**When** I click a bookmark
**Then** I am redirected through SSO and return to the bookmarked URL after successful re-auth

**Given** the `return_to` parameter points to an external domain
**When** the backend processes the login request
**Then** a 400 error is returned (validated in Story 1.10); fallback redirect goes to `/`

### Story 2.5: Admin setting — hide password form (SSO-only enforcement)

As a Security admin,
I want to configure the installation so that only SSO login is visible to end-users,
So that password-based access is restricted for compliance reasons while bootstrap admin access is preserved.

**Acceptance Criteria:**

**Given** I have ADMIN role
**When** I PATCH a new admin setting `hide_local_login_form=true`
**Then** the setting is persisted and an audit event is written

**Given** `hide_local_login_form=true` AND at least one enabled IdP exists
**When** an unauthenticated user visits `/login`
**Then** only SSO buttons are rendered; the password-form toggle is absent from the UI

**Given** the bootstrap admin account (`admin@roboscope.local`) exists
**When** the bootstrap admin navigates to `/login?bootstrap=1` (or equivalent dedicated URL)
**Then** the password form is always accessible regardless of `hide_local_login_form` setting

**Given** `hide_local_login_form=true` but no enabled IdP exists
**When** a user visits `/login`
**Then** the password form is shown (fail-safe — we never lock everyone out)

### Story 2.6: Session invariance during IdP outage

As a User with an active session,
I want my existing login session to remain valid even when the IdP is unreachable,
So that a transient outage doesn't force me to re-authenticate unnecessarily.

**Acceptance Criteria:**

**Given** I have a valid JWT session
**When** the IdP becomes unreachable
**Then** my API requests continue to succeed (JWT validation is stateless, no IdP roundtrip per request)

**Given** my JWT is near expiry and the IdP is unreachable
**When** I attempt to refresh by revisiting `/login`
**Then** I see the Sso-error flow (Story 2.7), not a silent failure

**Given** the `get_current_user` dependency is enhanced
**When** it validates a JWT
**Then** it re-checks `User.is_active` on every request; deactivated users are rejected with 401

### Story 2.7: Frontend SsoErrorView with localized outage copy

As a User,
I want to see a non-technical, actionable error message when SSO login fails,
So that I know whether to retry, contact someone, or try something else.

**Acceptance Criteria:**

**Given** the backend redirects me to `/sso-error?code=idp.unreachable`
**When** the SsoErrorView renders
**Then** I see a localized message "We couldn't reach your identity provider. Try again in a few minutes. If this keeps happening, contact your admin: {admin_contact_email}"
**And** the `admin_contact_email` is dynamically populated from backend Settings
**And** a `[Try again]` button re-initiates the SSO flow

**Given** the error code is `return_to.invalid` or `state.expired`
**When** the view renders
**Then** the copy is code-specific (e.g., "Your session timed out, please sign in again") but always user-facing (no OAuth codes)

**Given** the view renders
**When** `@axe-core/playwright` runs
**Then** no WCAG 2.1 AA violations; `role="alert"` + `aria-live="assertive"` announces the error; full keyboard navigation

**Given** the view renders in DE/FR/ES
**When** the locale is switched
**Then** all copy translates cleanly; vue-i18n prod-build test passes

### Story 2.8: Rate-limiting failed SSO attempts (DB counter)

As a Security engineer,
I want failed SSO attempts rate-limited per source IP via a DB counter,
So that credential-stuffing or state-enumeration attacks are mitigated without adding a Redis dependency.

**Acceptance Criteria:**

**Given** the `rate_limit_counters` table exists (per Story 1.1)
**When** an SSO callback fails (invalid state, token exchange error)
**Then** the source IP's counter is incremented with a timestamp

**Given** a source IP exceeds 20 failures in 5 minutes
**When** the next SSO attempt from that IP arrives
**Then** the backend returns HTTP 429 Too Many Requests with `Retry-After` header
**And** an `sso.login.rate_limited` audit event is written

**Given** one hour has passed
**When** the APScheduler counter-cleanup job runs
**Then** counters older than 1 hour are deleted (configurable via `RATE_LIMIT_CLEANUP_HOURS=1`)

**Given** a successful SSO login occurs
**When** the callback completes
**Then** the source IP's failure counter is reset

## Epic 3: Teams & Role Resolution

QA Leads und Admins organisieren User und Repos in Teams; das System berechnet effektive Rollen konsistent über 3 Layer.

### Story 3.1: Team and TeamMember models + CRUD API

As a RoboScope admin,
I want to create, rename, and delete Teams via a backend API,
So that I have the foundational entity for grouping users and repositories.

**Acceptance Criteria:**

**Given** the Phase-4 migration is applied
**When** I POST `/api/v1/teams` with `{name, description?}`
**Then** a Team row is created with an auto-assigned id, `external_id=null`, and an audit event is written

**Given** a Team exists
**When** I PUT `/api/v1/teams/{id}` or DELETE
**Then** the change applies; deleting a team cascades-nullifies `repositories.team_id` (ON DELETE SET NULL) and deletes `team_members`; audit events are written

**Given** I POST `/api/v1/teams/{id}/members` with `{user_id, role}`
**When** the TeamMember is created
**Then** the `source` is set to `manual` and an audit event `team_member.added` is written

**Given** a TeamMember has `source='idp_group_sync'`
**When** an admin attempts to update its role manually
**Then** the update is applied and the `source` is flipped to `manual` to prevent overwrite by next login-sync

**Given** I have a role less than ADMIN
**When** I attempt any Team CRUD
**Then** the response is 403 Forbidden (except GET, which follows user-is-team-member logic)

### Story 3.2: Repository-to-Team assignment

As a RoboScope admin,
I want to assign a repository to a Team,
So that Team members gain the Team's role on that repository.

**Acceptance Criteria:**

**Given** a Team and a Repository exist
**When** I PUT `/api/v1/repos/{repo_id}/team` with `{team_id}`
**Then** `repositories.team_id` is updated and an audit event `repository.team_assigned` is written

**Given** a Repository has `team_id=NULL`
**When** role resolution runs
**Then** the repository falls back to the pre-Phase-4 resolution (global role + project_member role) — verified by dedicated regression test

**Given** I PUT `{team_id: null}` on an assigned repo
**Then** the assignment is removed (team_id becomes NULL) and an audit event `repository.team_unassigned` is written

**Given** a Team is deleted
**When** the cascade runs
**Then** all affected repositories have `team_id` set to NULL (not orphaned)

### Story 3.3: IdP group-to-Team mapping

As a RoboScope admin,
I want to map an IdP group claim value to a Team and role,
So that users with that group membership automatically join the Team on login.

**Acceptance Criteria:**

**Given** an IdP and a Team exist
**When** I POST `/api/v1/teams/{team_id}/group-mappings` with `{idp_id, group_name, role}`
**Then** a `IdPGroupMapping` row is created with unique composite `(idp_id, group_name)`

**Given** a duplicate `(idp_id, group_name)` is submitted
**When** the create attempt runs
**Then** a 409 Conflict is returned

**Given** a GroupMapping exists
**When** I DELETE `/api/v1/group-mappings/{id}`
**Then** the mapping is removed and an audit event `group_mapping.deleted` is written

### Story 3.4: Bulk-create Teams via Import-from-IdP-groups

As a QA Lead,
I want to create multiple Teams at once from a live IdP group list,
So that I never hand-type group names that the IdP already knows.

**Acceptance Criteria:**

**Given** an admin has successfully run a dry-run or at least one user has logged in via an IdP
**When** I GET `/api/v1/auth/idp-providers/{id}/available-groups`
**Then** the response returns the cached group list from the last successful IdP interaction

**Given** I POST `/api/v1/teams/import-from-idp-groups` with `{idp_id, groups: [{group_name, team_name, role}], ...}`
**When** the handler runs
**Then** a Team is created for each entry and a GroupMapping is auto-created linking each IdP group to its Team
**And** the response summary returns `{created: N, skipped: M (already exist), failed: K}`

**Given** I have a role less than ADMIN
**When** I attempt the import
**Then** the response is 403 Forbidden

### Story 3.5: Login-time group sync (inline transactional)

As a User,
I want my Team membership to automatically reflect my IdP groups every time I log in,
So that HR-driven changes in Azure AD propagate without me contacting IT.

**Acceptance Criteria:**

**Given** I log in via SSO and my id_token claims include a groups array
**When** the callback handler processes claims
**Then** inline (same DB transaction as login): the system diffs my current `TeamMember` rows with `source='idp_group_sync'` against the IdP-reported groups, adds new rows, and removes stale ones
**And** the commit happens before JWT issuance (zero stale RBAC on first post-login request)

**Given** the same group claim arrives twice in quick succession (e.g., rapid re-login)
**When** sync runs
**Then** it is idempotent (no duplicate membership rows, no unnecessary writes)

**Given** a TeamMember has `source='manual'`
**When** the sync runs and the user is no longer in the corresponding IdP group
**Then** the row is preserved (manual grants are not overwritten by IdP absence)

**Given** the sync encounters a DB error
**When** the transaction is rolled back
**Then** the JWT is not issued; the user sees an `sso.login.failure` and the callback returns a 500 with audit entry

**Given** a user with 50 IdP groups logs in
**When** the sync runs
**Then** it adds no more than 500 ms latency to the overall login (NFR3)

### Story 3.6: `effective_role()` function + require_effective_role dependency

As a Backend engineer,
I want a single function `effective_role(user, repo) = MAX(global, team, project)` and a FastAPI dependency using it,
So that all repo-scoped permission checks have a single source of truth.

**Acceptance Criteria:**

**Given** `src/auth/permissions.py` is imported
**When** `effective_role(user, repo)` is called
**Then** it returns `max(user.role, team_role_for(user, repo), project_member_role(user, repo))` — purely additive, no deny semantics

**Given** a user is VIEWER globally, EDITOR via Team on repo X, RUNNER via ProjectMember on repo X
**When** `effective_role` is computed
**Then** the result is EDITOR

**Given** a repo has `team_id=NULL`
**When** `effective_role` is computed
**Then** it reduces to `max(user.role, project_member_role)` — identical to pre-Phase-4 behavior (regression-safe)

**Given** a `require_effective_role(min_role)` FastAPI dependency exists alongside existing `require_role`
**When** a route uses it with a `repo_id` path parameter
**Then** it resolves the repo, computes effective_role, and 403s if `< min_role`

**Given** a comprehensive unit test suite in `backend/tests/auth/test_effective_role.py`
**When** the test runs
**Then** every combination of (global, team, project) producing a different outcome is covered; test is table-driven

### Story 3.7–3.11: Step-by-step migration of endpoints from require_role to require_effective_role

As a Backend engineer,
I want to migrate repo-scoped endpoints one domain at a time from `require_role` to `require_effective_role`,
So that regression risk is localized to individual PRs.

*Five parallel sub-stories, each for one domain prefix:*

- **Story 3.7:** Migrate `/repos/*` endpoints
- **Story 3.8:** Migrate `/runs/*` endpoints (resolving repo via run→repo join)
- **Story 3.9:** Migrate `/reports/*` endpoints (resolving repo via report→run→repo join)
- **Story 3.10:** Migrate `/explorer/*` endpoints
- **Story 3.11:** Migrate `/stats/*` endpoints

**Shared Acceptance Criteria (applied per sub-story):**

**Given** a repo-scoped endpoint currently using `require_role`
**When** it is refactored to use `require_effective_role`
**Then** all existing tests continue to pass; pre-Phase-4 behavior for repos with `team_id=NULL` is identical

**Given** a user with Team-granted elevation
**When** they hit the migrated endpoint on a Team-assigned repo
**Then** the elevated role is honored

**Given** the migration PR
**Then** `project-context.md` Cat. 2 is updated to document any grenzfall exception (e.g., endpoints that derive repo_id from a join)

### Story 3.12: Frontend TeamListView

As a QA Lead,
I want a list view of all Teams with a discoverable "Import from IdP groups" entry point,
So that my daily workflow starts from a self-explanatory screen.

**Acceptance Criteria:**

**Given** I have ADMIN role and navigate to `/admin/teams`
**When** no Teams exist
**Then** I see empty-state with two equal-weight CTAs: `[+ New Team]` and `[Import from IdP groups]`

**Given** Teams exist
**When** the list renders
**Then** I see a `.data-table` with columns: Name, Member count, Repository count, Created
**And** row actions: View/Edit, Delete
**And** header actions: `[+ New Team]`, `[Import from IdP groups]`

**Given** search input and member-count-sort are available
**When** I filter or sort
**Then** the table updates client-side (debounce 300 ms for search)

**Given** the view renders
**When** `@axe-core/playwright` runs
**Then** no WCAG 2.1 AA violations

### Story 3.13: Frontend TeamDetailView with tabs

As a QA Lead,
I want a detailed Team view with Members, Group Mappings, and Repositories in tabs,
So that I can manage all facets of a Team without navigating multiple routes.

**Acceptance Criteria:**

**Given** I open a Team detail view
**When** the view loads
**Then** I see three tabs: Members / Group Mappings / Repositories
**And** each tab renders independently with its own empty-state (e.g., "No members yet. [+ Add member]")

**Given** I am on the Members tab
**When** I `[+ Add member]`
**Then** I pick a user via autocomplete, assign a role, and submit; the list updates; `source=manual`

**Given** I am on the Group Mappings tab
**When** I `[+ Add mapping]`
**Then** I pick an IdP from dropdown, pick a group from the live-returned list (not free-text), assign a role

**Given** the view renders
**When** `@axe-core/playwright` runs on each tab
**Then** no WCAG 2.1 AA violations

### Story 3.14: GroupMappingRow component with Display/Edit-Role modes

As a QA Lead,
I want inline role editing on Group Mapping rows,
So that I don't have to navigate to a separate edit page for a role change.

**Acceptance Criteria:**

**Given** a GroupMappingRow is rendered in Display mode
**When** I press Enter or click the role badge
**Then** the row switches to Edit mode with a role dropdown

**Given** I press Enter in Edit mode
**Then** the change submits and the row returns to Display

**Given** I press Escape in Edit mode
**Then** the change is discarded

**Given** the component is keyboard-only operated
**Then** all interactions work without mouse (Tab to row, Enter/Escape, Arrow keys in dropdown)

### Story 3.15: ApiToken role-cap verification (regression test)

As a Security engineer,
I want explicit test coverage that existing `rbs_…` API tokens are capped at the owner's global `User.role` and do NOT honor Team grants,
So that Phase-4's new Team semantics do not accidentally elevate CI/CD token access.

**Acceptance Criteria:**

**Given** User Alice is global VIEWER, Team-EDITOR on repo X
**And** Alice has an API token with `role=VIEWER`
**When** the token is used on any repo X endpoint
**Then** the effective permission is VIEWER (not EDITOR)

**Given** a regression test exists in `backend/tests/auth/test_api_token_cap.py`
**When** the suite runs
**Then** multiple role-cap cases are verified; failure breaks the build

**Given** documentation exists
**Then** `project-context.md` Cat. 2 and PRD Section 11 (Non-Goals) explicitly state the API-token-cap decision

## Epic 4: First-Login & Inclusion Experience

Neue User (insbesondere non-technische) landen in einer selbsterklärenden Welcome-Experience, die Zugang begründet und zum ersten sinnvollen Klick führt.

### Story 4.1: `/auth/me` extension with effective_roles_by_repo + first_login_complete

As a Frontend engineer,
I want `/auth/me` to return the user's Teams, default team, effective_roles_by_repo, and first_login_complete flag,
So that the frontend has a single canonical source for session state.

**Acceptance Criteria:**

**Given** I am authenticated
**When** I GET `/api/v1/auth/me`
**Then** the response includes `teams: Team[]`, `default_team_id: int | null`, `effective_roles_by_repo: {[repo_id]: Role}`, `first_login_complete: bool`, plus all existing fields
**And** the field is always present even when empty (`teams: []`, `effective_roles_by_repo: {}`)

**Given** I PATCH `/api/v1/auth/me/first-login-complete` with `{value: true}`
**Then** the User record is updated and the response returns 200

**Given** the response payload is compared before/after Phase 4
**When** clients expect only old fields
**Then** no existing field is removed or renamed (additive only)

### Story 4.2: Frontend FirstLoginView + WelcomeCard component

As a new User signing in for the first time,
I want a welcome screen that explains my access and points me to one clear next action,
So that I am not dumped into an empty dashboard.

**Acceptance Criteria:**

**Given** I have `first_login_complete=false` and complete SSO
**When** the frontend receives the JWT
**Then** a router guard redirects me to `/welcome`

**Given** I am on `/welcome` with exactly 1 Team that has repositories
**When** the WelcomeCard renders
**Then** I see three sections with hierarchy 1 > 2 >> 3 (no card borders, Amber left-accent on Section 1, Tour section visibly de-emphasized)

**Given** Section 1 renders
**Then** I see "Welcome, {name}." + labeled metadata line "Source: {idp-type} group `{group_name}`" + "This gives you {role} access to {N} repositories." + `[View your team →]`

**Given** Section 2 renders
**Then** I see "Jump into your team's main repository: `{repo_name}`" + metadata "Last run: {relative-time}" + primary `[Open {repo_name} →]` + secondary `[Browse all {N} repos]`

**Given** Section 3 renders AND `tour_completed=false`
**Then** I see "New to RoboScope? [60-second tour of the interface] · [Skip for now]"

**Given** `tour_completed=true`
**Then** Section 3 is not rendered

**Given** the view renders in all 4 locales
**When** vue-i18n prod build runs
**Then** it passes without escape errors; dynamic values (repo name, group name, role) are rendered via `<i18n-t>` slots

**Given** I click `[Open {repo_name} →]`
**Then** optimistic routing navigates immediately with Skeleton file-tree; `first_login_complete=true` is PATCHed

### Story 4.3: "Why you have access" microcopy locked in 4 locales

As a Tech Writer,
I want all Welcome-Card microcopy locked in EN/DE/FR/ES before Sprint 1 implementation ends,
So that late-stage translation does not regress the product build.

**Acceptance Criteria:**

**Given** the translation files `frontend/src/locales/{en,de,fr,es}.json`
**When** they are reviewed at end of Sprint 1
**Then** all Welcome-Card keys are present, proofread by a native-or-fluent speaker of each locale, and pass vue-i18n prod-build test

**Given** the DE translation
**When** it is reviewed
**Then** the copy uses "Willkommen bei RoboScope, {name}." and does NOT embed the IdP-group as a participle-clause (Paige's restructure applied — statement + metadata-line pattern)

**Given** the FR translation
**When** it is reviewed
**Then** gender-neutral phrasing is used (avoiding "ajouté/ajoutée" agreement)

**Given** a repo named `a@b|c{d}` is tested in e2e
**When** the view renders
**Then** the name renders correctly without breaking the vue-i18n build

### Story 4.4: TeamSwitcher component + header integration

As a Multi-Team user,
I want a Team-Switcher chip in the header,
So that I can switch context without navigating through Admin.

**Acceptance Criteria:**

**Given** I am a member of exactly 1 Team
**When** the header renders
**Then** `TeamSwitcher.vue` renders as a static label (no dropdown)

**Given** I am a member of 2+ Teams
**When** the header renders
**Then** the TeamSwitcher renders as a chip-style dropdown showing current team name + role badge; clicking opens a menu

**Given** the menu is open
**When** I navigate with Arrow-Up/Down and press Enter on a team
**Then** the team context switches and the current route refreshes with the new context

**Given** the component renders
**When** `@axe-core/playwright` runs
**Then** `role="button"` + `aria-haspopup="menu"` + `aria-expanded` are correct; keyboard interactions work (Escape closes, Enter selects, Arrows navigate)

### Story 4.5: Zero-Teams and Zero-Repos empty states

As a new User with no Teams or no repos yet,
I want a non-dead-end welcome state with a concrete next action,
So that I am not stuck on a blank screen.

**Acceptance Criteria:**

**Given** I have zero Teams
**When** `/welcome` renders
**Then** Section 1 shows "Welcome. You're signed in, but you haven't been added to a team yet." + `[Request access from {admin_contact_email}]` (mailto prefilled) + optional demo-repo link if configured

**Given** I have Teams but the combined repo count is zero
**When** `/welcome` renders
**Then** Section 2 shows "Your team hasn't added any repositories yet." + `[Message your team lead]` + `[Browse public repos]` if any public repos exist

**Given** I have multiple Teams and no default is set
**When** `/welcome` renders
**Then** Section 1 shows all Teams as chips: "You're in {N} teams. Which one today?" and Section 2 adapts based on selected team
**And** a default-Team preference is persisted after first selection (to user's profile)

### Story 4.6: Read-Only affordances in FlowEditor

As a VIEWER-role user,
I want a clear read-only banner on editable views with explanation of why I can't edit,
So that I don't attempt edits and hit silent 403s.

**Acceptance Criteria:**

**Given** `useCanEdit(repoId)` composable exists
**When** called, it returns `{canEdit, canRun, role, readOnlyReason}` derived from `authStore.effective_roles_by_repo[repoId]`

**Given** my effective role on the open repo is VIEWER
**When** the FlowEditor renders with `:readOnly="true"`
**Then** a sticky `.read-only-banner--viewer` appears at the top: "Read-only — ask an EDITOR to change this [Contact your QA lead]"
**And** all edit controls are disabled-with-tooltip (not hidden)
**And** the Run button is hidden (VIEWER cannot run)

**Given** my effective role is RUNNER
**Then** edit controls remain disabled-with-tooltip; Run button is active

**Given** my effective role is EDITOR or higher
**Then** the banner is not rendered; edit and run are fully active

**Given** a Role-downgrade occurs mid-session (detected from 403 error)
**Then** a persistent `.read-only-banner--role-changed` appears; unsaved changes are preserved in localStorage for 7 days; a mailto link to admin is offered

### Story 4.7: Existing-local-account link-consent dialog

As a User whose email matches both a local account and an SSO identity,
I want an explicit consent dialog before my accounts are linked,
So that I know what is happening and can choose.

**Acceptance Criteria:**

**Given** a local-account user exists with email `maya@acme.com`
**When** Maya signs in via SSO with the same email for the first time
**Then** after OIDC success but before JWT issuance, a consent page is shown: "An account for {email} already exists. Link SSO to this account?" with `[Yes, link]` and `[No, cancel]`

**Given** I click `[Yes, link]`
**Then** the SSO identity is linked; audit event `user.account_linked` is written; JWT is issued and I land in RoboScope

**Given** I click `[No, cancel]`
**Then** the SSO session is discarded; I return to `/login` with a toast "Sign-in cancelled"

### Story 4.8: `@axe-core/playwright` integration + accessibility passes

As a Frontend engineer,
I want `@axe-core/playwright` integrated into the existing Playwright suite with accessibility checks on every new Phase-4 view,
So that WCAG 2.1 AA compliance is enforced as a CI gate.

**Acceptance Criteria:**

**Given** `@axe-core/playwright` is added to `e2e/package.json`
**When** CI runs Playwright tests
**Then** each Phase-4 view has at least one spec calling `injectAxe()` and `checkA11y()` with no serious or critical violations

**Given** a new Phase-4 view introduces a new accessibility violation
**When** the CI runs
**Then** the build fails and the PR cannot merge

**Given** the full suite
**When** Sprint 3 E2E tests run
**Then** at least 7 new Playwright specs exist (per Architecture Story 16), all passing

### Story 4.9: driver.js tour for First-Login

As a new User,
I want an optional 60-second interface tour with contextual tooltips,
So that I can orient myself without being forced into a modal takeover.

**Acceptance Criteria:**

**Given** I am on `/welcome` with `tour_completed=false` and click `[60-second tour]`
**When** the tour starts
**Then** driver.js highlights key UI areas in sequence using existing `.roboscope-tour-popover` styling: sidebar navigation, team switcher, flow-editor area, run button, reports link

**Given** the tour runs
**Then** each step has a localized (EN/DE/FR/ES) title and description; Next/Previous/Close buttons work via mouse and keyboard

**Given** I click "Close" or complete all steps
**Then** `tour_completed=true` is PATCHed to my user; the tour does not auto-show on subsequent welcomes

**Given** I never click the tour link
**Then** nothing forces it (inline offer only, never modal takeover)

## Epic 5: Operational Resilience, Offboarding, Compliance & Release Readiness

Admins haben die Werkzeuge für Outages, Offboarding und SIEM-Integration; Release erfüllt alle Enterprise-Procurement-Anforderungen.

### Story 5.1: Emergency-bypass toggle API + auto-expire

As a Security admin,
I want to activate and auto-expire an installation-wide emergency bypass via API,
So that extended IdP outages don't lock me out of operations.

**Acceptance Criteria:**

**Given** I have ADMIN role
**When** I POST `/api/v1/settings/sso-emergency-bypass` with `{hours: 4}`
**Then** `settings.sso_emergency_bypass=true`, `sso_emergency_bypass_expires_at=now+4h`
**And** an APScheduler one-shot job is registered for expiry
**And** an `sso.emergency_bypass.activated` audit event is written with `{actor_id, duration_hours}`

**Given** `hours > SSO_EMERGENCY_BYPASS_MAX_HOURS` (default 24)
**When** the POST is submitted
**Then** the response is 400 with error "Bypass duration exceeds maximum of 24 hours"

**Given** the bypass is active
**When** the expiry time passes
**Then** the APScheduler job deactivates it; an `sso.emergency_bypass.deactivated` audit event is written

**Given** I DELETE `/api/v1/settings/sso-emergency-bypass`
**Then** the bypass deactivates immediately; audit event written

**Given** a role less than ADMIN attempts any bypass action
**Then** 403 Forbidden

### Story 5.2: Emergency-bypass admin UI + header indicator

As a Security admin,
I want a UI to activate the bypass and a prominent header indicator while it's active,
So that the state is obvious to me and any other admin.

**Acceptance Criteria:**

**Given** I am on the Admin → Emergency Bypass page
**When** the page renders
**Then** I see the current state (active/inactive), remaining time if active, activation history (last N events), and buttons `[Activate (duration dropdown)]` / `[Deactivate]`

**Given** the bypass is active anywhere in the app
**When** any authenticated user views any page
**Then** a persistent `.bypass-banner` appears in the header with Amber background, text "Emergency bypass active — expires in {X}", and a link to the admin view (visible only to admins)

**Given** I am a non-admin user
**When** the bypass is active
**Then** the banner still shows (informational) but the link to admin is absent

**Given** the bypass is active
**When** the LoginView renders
**Then** the local-password form is visually elevated

### Story 5.3: User deactivation propagation

As a Security admin,
I want deactivating a user to immediately invalidate their active sessions and API tokens,
So that offboarding takes effect in near-real-time.

**Acceptance Criteria:**

**Given** a user has active sessions and API tokens
**When** an admin PATCHes `/api/v1/users/{id}` with `{is_active: false}`
**Then** the user's `is_active=false` is persisted
**And** all of that user's `ApiToken` rows have `revoked_at=now()` set in a cascade
**And** audit event `user.deactivated` is written with cascade details

**Given** the deactivated user makes any request with a previously valid JWT
**When** `get_current_user` runs
**Then** the is_active recheck fails and the request returns 401

**Given** the deactivated user's API token is presented
**When** validated
**Then** the token is rejected (revoked)

### Story 5.4: ApiToken reassign endpoint + admin UI

As an Operations admin,
I want to reassign ownership of a shared CI/CD API token from a deactivated user to an active user,
So that production pipelines don't break on personnel changes.

**Acceptance Criteria:**

**Given** I have EDITOR+ role and a token exists owned by a deactivated user
**When** I POST `/api/v1/auth/api-tokens/{token_id}/reassign` with `{user_id}`
**Then** the token's owner is updated; its `role` is re-capped at the new owner's global `User.role` at reassign time
**And** an audit event `api_token.reassigned` is written with {old_user_id, new_user_id}

**Given** the new owner has a lower global role than the token currently has
**Then** the token's role is reduced to the new owner's role (never elevated)

**Given** I am on the admin users page and view a deactivated user's tokens
**When** I click `[Reassign]` on a token
**Then** an inline modal lets me pick an active user; submission applies the reassign

**Given** a role less than EDITOR attempts reassign
**Then** 403 Forbidden

### Story 5.5: Retention cleanup APScheduler jobs

As a Platform engineer,
I want retention-cleanup jobs for removed TeamMembers, OidcLoginAttempts, and RateLimitCounters piggy-backed on the existing APScheduler,
So that Phase-4 tables don't grow unbounded.

**Acceptance Criteria:**

**Given** `deprovision_retention_days=90` in Settings
**When** the daily APScheduler job runs
**Then** TeamMember rows with `deleted_at` older than 90 days (or equivalent tombstone) are hard-deleted

**Given** `OidcLoginAttempt` rows older than 10 minutes exist
**When** the cleanup runs (hourly or more frequent)
**Then** they are deleted

**Given** `RateLimitCounter` rows older than 1 hour exist
**When** the hourly cleanup runs
**Then** they are deleted

**Given** cleanup jobs run
**Then** each emits a structured log entry (no audit event — these are operational, not user-action)

### Story 5.6: AuditEventType enum + structured emission

As a Security analyst,
I want all Phase-4 audit events use a centralized `AuditEventType` enum with structured detail JSON,
So that SIEM ingestion is deterministic.

**Acceptance Criteria:**

**Given** `src/audit/event_types.py` exists
**When** imported, it exports an `AuditEventType` StrEnum with constants for all Phase-4 events: `sso.login.success`, `sso.login.failure`, `sso.login.rate_limited`, `idp.created`, `idp.updated`, `idp.deleted`, `idp.dry_run_executed`, `team.created`, `team.updated`, `team.deleted`, `team_member.added`, `team_member.removed`, `team_member.synced_from_idp`, `group_mapping.added`, `group_mapping.deleted`, `repository.team_assigned`, `repository.team_unassigned`, `api_token.reassigned`, `user.deactivated`, `user.account_linked`, `sso.emergency_bypass.activated`, `sso.emergency_bypass.deactivated`

**Given** every new Phase-4 event is emitted
**When** inspected in AuditLog
**Then** the detail JSON matches the schema: `{actor_user_id, actor_role, source_ip, target_entity_type, target_entity_id, changes: {old: …, new: …} | null, extras: {…}}`

**Given** a legacy event type used in Phase 1–3
**Then** no existing event type name changes (backward compatible)

### Story 5.7: i18n-complete pass for all Phase-4 strings

As a Tech Writer,
I want all Phase-4 user-facing strings reviewed and present in EN/DE/FR/ES at end of Sprint 2,
So that Sprint 3 does not introduce late translation regressions.

**Acceptance Criteria:**

**Given** all Phase-4 translation keys
**When** the review is complete
**Then** EN is the master, DE/FR/ES are reviewed by a native or fluent speaker, and all pass the vue-i18n prod-build test

**Given** dynamic values appear in translations
**When** reviewed
**Then** they are consistently rendered via `<i18n-t>` slots (never inside `$t()` templates) — verified by a test fixture that uses a repo name containing `@|{}`

**Given** Break-glass terminology
**When** DE is reviewed
**Then** "Emergency Bypass" is translated as "Notfallzugang" consistently across all admin UI

### Story 5.8: Procurement checklist response document

As Sales / Security-Review liaison,
I want a ready-to-send procurement checklist response document covering Phase-4 capabilities and non-goals,
So that sales conversations don't stall on questionnaire items.

**Acceptance Criteria:**

**Given** the Release-Gate is reached
**When** the document is produced
**Then** it covers: OIDC support (Azure AD/Google/GitHub), SAML status (deferred), SCIM status (deferred), MFA delegation, audit log capture/export, session timeout configurability, data residency, secret encryption, SSO-only enforcement, offboarding, SBOM, emergency bypass auditability, password storage (bcrypt), transport security (TLS 1.2+)

**Given** the document is finalized
**Then** it is stored in `docs/compliance/procurement-checklist-phase-4.md` and linked from release notes

### Story 5.9: Release-gate CI additions

As a Release engineer,
I want new CI gates enforced for Phase 4,
So that release candidates meet all quality bars automatically.

**Acceptance Criteria:**

**Given** the CI pipeline
**When** a PR is opened
**Then** the following gates run and must pass before merge to main:

1. **Prod-Frontend-Build-Test** — `npm run build` runs; vue-i18n prod-mode passes all locale files without escape errors.
2. **Offline-Boot-Network-Isolation Smoke Test** — A test container boots the backend with egress blocked; the app must start successfully with no outbound network calls (validated via logging or iptables trace).
3. **Windows Offline-ZIP Build** — the `windows-latest` GitHub Actions job succeeds end-to-end; the produced ZIP is artifact-uploaded.
4. **Mock-OIDC Integration Tests** — all Phase-4 SSO-related tests using the `mock_oidc` fixture pass.
5. **`@axe-core/playwright` passes** for all Phase-4 views.
6. **Existing ~555 backend + 217 Playwright tests** remain green (zero regressions).

**Given** any gate fails
**Then** the PR cannot merge

### Story 5.10: Chrome Recorder Phase-4 Impact Documentation

As an existing Chrome Recorder user,
I want to understand what changes (and what doesn't) for me in Phase 4,
So that I'm not confused when my team access expands but my recorder access doesn't.

**Acceptance Criteria:**

**Given** the Phase-4 release notes are published
**Then** they include a dedicated section explaining:
- Chrome Recorder extension is unchanged in Phase 4 (no SSO-aware, no Team-aware features)
- API-token-based auth is preserved (no action required)
- `ApiToken.role` remains capped at the owner's global `User.role` — Team grants do NOT elevate recorder permissions
- To access Team-scoped repos via the recorder, users must either (a) be granted an elevated global role, or (b) wait for Phase 5 Team-scoped API tokens

**Given** the in-app docs
**When** updated
**Then** the `/docs/extensions/chrome-recorder` page has a "Phase 4 Update" callout with the same explanation in all 4 locales

**Given** the PRD Non-Goals section
**Then** the Chrome Recorder entry remains (added in prior PRD update, referenced here)

**Given** a post-GA metric is defined
**Then** support-ticket volume about "recorder can't access Team-scoped repos" is tracked for 30 days to inform Phase-5 priority

### Story 5.11: Non-Goals documentation lock

As a Product Manager,
I want the final PRD Non-Goals section reviewed and frozen at Release-Gate,
So that any Phase 5 proposal references the exact non-goals we deferred.

**Acceptance Criteria:**

**Given** the PRD Non-Goals section
**When** reviewed at Release-Gate
**Then** each non-goal has: rationale, deferred-to version (Phase 4.5 / Phase 5 / Vision / deleted), and trigger condition for reconsideration (e.g., support-ticket volume, design-partner request)

**Given** a Phase 5 kick-off
**Then** the non-goals become the explicit starting-point backlog
