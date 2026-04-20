---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation-skipped', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
completedAt: 2026-04-14
classification:
  projectType: web-application-multi-part
  domain: developer-tooling-test-automation
  complexity: medium-high
  projectContext: brownfield
  scope: phase-4-auth-sso-teams
inputDocuments:
  - _bmad-output/project-context.md
  - _bmad-output/project-docs/index.md
  - _bmad-output/project-docs/project-overview.md
  - _bmad-output/project-docs/source-tree-analysis.md
  - _bmad-output/project-docs/backend-auth-deep-dive.md
  - _bmad-output/project-docs/data-models-backend.md
  - _bmad-output/project-docs/api-contracts-auth.md
  - CLAUDE.md
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 7
workflowType: 'prd'
---

# Product Requirements Document - roboscope

**Author:** Thomas
**Date:** 2026-04-14

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Classification](#project-classification)
3. [Success Criteria](#success-criteria)
4. [Product Scope](#product-scope)
5. [User Journeys](#user-journeys)
6. [Non-User Stakeholder Requirements](#non-user-stakeholder-requirements)
7. [Phase 4 Technical Requirements](#phase-4-technical-requirements)
8. [Project Scoping & Phased Development](#project-scoping--phased-development)
9. [Functional Requirements](#functional-requirements)
10. [Non-Functional Requirements](#non-functional-requirements)
11. [Non-Goals (Explicit)](#non-goals-explicit)
12. [Rollout & Success Metrics](#rollout--success-metrics)
13. [Open Risks & Decisions Needed](#open-risks--decisions-needed)
14. [Glossary](#glossary)
15. [Appendix A: Hypothesis Personas](#appendix-a-hypothesis-personas)

## Executive Summary

RoboScope Phase 4 extends the existing self-hosted Robot Framework test-management platform with enterprise identity (OAuth2/OIDC) and a first-class Teams model, layered on top of the `User` / `ProjectMember` primitives already in place. The work unblocks enterprise adoption — today's username/password-only login is a hard stop for buyers whose security policies require corporate SSO — and, equally important, removes the primary friction keeping non-technical stakeholders out of RoboScope: testers evaluating a move to Robot Framework, and Product Owners/Managers who want to see what's being tested without asking QA for screenshots.

**Target users (who this PRD serves):**
- **Tester not yet on Robot Framework** — logs in via corporate SSO, lands on existing tests and the Phase 3 visual flow editor, and gets value before writing a line of `.robot` syntax.
- **Product Owner / Product Manager** — reads and runs tests in language they understand, via SSO-driven access that IT already provisioned.
- **Platform / Security Admin** — configures the IdP once, maps IdP groups to RoboScope Teams, and delegates repo-level member management away from central IT.
- **QA Lead (secondary)** — manages access at Team scale instead of repo-by-repo.

**Problem:** Enterprise buyers reject RoboScope on SSO grounds; simultaneously, non-technical stakeholders are gated out of a product that already has strong visual/reporting affordances they would benefit from.

**Outcome:** Corporate-account login (Azure AD, Google, GitHub via OIDC), a Team/Org model that inherits roles into projects, and IdP-group → Team mapping so access scales without per-project toil. SAML 2.0 is explicitly deferred to a follow-on story.

### What Makes This Special

Enterprise auth is usually sold as a security gate. In RoboScope, SSO + Teams is a gate *for inclusion* — it delivers the Phase 3 visual-testing experience to the people who most need it (testers, POs) but were previously blocked by a login screen. The differentiator is not the protocol (every tool has OIDC) but the pairing with already-shipped capabilities:

- **Frictionless onboarding into a visually-readable product** — SSO drops a non-technical user directly onto the visual flow editor and human-readable reports, not a YAML/CLI cliff.
- **Offline-first, self-hosted** — IdP configuration works in air-gapped deployments; no cloud dependency, consistent with the rest of the platform.
- **Inherited audit trail** — every SSO login and Team membership change flows into the Phase 2 `AuditLog` and retention scheduler automatically; compliance evidence is a byproduct, not extra work.
- **Non-invasive to shipped primitives** — `User`, `ProjectMember`, and the JWT/API-token auth dependency are preserved; Teams layer *above* them, and the existing `_authenticate_api_token` min-of-role semantics extend cleanly into Team-role resolution.

Core insight: RoboScope has already built the visual/reporting layer that non-technical testers and POs need. Phase 4 is the *distribution mechanism* that finally gets those users in front of it.

## Project Classification

- **Project Type:** Multi-part self-hosted web application (FastAPI backend + Vue 3 SPA + Chrome MV3 extension)
- **Domain:** Developer/QA tooling — test-automation platform (Robot Framework), deployed inside enterprise IT
- **Complexity:** Medium-High — brownfield integration with live auth, RBAC, audit, and encryption primitives; new Team/Org model; role-resolution ambiguity across three layers (global role → Team role → per-project override) must be decided; offline/self-hosted constraints; identity-provider abstraction to introduce without breaking existing JWT/API-token flow.
- **Project Context:** Brownfield — Phase 4 of the Enterprise-Readiness milestone. Phases 1 (CI/CD webhooks + API tokens), 2 (audit + retention + secret encryption), and 3 (visual flow editor) are shipped.

## Success Criteria

### User Success

- A new tester (no prior RoboScope account) completes SSO login and reaches a rendered test report in under **60 seconds** from a fresh browser, with zero prior account setup.
- A Product Owner or PM added to a Team can view **100% of that Team's repositories** without a repo-by-repo membership action.
- After SSO is configured for an install, targeted non-technical personas create **zero local passwords** — the username/password path is effectively bypassed for those users.
- Platform/Security Admin configures an OIDC IdP once (client ID, secret, issuer URL, group claim) and can onboard additional Teams without touching IdP settings again.

### Business Success

- **Enterprise unblock (qualitative):** no prospective customer is rejected on "no SSO" grounds after Phase 4 ships. Sales/PoC conversations that previously stalled at auth reach a technical evaluation.
- **Stakeholder inclusion:** non-technical roles (PO, PM, tester-new-to-RF, VIEWER-tier users) become a meaningful share of active seats on installs that have adopted SSO — tracked qualitatively via customer feedback and install telemetry where available.
- **Timeline:** no hard external deadline. Phase 4 is the next enterprise-readiness milestone and ships when MVP scope is done and audited.

### Technical Success

- **Zero regressions in existing auth.** The current ~555 backend tests and 217 Playwright E2E tests remain green. Existing JWT login and `rbs_…` API-token flows are unchanged externally.
- **SSO integration tests per IdP.** Azure AD, Google, and GitHub OIDC paths each have integration coverage using mocked OIDC fixtures (no live IdP calls in CI).
- **Role-resolution rule is explicit, documented, and tested.** The three-layer hierarchy (global `User.role` → `TeamMember.role` → `ProjectMember.role`) has a single documented resolution rule, enforced in `get_effective_role()` (or equivalent), with unit tests covering every combination that produces a different outcome.
- **Audit coverage is automatic.** Every SSO login (success and failure), IdP configuration change, Team CRUD, and Team membership change is captured in `AuditLog` via the existing middleware. Verified by test.
- **Offline/self-hosted invariant holds.** No new CDN, Google Fonts, or external asset is introduced. No mandatory outbound network call at application boot. IdP discovery endpoints are only contacted when an admin has configured an IdP.
- **Secrets handled correctly.** OIDC client secrets are encrypted at rest via the existing Fernet/`is_secret=True` pathway; never logged in plaintext.

### Measurable Outcomes

| Outcome | Measure | Target |
|---|---|---|
| New-user SSO time-to-first-report | Wall-clock from "Sign in" click to report render | < 60 s |
| Team → repo access propagation | Repos visible to a Team-only member / total Team repos | 100% |
| Existing-test regression | Failing backend + E2E tests after Phase 4 merge | 0 |
| IdP coverage | OIDC providers with integration tests | Azure AD, Google, GitHub |
| Audit coverage for Phase-4 events | Event types emitted to `AuditLog` | login (ok/fail), IdP config CRUD, Team CRUD, TeamMember CRUD |
| Offline compatibility | New external network dependencies at boot | 0 |

## Product Scope

### MVP — Minimum Viable Product (ships in Phase 4)

- **OIDC login** for Azure AD, Google, and GitHub, with admin-configured IdP entries (client ID, secret, issuer URL, scopes, group claim name).
- **`Team` + `TeamMember` models** with Role enum reuse (`VIEWER/RUNNER/EDITOR/ADMIN`), CRUD API, and admin UI.
- **Team → Project (repository) assignment** with role inheritance into `ProjectMember`-equivalent resolution.
- **IdP-group → Team mapping** (an IdP group claim value maps to a Team; login auto-syncs membership).
- **Documented role-resolution rule** across the three layers, with tests.
- **Audit coverage** for all new events via existing middleware.
- **Admin UI** for IdP configuration, Team management, and group mapping — aligned with shipped RoboScope UI conventions and i18n (EN/DE/FR/ES).
- **Migration plan** for existing `User` / `ProjectMember` data: no data loss, local-password login remains available post-Phase-4 for bootstrap and break-glass scenarios.

### Growth Features (Post-MVP)

- **SAML 2.0** support for enterprise IdPs that require it.
- **SCIM 2.0** user/group provisioning.
- **Just-in-time (JIT) user policies** — configurable auto-provisioning rules beyond simple group-to-Team mapping.
- **Team-scoped API tokens** (extend `ApiToken` with optional `team_id`).
- **Additional OIDC providers** (Okta, Keycloak, generic OIDC) via the admin-config abstraction introduced in MVP.

### Vision (Future)

- **Organization hierarchy** — `Organization` → nested Teams → Projects, with role inheritance across the hierarchy.
- **Fine-grained permission policies** beyond the 4-role enum (e.g., per-action grants, conditional rules).
- **Delegated admin** — scoped admin rights to a Team or Organization without global ADMIN role.
- **External identity federation** — B2B guest access, cross-tenant Teams.

## User Journeys

### Journey 1 — Maya: tester new to Robot Framework (primary, success path)

**Opening scene.** Maya is a manual tester at a mid-size insurance company. Her QA lead has decided the team will migrate to Robot Framework "sometime this year." Maya is skeptical — her last automation attempt meant wrestling with Selenium IDs for three weeks and shipping nothing.

**Rising action.** Her QA lead sends her a link to the internal RoboScope install. The login page shows two options: a primary **"Sign in with Azure AD"** button and, tucked behind a "Sign in with password" toggle, a local-password form. Maya clicks the familiar Azure AD button — the same one she uses for Jira, Confluence, and payroll — consents to the standard corporate login, and lands back on RoboScope.

**Climax.** She does not land on a dashboard. She lands on a **first-login welcome screen** showing three cards in sequence:

1. **Your teams** — *"You've been added to `Checkout-QA` via your Azure AD group `checkout-testers`."* This single sentence tells her **why** she has access, which preempts the "am I supposed to be seeing this?" hesitation that gates non-technical users for minutes.
2. **Start here** — one primary call-to-action: *"Open `checkout-e2e` repository."* One repo, the most-recently-active one in her default Team, not a grid of twelve.
3. **New to RoboScope?** — an inline link to a 60-second tour. Not a modal takeover.

She clicks through to `checkout-e2e`, opens a test in the Phase 3 visual flow editor, and sees it as a flowchart. A banner at the top reads *"Read-only — ask an EDITOR to change this"* because her effective role on this repo resolves to VIEWER+RUNNER. She can't edit nodes, but she can click **Run**. The button responds within 300 ms with a persistent *"Run started — [watch live]"* indicator. She watches the run pass.

**Resolution.** "I can understand this before I can write it." She opens a second test the next day, then a third. Two weeks later she writes her first keyword.

**Reveals requirements:**
- SSO button prominent on login page, local-password form always available but visually secondary when SSO configured.
- First-login landing page with named "why you have access" reassurance drawn from IdP group claims.
- Group-claim → Team auto-assignment at login.
- VIEWER/RUNNER visual affordances in the flow editor (read-only banner, disabled-with-tooltip editing, enabled Run).
- < 300 ms Run feedback with persistent in-flight indicator.
- First-login "Start here" defaults to a single most-recently-active repo in the default Team; configurable demo/read-only repo fallback when the user's Teams have zero repos.

### Journey 2 — QA Lead: daily Team operator (primary, operator persona)

**Opening scene.** Anita is the QA lead for the Checkout squad. Until Phase 4, she manages access by emailing platform admins every time a new hire joins, a contractor leaves, or a repo moves squads. She spends ~2 hours a month on access tickets and hates every minute of it.

**Rising action.** After Phase 4 ships, Sarah (RoboScope Admin) creates the OIDC config and hands Anita the Teams UI. Anita opens **Admin → Teams**. The empty state doesn't show a blank form — it shows **"No Teams yet. A Team is a group of people who share access to a set of repositories. [Create your first Team] or [Import from IdP groups]."** She clicks **Import from IdP groups** and picks `checkout-testers`, `checkout-editors`, `checkout-leads` from a live list — no hand-typing of group names that already exist in Azure AD.

**Climax.** Over the next week she: (a) onboards a new hire by asking IT to add them to `checkout-testers` in Azure AD — no RoboScope action needed, the user's first login syncs membership automatically; (b) moves the `vouchers-api` repo from the Claims Team to the Checkout Team via the repo settings (one `team_id` FK change); (c) removes a departing contractor by asking IT to disable them in Azure AD — `is_active=false` propagation handles immediate session revocation; Team memberships remain in `AuditLog` for compliance.

**Resolution.** Anita's monthly access-ticket workload drops from two hours to near-zero. Her access operations now live inside her IdP, which is where HR is already making the truth-of-record changes.

**Reveals requirements:**
- Team CRUD UI with empty-state that teaches the concept.
- **"Import from IdP groups"** primary CTA — lists groups the IdP has returned in the most recent login or dry-run, not a blank text field.
- One repository → one Team assignment (`Repository.team_id` FK; `NULL` = unscoped).
- Team-level role assignment (VIEWER/RUNNER/EDITOR/ADMIN) per group→Team mapping.
- Login-time group→Team membership sync, inline + transactional.
- Membership history preserved in `AuditLog` after removal.
- No real-time deprovisioning: `is_active=false` is the immediate-revocation path; Team membership stale until next login. This is an **explicit non-goal**, documented in-product.

### Journey 3 — Sarah: RoboScope Admin (secondary, one-time setup, distrust-centered)

**Opening scene.** Sarah owns SaaS identity at the same insurance company. New request: "RoboScope, QA wants it, make it SSO." She's been burned by OIDC configs that work in a dry-run and fail at 9 a.m. Monday when a real user tries to log in. She does not trust happy paths.

**Rising action.** She logs in with the bootstrap `admin@roboscope.local` account (local-password path, always available as a separate auth path — not a fallback *inside* the SSO flow). Opens **Admin → Identity Providers → New Provider**. The form collects: display name, issuer URL, client ID, client secret (stored Fernet-encrypted via `src/encryption.py`), scopes, group-claim name, redirect URI (pre-filled, read-only). A prominent **"Run dry-run"** button sits next to **Save as draft**.

**Climax — the distrust beat.** Sarah clicks **Run dry-run before committing**. RoboScope performs a discovery probe (`GET <issuer>/.well-known/openid-configuration`), fetches the JWKS, and returns a structured report:

- ✅ Issuer reachable (387 ms)
- ✅ Discovery document valid (`authorization_endpoint`, `token_endpoint`, `jwks_uri` present)
- ✅ JWKS fetched (3 signing keys)
- ⚠️  Group claim preview requires a real login — *[Run test login as yourself]*
- ❌ `client_secret` — not verified (verified at first real token exchange)

The report renders **before** the Save button is enabled. If the dry-run fails (issuer unreachable, discovery invalid), the error message is specific enough to act on — *"Can RoboScope reach `{issuer_url}`? Check firewall/egress"* — not a generic "IdP error." Only after Sarah sees green does she save. She then runs **Test login as yourself**, which completes a real OIDC round-trip and displays the decoded token claims (including the `groups` array) in a debug panel, so she can **see the exact group names before mapping them to Teams**.

She creates three group→Team mappings by picking from the live group list in the debug panel (not typing), assigns each a default role, and calls it done. She then downloads the **pre-generated IdP-admin handoff artifact** — a one-page PDF with callback URL, redirect URIs, required scopes, the group claim name she configured, and a test-login procedure — and emails it to Ingrid (the customer-org IdP admin, PRD Section 4.2) as the document that finalizes the Azure AD side of the setup.

**Resolution.** Three months later the QA team has 40 members across 8 Teams; Sarah has not touched the config. Her SIEM exports `AuditLog` entries for SSO logins, IdP config changes, and emergency-bypass activations.

**Reveals requirements:**
- Admin UI: IdP CRUD with mandatory **dry-run-before-save** gate (discovery + JWKS probe).
- Separate, explicit **"Test login as yourself"** flow that completes a real round-trip and surfaces decoded claims (deferred polish, not MVP blocker).
- Group→Team mapping UI that picks from **live returned groups**, never a free-text field.
- `client_secret` stored Fernet-encrypted at rest (reuses `is_secret=True` pattern from env-var secrets).
- Local-admin auth path always available as a **separate path**, not a fallback inside the SSO flow.
- Pre-generated downloadable IdP-admin handoff artifact (see Section 4.2).
- `AuditLog` entries for: SSO config CRUD, emergency-bypass toggle, login success/failure, group→Team sync, Team CRUD, membership changes.

### Journey 4 — Maya redux: IdP outage, rewritten from the user's POV (primary, edge case)

**Opening scene.** Monday, 9:04 a.m. Azure AD has a regional incident. Maya does not know this.

**Rising action.** She clicks **Sign in with Azure AD**. The browser spins for 8 seconds. She gets an error screen — in her language, via i18n (EN/DE/FR/ES) — that reads:

> **We couldn't reach your identity provider.**
>
> This usually means your company's login system is temporarily unavailable. Try again in a few minutes.
>
> If this keeps happening, contact your admin: **sarah@acme.com**.
>
> *[Try again]*

No jargon. No "invalid_grant." No mention of break-glass, bypass toggles, or failure codes. From Maya's point of view, the login is temporarily broken; she doesn't need to know why, and she has a name to ping if it persists.

**Climax.** Refresh in 10 minutes: the button works. She's logged in. No data lost: her existing JWT (if any) was never invalidated by the outage — only *new* logins were blocked.

**Resolution (admin side, happens in parallel, invisible to Maya).** If the outage extends, Sarah flips a single global `Settings.sso_emergency_bypass` toggle (ADMIN-only, audit-logged, auto-expires after 4h via APScheduler). While active, the local-password form is visually elevated on the login page; SSO users can reset their local password via the normal "forgot password" flow to get in. The toggle self-disables on expiry. All failed SSO attempts during the outage are captured in `AuditLog` for post-incident review.

**Reveals requirements:**
- Human-language error copy for IdP-unreachable states, localized to all four app languages, with admin-contact auto-populated from the IdP config.
- Existing JWTs remain valid during IdP outages (no IdP call on every request; stateless JWT validation as today).
- **Single global `Settings.sso_emergency_bypass`** toggle — NOT per-user. Auto-expires. Audit-logged. (Per-user local-login override is an **explicit non-goal** — deleted from scope.)
- Local-password auth path always available as a separate, always-on path (no "outage mode" to flip).
- All failed SSO attempts captured in `AuditLog`.

### Journey Requirements Summary

Capabilities revealed across the four journeys, grouped by functional area:

**Authentication & session**
- OIDC login (Azure AD, Google, GitHub) with `authlib`; IdP `id_token` consumed once at callback and discarded; RoboScope JWT issued with existing shape.
- Local-password path always available as a separate, always-on auth path.
- Bookmark-survives-session-expiry: on 401, SPA redirects to `/login?return_to=<url>`; after re-auth, redirects back. Boring, no silent renew. `return_to` validated against app origin.
- Existing `rbs_…` API tokens unchanged; `ApiToken.role` continues to cap against `User.role` (global), not effective role.

**Identity provider configuration (admin)**
- `IdentityProvider` model: display name, issuer URL, client ID, Fernet-encrypted client secret, scopes, group-claim name, enabled/draft state.
- Mandatory dry-run-before-save: discovery probe + JWKS fetch. Structured report UI.
- OIDC discovery cached per-IdP in DB with 24h TTL refresh via existing APScheduler; lazy-fetched, never blocks app boot.
- Test-login flow with decoded-claims debug panel (polish, post-MVP).

**Teams & membership**
- `Team` model (name, description, created_at) + `TeamMember(user_id, team_id, role)` unique composite.
- `Repository.team_id: int | None` FK — one team per repo; `NULL` = unscoped/global.
- Group→Team mapping stored as part of IdP config (`IdPGroupMapping(idp_id, group_name, team_id, role)`).
- "Import from IdP groups" creates Teams from live returned groups, not typed input.
- Team CRUD UI with teaching empty-states.

**Role resolution**
- `effective_role(user, repo) = MAX(user.role, team_role_for(user, repo), project_member_role(user, repo))`.
- Documented resolution rule with unit-test coverage of every combination that produces a different outcome.
- Visual affordances in flow editor (VIEWER/RUNNER read-only banner, disabled-with-tooltip editing).

**First-login UX**
- Dedicated welcome screen, shown once per user, dismissable.
- Surfaces "you were added to Team X via IdP group Y" reassurance.
- Primary CTA = open one most-recently-active repo in default Team.
- Team switcher in header from day one when user is in >1 Team.
- Fallback demo/read-only repo when user's Teams have zero repos.
- NOT a stats dashboard. NOT a modal takeover.

**Error & empty states (enumerated, required)**
1. First-login, zero Teams matched — "signed in, no Team yet" with Request Access CTA.
2. First-login, multiple Teams matched — Team switcher + default-Team preference.
3. Dry-run: issuer unreachable — specific firewall/egress copy.
4. Dry-run: credentials rejected — "secret may have been rotated" copy.
5. Dry-run: group claim missing — list alternatives (`groups`, `roles`, `wids`), show raw claims.
6. Dry-run: groups present but no mappings — surface as the *"SSO works → now make it useful"* CTA.
7. Team config dialog empty — "Create first Team" + "Import from IdP groups" primary CTAs.
8. Existing local user, first SSO login with matching email — explicit link-consent dialog + audit entry.
9. Bookmarked report URL, session expired — preserve deep-link through SSO redirect.
10. VIEWER opens flow editor — read-only banner, edit disabled-with-tooltip, Run enabled.
11. IdP outage from user POV — human-language copy, admin contact surfaced, i18n all four locales.

**Sync semantics**
- Login-time only; runs inline + transactional with the login request.
- Under `ThreadPoolExecutor(max_workers=1)` constraint: must commit before the login response returns to avoid stale RBAC on the first post-login request. Idempotency on `(user_id, login_session_id)`.
- Stable `external_id: str | None` on `Team` and `TeamMember` for future SCIM compatibility (not exposed in MVP).
- Real-time deprovisioning is an **explicit non-goal**. `is_active=false` is the immediate-revocation path.

**Audit**
- Every new event type flows through existing `AuditMiddleware` into `AuditLog`: SSO login (ok/fail), IdP config CRUD, emergency-bypass activation/expiry, group→Team sync, Team CRUD, TeamMember CRUD, deprovision events.
- No new audit infrastructure; reuses Phase 2 retention scheduler.

**Offline & security invariants**
- No new CDN, Google Fonts, or external asset bundled. No outbound call at app boot.
- OIDC discovery is a runtime call gated on admin having configured an IdP — explicitly documented as distinct from the "no external runtime calls" rule, which concerned static assets and boot-time behavior.
- `client_secret` Fernet-encrypted at rest, never logged.
- `return_to` validated against app origin to prevent open redirect.

**Non-goals (explicit, documented in PRD Section 5)**
- SAML 2.0 — deferred to Phase 4.5 (`xmlsec` C dependency incompatible with `uv` / Windows / slim Docker).
- SCIM 2.0 — deferred to Phase 5.
- Per-user local-login override — deleted from scope; replaced by single global `Settings.sso_emergency_bypass`.
- Silent token renew via iframe — replaced by boring `return_to` redirect on 401.
- Multi-team-per-repo — one team per repo in v1.
- Real-time deprovisioning — login-time sync only.
- Paul the Product Owner as a confirmed persona — moved to hypothesis appendix with 60-day post-GA validation metric (see Appendix A).

## Non-User Stakeholder Requirements

RoboScope's domain is developer/QA tooling — not itself a regulated domain, but **deployed inside regulated enterprises** whose procurement and security teams impose requirements via checklist rather than through direct product use. This section captures those requirements from three non-user stakeholder clusters: the procurement/security-review buyer, the customer-org IdP admin (Ingrid — named for reference but not given a journey), and the offboarding/deprovisioning flow.

### 4.1 Procurement / Security-Review Checklist Requirements

Each item either ships in Phase 4 v1, has a named deferred release, or is explicitly out of scope. This table is intended to be copy-pasted into a vendor security questionnaire response.

| Item | Phase 4 v1 | Rationale / Detail |
|---|---|---|
| OIDC / OAuth2 login for major IdPs | ✅ Azure AD, Google, GitHub | Core scope; `authlib`-based. |
| SAML 2.0 | ❌ deferred to **Phase 4.5** | `xmlsec` C dependency incompatible with `uv` / Windows dev / slim Docker; planned but separated to avoid destabilizing the v1 build. |
| SCIM 2.0 user provisioning | ❌ deferred to **Phase 5** | Procurement answer: "on roadmap." Teams designed with stable `external_id` on `Team`/`TeamMember` to support SCIM later without a migration. |
| MFA enforcement | ✅ delegated to IdP | RoboScope does not enforce MFA itself; IdP is source of truth. Documented in security posture page. |
| Audit log | ✅ existing (Phase 2) | SSO events flow in automatically via `AuditMiddleware`. |
| Audit log export | ✅ JSON + CSV via `/audit` | Already supported; SIEM-friendly field additions made as gaps surface. |
| Session timeout | ✅ configurable per install | JWT TTL; default 8h. Re-auth is a `return_to` redirect, not silent renew. |
| Data residency | ✅ self-hosted, no phone-home | Offline-first invariant preserved; no telemetry to external services. |
| Secret encryption at rest | ✅ Fernet (existing) | `IdentityProvider.client_secret_encrypted` reuses the `is_secret=True` pattern from Phase 2. |
| SSO-only enforcement | ✅ toggleable per install | Admin can hide the local-password form from the login UI; bootstrap admin always retains access as break-glass. |
| Offboarding / immediate revocation | ✅ via `is_active=false` | Documented as the immediate-revoke path; group-sync is login-time. See Section 4.3. |
| SBOM | ✅ generated at release | Existing release pipeline publishes SBOM alongside artifacts; documented in security page. |
| Emergency bypass auditability | ✅ `Settings.sso_emergency_bypass` toggle | ADMIN-only, auto-expires (4h default), every activation + expiry written to `AuditLog`. |
| Password storage | ✅ bcrypt (existing) | Unchanged by Phase 4. |
| Transport security | ✅ HTTPS required in prod Docker compose | Nginx reverse-proxy config ships with recommended TLS settings. |

### 4.2 Customer IdP-Admin Handoff (Ingrid persona — non-user stakeholder)

RoboScope's admin (Sarah) and the customer-org IdP admin (Ingrid) are two people in two departments. They communicate by ticket, not by shared UI session. Phase 4 must produce an artifact Sarah can hand to Ingrid to finalize the IdP-side configuration.

**Requirements:**

- **Generated handoff artifact.** Downloadable from the IdP config screen as both a one-page PDF and a markdown file, containing:
  - Callback URL / redirect URIs (copy-paste ready, exact strings the IdP must whitelist).
  - Required OIDC scopes (minimum `openid profile email` + the group-claim scope the deployment uses).
  - Expected token claims and the configured `group_claim_name`.
  - Recommended IdP group naming conventions (to reduce accidental mismatches).
  - Test-login procedure Ingrid can perform without a RoboScope account (she logs into her IdP's test console and inspects the claims the IdP would issue).
- **Ingrid does not get a RoboScope login.** She owns the IdP-side configuration only.
- **Artifact is localized** to the four app languages (EN/DE/FR/ES).
- **Markdown version embeds a Mermaid sequence diagram** of the OIDC handshake (per tech-writer feedback), so Ingrid can see the full flow at a glance without reading OIDC spec documents.

### 4.3 Offboarding & Deprovisioning Semantics

This section addresses the #1 security-review question explicitly, so neither procurement nor audit needs to infer it from code.

**Expected offboarding flow (HR-driven):**

1. HR disables the departing user in the IdP (Azure AD / Google / GitHub).
2. On any subsequent login attempt, the IdP itself rejects the user; RoboScope never receives a token.
3. `AuditLog` captures the failed login attempt if it reaches RoboScope's error path, or captures no event if the IdP rejects pre-redirect (this is correct — RoboScope cannot audit what it does not see).
4. The user's existing JWT remains valid until its TTL expires (default 8h). For immediate revocation, follow the path below.

**Immediate revocation path:**

- Admin sets `User.is_active=false` in RoboScope.
- `get_current_user` dependency re-checks `is_active` on every request; sessions belonging to deactivated users are rejected on the next API call.
- All `ApiToken` records belonging to the user are marked `revoked_at=now()` automatically (cascade trigger on `User.is_active` transition to false).
- Event is written to `AuditLog`.

**Orphan / retention policy:**

- Removed `TeamMember` records are retained for **90 days** (configurable via new setting `deprovision_retention_days`, reuses the Phase 2 retention scheduler).
- After the retention window, records are deleted; the originating `AuditLog` entries remain subject to the existing audit retention policy.
- Retention window is independently configurable from the audit-log retention window.

**API tokens at deprovision:**

- `ApiToken` records owned by a deprovisioned user are marked `revoked_at=now()`; not deleted.
- A new admin endpoint `POST /auth/api-tokens/{token_id}/reassign {user_id}` (EDITOR+ only, audit-logged) allows transferring ownership of a shared-CI/CD token when the original owner leaves the company. Prevents a disruptive rotation of production CI/CD credentials as collateral damage of every personnel change.

**Group-sync staleness window (documented non-goal):**

- A user removed from an IdP group retains their Team role in RoboScope until their next login (when login-time sync runs and updates membership).
- Immediate revocation requires `is_active=false`, not group removal.
- This limitation is documented in-product (admin docs page) and in the procurement checklist response.

## Phase 4 Technical Requirements

The net-new technical surface for Phase 4. This section is the drop-in reference for architects and implementers; it complements (and does not repeat) the Journey Requirements Summary and Section 4.

### New Data Models

| Model | Purpose | Key fields |
|---|---|---|
| `IdentityProvider` | One OIDC provider config per enabled IdP | `id`, `name`, `provider_type` (`azure_ad` / `google` / `github` / `generic_oidc`), `issuer_url`, `client_id`, `client_secret_encrypted` (Fernet), `scopes`, `group_claim_name`, `discovery_cache_json`, `discovery_cached_at`, `is_enabled` |
| `Team` | Group of users sharing access to a set of repositories | `id`, `name`, `description`, `external_id` (nullable, reserved for SCIM), `created_at`, `updated_at` |
| `TeamMember` | User ↔ Team membership with role | `user_id`, `team_id`, `role` (reuses existing `Role` enum), `source` (`manual` / `idp_group_sync`), `external_id` (nullable), unique composite `(user_id, team_id)` |
| `IdPGroupMapping` | Maps an IdP group claim value to a Team + role | `idp_id`, `group_name`, `team_id`, `role`, unique composite `(idp_id, group_name)` |
| `OidcLoginAttempt` | Short-lived state/nonce/PKCE storage for in-flight OIDC flow | `state` (PK), `nonce`, `pkce_verifier`, `idp_id`, `return_to`, `created_at`; TTL ~10 min cleaned by existing APScheduler retention job |

### Modified Existing Models

- `Repository` — add `team_id: int | None` FK (nullable, one team per repo; `NULL` = unscoped / global).
- `User` — no schema change. `hashed_password` remains required; "SSO-only user with no password at all" is out of scope for v1 (bootstrap admin + break-glass logic depends on the password path existing).
- `Settings` — add `sso_emergency_bypass` (bool), `sso_emergency_bypass_expires_at` (datetime), `deprovision_retention_days` (int, default 90).

### New / Changed API Endpoints (`/api/v1/`)

| Method | Path | Required Role | Purpose |
|---|---|---|---|
| GET | `/auth/sso/providers` | public | List enabled IdPs for login UI (display name + icon only) |
| GET | `/auth/sso/{idp_id}/login` | public | Initiate OIDC flow; writes `OidcLoginAttempt`; 302 → IdP authorization endpoint |
| GET | `/auth/sso/callback` | public | OIDC callback; exchanges code, validates id_token, syncs groups → Teams, issues RoboScope JWT, 302 → `return_to` |
| POST | `/auth/api-tokens/{id}/reassign` | EDITOR+ | Reassign shared CI/CD API token ownership after user deprovision |
| GET | `/auth/idp-providers` | ADMIN | List configured IdPs (full config; `client_secret` never returned) |
| POST | `/auth/idp-providers` | ADMIN | Create IdP config (draft state until dry-run passes) |
| PUT | `/auth/idp-providers/{id}` | ADMIN | Update IdP config |
| DELETE | `/auth/idp-providers/{id}` | ADMIN | Delete IdP config |
| POST | `/auth/idp-providers/{id}/dry-run` | ADMIN | Discovery probe + JWKS fetch; returns structured report |
| GET | `/auth/idp-providers/{id}/handoff` | ADMIN | Download handoff artifact (PDF + markdown, localized) |
| GET | `/teams` | VIEWER | List Teams user has membership in |
| POST | `/teams` | ADMIN | Create Team |
| POST | `/teams/import-from-idp-groups` | ADMIN | Bulk create Teams from live IdP group list |
| PUT | `/teams/{id}` | ADMIN | Update Team |
| DELETE | `/teams/{id}` | ADMIN | Delete Team |
| GET | `/teams/{id}/members` | VIEWER (member) / ADMIN | List Team members |
| POST | `/teams/{id}/members` | ADMIN | Add member manually (source=`manual`) |
| DELETE | `/teams/{id}/members/{user_id}` | ADMIN | Remove member manually |
| GET | `/teams/{id}/group-mappings` | ADMIN | List IdP group → Team mappings for this Team |
| POST | `/teams/{id}/group-mappings` | ADMIN | Create IdP group → Team mapping |
| DELETE | `/group-mappings/{id}` | ADMIN | Delete mapping |
| PUT | `/repos/{id}/team` | ADMIN | Assign / reassign repo to a Team (updates `Repository.team_id`) |
| POST | `/settings/sso-emergency-bypass` | ADMIN | Activate bypass (duration in hours; max 24) |
| DELETE | `/settings/sso-emergency-bypass` | ADMIN | Deactivate bypass manually |

All endpoints flow through existing `AuditMiddleware`.

### OIDC Login Flow (sequence)

1. Browser → `GET /auth/sso/{idp_id}/login?return_to=<url>`
2. Backend validates `return_to` against own origin (open-redirect defense); generates `state`, `nonce`, `pkce_verifier`; persists `OidcLoginAttempt`; 302 → IdP `authorization_endpoint`
3. User consents at IdP → IdP 302 → `GET /auth/sso/callback?code=…&state=…`
4. Backend looks up `OidcLoginAttempt` by `state`; verifies `nonce`; exchanges `code` for `id_token` via `authlib`; validates signature against cached JWKS
5. Backend extracts claims: `sub`, `email`, group-claim array
6. Backend upserts `User` by email; sets `last_login_at`
7. **Inline transactional group → Team sync** (same DB transaction as login): diffs IdP-reported groups vs current `TeamMember` rows with `source='idp_group_sync'`; inserts new rows, removes stale; commits
8. Backend issues RoboScope JWT (existing shape; no IdP claims embedded); 302 → `return_to`
9. IdP `id_token` is discarded — RoboScope is not an OIDC RP that carries foreign tokens

### Test Surface (estimate)

- **~35 new pytest tests** — split across auth flow, group sync, role resolution, dry-run, encrypted secret, bypass toggle, offboarding semantics.
- **~7 new Playwright tests** — first-login landing, VIEWER read-only banner, admin dry-run + save, Team import-from-groups, bookmark-survives-expiry, emergency bypass, outage error copy.
- **1 shared mock OIDC fixture** in `backend/tests/fixtures/mock_oidc.py` — powers every SSO-path test so CI never depends on a live IdP.
- Existing ~555 backend + 217 Playwright tests must remain green (zero regressions, per Success Criteria).

### Implementation Constraints (reminders from `CLAUDE.md`)

- **uv-only venv management.** All dependency changes via `uv`; `authlib` addition via `uv add`, pinned.
- **No outbound call at app boot.** Discovery fetch is lazy, cached in DB with 24h TTL, refreshed via existing APScheduler.
- **Sync SQLAlchemy 2.0.** All new models use the sync session; no async additions.
- **`db.commit()` before any `dispatch_task()`.** Login-time group sync is inline (not dispatched); no task-executor interaction in the auth path.
- **Offline invariant for static assets unchanged.** No CDN, no Google Fonts, no external runtime asset bundled.
- **vue-i18n escaping.** All user-facing strings localized in EN/DE/FR/ES; `@|{}` escaped; production build must pass locally before merge.
- **Audit middleware.** Every POST/PUT/PATCH/DELETE endpoint above is automatically logged; no manual audit calls needed.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach: Problem-Solving MVP.** The smallest SSO + Teams surface that lets a security-reviewed enterprise deploy RoboScope without a procurement exception — nothing more. Every feature request between now and GA is held against that sentence. If a candidate feature doesn't help a procurement review pass or doesn't unblock one of the four canonical journeys (Maya, QA Lead, Sarah, Maya-redux), it's out of v1.

**Validated-learning target.** One design-partner deployment clears security review, onboards one non-technical seat (tester or PO) via SSO, and runs for 30 days without an auth-related support ticket. That is the "v1 is done" signal.

**Resource Requirements.**

- **1 backend engineer** (primary — OIDC flow via `authlib`, Teams model, group sync, migrations, ~35 new pytest).
- **1 frontend engineer** (part-time through sprint 2, full in sprint 3 — login page, first-login landing, admin IdP/Teams UI, 4-locale i18n, VIEWER read-only affordances).
- **1 QA / E2E engineer** (part-time — 7 Playwright specs; builds the shared mock-OIDC fixture in sprint 1).
- **Ad-hoc tech-writer review** (Paige's 12-term glossary, two Mermaid diagrams for Journey 3, J4 outage-copy per-locale pass).
- **Timeline:** ~3 sprints (~6 weeks) disciplined; ~5 sprints if any deferred item (SAML, SCIM, per-user override) is pulled back in.

### MVP Feature Set (Phase 4 v1)

Covered in **Product Scope → MVP** and **Phase 4 Technical Requirements**; not restated here. Canonical summary: OIDC (Azure AD / Google / GitHub), `Team` + `TeamMember` + `Repository.team_id`, login-time group sync, `MAX()` role resolution, `sso_emergency_bypass` toggle, first-login landing page, dry-run-before-save, procurement / handoff / offboarding docs, EN/DE/FR/ES locale complete.

### Post-MVP Features

Covered in **Product Scope → Growth** and **Vision**. Canonical summary:

- **Phase 4.5** — SAML 2.0 (isolated because `xmlsec` breaks `uv` install on slim Docker / Windows).
- **Phase 5** — SCIM 2.0 user/group provisioning; additional OIDC providers (Okta, Keycloak, generic); Team-scoped API tokens.
- **Future** — Organization hierarchy (Org → Teams → Projects); fine-grained policy permissions beyond the 4-role enum; delegated admin; external B2B federation.

### Risk Mitigation Strategy

**Technical risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Login-time group sync races under sync `ThreadPoolExecutor(max_workers=1)`, producing stale RBAC on first post-login request | Medium | High | Sync runs inline in the same transaction as the login request; commits before JWT issuance. Idempotency on `(user_id, login_session_id)`. Dedicated ~8 pytest covering concurrency, rollback, duplicate cases. |
| OIDC discovery URL breaks offline-install invariant | Low | Medium | Discovery fetch is runtime-only and admin-triggered; cached per-IdP in DB with 24h TTL refresh via existing APScheduler. Documented as distinct from the "no outbound at boot" rule, which concerns static assets and boot behavior. |
| `xmlsec` C dependency blocks `uv` install on slim Docker / Windows if SAML is added | High (if pulled forward) | High | SAML is explicitly Phase 4.5; do not pull forward under any scope pressure. |
| Three-layer role resolution produces surprising effective roles via `MAX()` | Low | Medium | Rule is explicit, documented, and unit-tested across every combination that yields a different outcome. |
| `return_to` redirect is exploited for open-redirect | Low | Medium | `return_to` validated against app origin; regression test in place. |

**Market risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No design partners recruited before v1 cut — feedback loop is slow, Phase 4.1 tightening pass likely | **High (current state: no partners)** | Medium | Recommend recruiting 2 design partners before v1 cuts from trunk. If not possible, plan an explicit Phase 4.1 tightening sprint in the roadmap and communicate to stakeholders. Telemetry on SSO-login rate + first-login-landing engagement at pilot customers is the validation signal. |
| Paul-the-PO persona is a ghost (no non-technical seats actually log in post-GA) | Unknown (no evidence either way) | Low for v1 (Paul is out of scope); Medium for Phase 5 prioritization | 60-day post-GA validation metric: ≥3 non-engineering seats / deployed customer with weekly login + >30 s on reports view. If it fails, cut Paul permanently; if it passes, Phase 5 earns a stakeholder-dashboard story. |
| Procurement at a target customer has an uncovered checklist item (custom SAML metadata, specific audit-format need) | Medium | Medium | Section 4.1 is extensible; first procurement rejection after GA triggers a checklist delta review, not a re-architecture. |

**Resource risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Frontend engineer unavailable during localization pass | Medium | Medium | Lock translation keys in sprint 1; tech-writer pass runs in sprint 2 in parallel with implementation, not sequentially at the end. Automated prod-build test in CI catches vue-i18n `@\|{}` escape regressions. |
| Group-sync subtask underestimated (Amelia flagged this as the #1 underestimated piece) | Medium | Medium | Carve group sync into its own explicit sub-story with its own acceptance criteria; do not bundle under "SSO login." Track it separately from sprint 1. |
| Scope pressure to pull SAML / SCIM / per-user override into v1 | Medium | High | Non-Goals list is **PRD-level, not sprint-level**. Any request to pull in a non-goal requires a PRD amendment, not a sprint-scope conversation. |

## Functional Requirements

*This section is the binding **capability contract** for Phase 4 v1. UX designs, architecture decisions, epics, stories, and tests must trace back to one or more FRs below. Any capability not listed here will not exist in Phase 4 v1 unless explicitly added via PRD amendment.*

### Identity Provider Configuration

- **FR1:** An Admin can create, view, update, and delete OIDC identity-provider configurations for at least Azure AD, Google, and GitHub.
- **FR2:** An Admin can store an identity provider's client secret in a form that is encrypted at rest and never returned in any API response.
- **FR3:** An Admin can validate an identity-provider configuration via a dry-run that checks issuer reachability and key-material availability, without committing the configuration.
- **FR4:** An Admin cannot enable an identity-provider configuration until its dry-run has succeeded at least once.
- **FR5:** An Admin can download a localized handoff artifact (PDF + markdown) containing the information needed by the customer-org's IdP admin to complete the IdP-side configuration.
- **FR6:** The system caches identity-provider discovery metadata per-IdP and refreshes it on a schedule, such that no outbound network call is required at application boot.

### SSO Authentication (end-user)

- **FR7:** An unauthenticated user can initiate sign-in with any enabled identity provider from the login page.
- **FR8:** An unauthenticated user can still sign in with a local password as a separate, always-available path, independent of identity-provider state.
- **FR9:** When single sign-on is configured, the local-password form is visually de-emphasized (not removed) on the login page.
- **FR10:** An Admin can configure the system to hide the local-password form entirely from the login page while preserving bootstrap-admin access.
- **FR11:** After successful SSO authentication, the system issues a session credential whose shape is identical to the existing local-login session credential, so that existing API-token and session-based code paths continue to function unchanged.
- **FR12:** A user landing on the login page via a deep link to a protected resource is returned to that exact resource after successful authentication.
- **FR13:** The system validates the post-authentication redirect target against the application's own origin and rejects any redirect to an external URL.

### Teams & Membership

- **FR14:** An Admin can create, rename, and delete Teams.
- **FR15:** An Admin can assign a repository to at most one Team and can reassign or unassign it later.
- **FR16:** An Admin can add and remove users as Team members, and can assign each Team member a role drawn from the existing role hierarchy.
- **FR17:** An Admin can map an identity-provider group claim value to a Team plus role, causing users whose tokens carry that group to gain that Team membership on login.
- **FR18:** An Admin can bulk-create Teams by importing the list of groups the identity provider returned during its most recent successful dry-run or login.
- **FR19:** A user's Team membership is synchronized with the groups reported by the identity provider at each login, such that first-login and subsequent-login both produce consistent membership.
- **FR20:** Team memberships created by IdP-group synchronization are distinguishable from memberships created manually, so that IdP-driven changes do not overwrite intentional manual grants.
- **FR21:** A user can view the list of Teams they belong to.
- **FR22:** An Admin or Team member can view the full member roster of any Team they belong to; non-members cannot.

### Access Control & Role Resolution

- **FR23:** The system computes a user's effective role on a given repository as the maximum of the user's global role, the user's Team role on the Team that owns the repository, and the user's direct project-member role on that repository.
- **FR24:** The effective-role rule is the single source of truth for all permission checks on repository-scoped actions.
- **FR25:** A user with VIEWER effective role on a repository can read repository content and reports, and cannot edit or run.
- **FR26:** A user with RUNNER effective role can additionally execute tests on that repository.
- **FR27:** A user with EDITOR effective role can additionally modify repository content on that repository.
- **FR28:** A user with ADMIN role (global or via any layer) retains existing ADMIN capabilities unchanged.
- **FR29:** A repository not assigned to any Team continues to apply global-role-plus-project-member resolution, identical to pre-Phase-4 behavior.
- **FR30:** Existing long-lived API tokens continue to authenticate and authorize exactly as before Phase 4; their effective role remains capped at the owner's global role at token creation.

### First-Login & Onboarding Experience

- **FR31:** A user signing in via SSO for the first time is presented with a welcome experience that surfaces which Teams they belong to and why (the identity-provider group(s) that granted the Team membership).
- **FR32:** The welcome experience directs the user to a single primary starting point — the most recently active repository in their default Team — rather than an empty or stats-oriented dashboard.
- **FR33:** A user belonging to more than one Team can select and change their default Team from the application header.
- **FR34:** A user whose Teams contain no repositories is shown a non-dead-end state: a request-access action, and where configured, a read-only demonstration repository.
- **FR35:** A user opening a read-only view of editable content is shown an explicit read-only indicator that explains why editing is unavailable.
- **FR36:** A user whose SSO-derived identity matches an existing local-account email is given an explicit consent dialog before the accounts are linked.

### Resilience & Outage Handling

- **FR37:** A user whose session credential is still valid remains authenticated even when the identity provider is unreachable.
- **FR38:** A user whose SSO sign-in fails because the identity provider is unreachable is shown a localized, non-technical error message that surfaces the administrator's contact address and invites them to retry.
- **FR39:** An Admin can activate a time-bounded emergency bypass that allows local-password sign-in on an installation configured as SSO-only.
- **FR40:** An emergency bypass automatically deactivates after a configurable expiry, with a system-enforced maximum duration.
- **FR41:** Exactly one emergency-bypass mechanism exists at installation scope; there is no per-user bypass.

### Deprovisioning & Offboarding

- **FR42:** An Admin can deactivate a user such that the user's existing sessions are rejected on the next request and all of the user's API tokens are revoked.
- **FR43:** The system retains removed Team-membership records for a configurable retention window before deletion, so that historical membership remains inspectable during that window.
- **FR44:** An Admin can reassign ownership of an API token from a deactivated user to an active user, so that shared CI/CD credentials survive personnel changes without rotation.
- **FR45:** The system documents and enforces that IdP-group removal does not take effect on an existing RoboScope session until the user's next login; immediate revocation requires account deactivation.

### Audit & Compliance

- **FR46:** Every identity-provider configuration change, emergency-bypass activation and expiry, Team change, Team-membership change (including IdP-group-synchronization changes), and API-token reassignment is recorded in the audit log with user, timestamp, and detail.
- **FR47:** Every SSO sign-in attempt (successful and failed) that reaches the RoboScope server is recorded in the audit log.
- **FR48:** The audit log is exportable in the existing formats without modification required by Phase 4.
- **FR49:** The audit retention scheduler applies to all new Phase 4 audit events using the existing retention configuration.

### Localization & Accessibility

- **FR50:** Every user-facing string introduced by Phase 4 — including error messages, first-login welcome content, admin-UI labels, and the IdP-admin handoff artifact — is available in the four supported application languages (EN, DE, FR, ES).

## Non-Functional Requirements

### Performance

- **NFR1:** An interactive SSO sign-in round-trip (user click → IdP round-trip → first application page rendered) completes in under **5 seconds** on a healthy IdP connection, so that the overall "time to first report" target of < 60 s remains achievable.
- **NFR2:** The IdP dry-run completes within **10 seconds** or returns a specific timeout error identifying which phase (discovery fetch vs JWKS fetch) exceeded the budget.
- **NFR3:** Login-time group-to-Team synchronization adds no more than **500 ms** of latency to the overall login round-trip for a user belonging to up to 50 IdP groups.
- **NFR4:** The existing ~555 backend tests and 217 Playwright tests retain their current execution time within **±10 %** after Phase 4 changes — no test-suite regression.

### Security

- **NFR5:** OIDC client secrets, like all other `is_secret=True` values, are encrypted at rest using Fernet with the installation's `SECRET_KEY` and are never logged, returned in any API response, or written to error messages.
- **NFR6:** All OIDC state, nonce, and PKCE verifier values are cryptographically random (≥128 bits of entropy), single-use, and expire within **10 minutes** of issuance.
- **NFR7:** The post-authentication redirect target (`return_to`) is validated against the application's own origin; any attempt to redirect to an external URL is rejected with a safe default redirect (application root).
- **NFR8:** OIDC `id_token`s received from identity providers are discarded immediately after claim extraction and are never stored beyond the login request's lifetime.
- **NFR9:** Session credentials issued after SSO authentication carry no identity-provider claims beyond what the existing local-login session credential carries, so that no foreign-token material enters the wider system.
- **NFR10:** Failed SSO authentication attempts are rate-limited per source IP to prevent credential-stuffing-style enumeration.
- **NFR11:** The emergency-bypass toggle requires ADMIN role to activate and to deactivate, records both events in the audit log with the activating user's identity, and is subject to a system-enforced maximum duration of **24 hours**.
- **NFR12:** Bootstrap admin access (local password) cannot be disabled, deleted, or locked out by any Phase 4 administrative action, so that break-glass access is always available.
- **NFR13:** All HTTPS termination for Phase 4 traffic — the login page, OIDC redirect endpoints, admin UI, and API — requires **TLS 1.2 or newer**; TLS 1.0 and 1.1 are explicitly disabled in the shipped Nginx reverse-proxy configuration. Outbound calls from the backend to identity providers (discovery, JWKS, token exchange) require TLS 1.2 or newer and reject older protocol versions at the client.

### Reliability & Operability

- **NFR14:** An identity-provider outage does not invalidate or reject existing, still-valid session credentials; only new sign-in attempts are affected.
- **NFR15:** The application boot sequence makes **zero outbound network calls** to any identity provider; discovery metadata is fetched lazily on first sign-in attempt after configuration and cached per-IdP for 24 hours.
- **NFR16:** OIDC discovery-metadata cache refresh is a best-effort background job; failure to refresh does not block user sign-in as long as a cached copy exists, and the admin UI surfaces an "expired-but-usable" warning.
- **NFR17:** All Phase 4 database migrations are forward-and-backward compatible within the current milestone: operators can roll back from Phase 4 → Phase 3 without data loss for pre-Phase-4 entities. New Phase 4 rows may be lost on rollback; `User`, `ApiToken`, `Repository`, `AuditLog` content is preserved.
- **NFR18:** Installations running against SQLite (development) and PostgreSQL (production) pass the identical Phase 4 test suite with no DB-specific skips.

### Deployability & Environment

- **NFR19:** No new static asset added by Phase 4 is loaded from an external CDN, Google Fonts, or any third-party host. All new UI assets are bundled into the existing offline-build artifact.
- **NFR20:** `authlib` (or equivalent OIDC library) is added via `uv` with a pinned version and is included in the Windows `windows-latest` GitHub Actions offline-ZIP build, which must succeed as a release gate.
- **NFR21:** No new dependency added by Phase 4 introduces a C-extension requiring `xmlsec`, or any other component incompatible with slim Docker images or with Windows development environments. *(This NFR is the explicit scope-gate that keeps SAML out of v1.)*
- **NFR22:** The existing Docker Compose production configuration (backend + Postgres + Nginx) boots successfully with Phase 4 changes, requiring no schema of service additions beyond the standard migration.

### Accessibility

- **NFR23:** All new UI surfaces (login page, first-login landing, admin IdP config, Teams admin, error screens) meet **WCAG 2.1 AA** for color contrast, keyboard navigability, focus visibility, and screen-reader labeling.
- **NFR24:** The login page, including the SSO provider buttons and the local-password fallback toggle, is fully operable by keyboard with no mouse interaction.
- **NFR25:** Every new interactive element has a translated `aria-label` in all four supported languages (EN, DE, FR, ES).

### Integration

- **NFR26:** The system interoperates with identity providers compliant with **OpenID Connect Core 1.0** that support the `authorization_code` flow with PKCE.
- **NFR27:** Group-claim extraction supports both string-array and JSON-path group claims, covering the formats issued by Azure AD (`groups`), Google (via Google Workspace `groups` scope), and GitHub (org/team membership via scope).
- **NFR28:** Existing `rbs_…` API tokens continue to authenticate against all existing and new Phase 4 endpoints exactly as before; no API-token client (CI/CD job, script, webhook consumer) requires modification as a result of Phase 4.

### Auditability

- **NFR29:** Every Phase 4 audit event includes structured, machine-parseable detail suitable for ingestion by SIEM systems (event type, actor, target, timestamp, IP, detail JSON).
- **NFR30:** Phase 4 audit events do not materially increase audit-log storage growth: in normal operation, the expected additional volume is below **5 %** of existing Phase 2 audit-log volume on a representative installation.

### Explicitly Out of Scope

- **Scalability** as a separate NFR section — RoboScope is self-hosted and single-tenant; sizing guidance is absorbed into Reliability/Deployability (NFR17, NFR22).
- **Privacy** as a new NFR section — no new personal-data categories beyond existing `User.email`; GDPR posture vs Phase 2 is unchanged.

## Non-Goals (Explicit)

These are consciously excluded from Phase 4 v1. Any request to pull one in requires a PRD amendment, not a sprint-scope conversation.

- **SAML 2.0** — deferred to **Phase 4.5**. Reason: `xmlsec` C-dependency breaks `uv` install on slim Docker images and on Windows dev environments (NFR21). Isolated into its own phase so a build-infrastructure problem cannot destabilize the v1 cut.
- **SCIM 2.0 user/group provisioning** — deferred to **Phase 5**. Reason: significant surface area (pagination, delete-detection, service-account auth); Phase 4 v1 preserves forward compatibility via stable `external_id` on `Team` and `TeamMember`.
- **Per-user local-login override** — **deleted from scope**. Reason: the single installation-wide `sso_emergency_bypass` toggle (NFR11, FR39–41) delivers the same outage-recovery outcome with a third of the implementation surface.
- **Silent token renewal via iframe or refresh tokens** — **deleted from scope**. Reason: boring `return_to`-redirect re-auth (FR12–13) gives Paul's bookmarkable-URL journey everything it needs at zero CSP and session-management cost.
- **Multi-team-per-repository** — one team per repository in v1. Reason: avoids ambiguity in `MAX()` role resolution and keeps the data model migrateable.
- **Real-time deprovisioning / webhook-driven IdP-group sync** — login-time sync only. Reason: procurement's immediate-revocation need is met by `is_active=false` (FR42); real-time sync is SCIM-territory (Phase 5).
- **Paul the Product Owner as a confirmed persona** — moved to hypothesis appendix (see Appendix A). Reason: no interview, ticket, or telemetry evidence currently supports the Paul persona. 60-day post-GA metric decides whether he earns a Phase 5 slot.
- **Self-service Team-admin UI for QA Leads beyond Team CRUD + membership management** — v1 covers Anita's canonical workflow (see Journey 2) but does not add Team-level settings, custom notification rules, or Team-scoped dashboards.
- **Additional OIDC providers beyond Azure AD / Google / GitHub** — Okta, Keycloak, and generic OIDC ship in Phase 5 via the admin-config abstraction introduced in v1.
- **Organization-level hierarchy, fine-grained permission policies, delegated admin** — Vision scope; see Product Scope → Vision.
- **Chrome Recorder extension changes** — the Chrome Recorder extension is explicitly **not part of Phase 4**. API-token-based authentication is preserved unchanged (FR30, NFR28). Because `ApiToken.role` remains capped at the owner's global `User.role` (not at `effective_role`), recorder users with Team-granted elevation on the web UI will see a **smaller effective permission set via the recorder than via their SSO session**. This is a deliberate design decision (API tokens are machine identities, not human-session proxies). Documented in Release Notes + in-app docs (Epic 5 deliverable). **Phase-5 candidate:** Team-scoped API tokens OR lifting `ApiToken.role` cap to effective_role — decided post-GA based on support-ticket volume (≥ N tickets → promote to a Phase-5 story; else cut).

## Rollout & Success Metrics

### Release strategy

Phase 4 v1 ships as a single coordinated release across backend, frontend, Docker images, and the offline ZIP. No feature flags are introduced: SSO is either configured (and then available on the login page) or not.

### Recommended rollout sequence

1. **Pre-merge gate.** Design-partner recruitment — ideally 2 named customers who commit to enabling SSO within 30 days of GA. If not achievable, explicitly communicate the "slow feedback loop" risk to stakeholders and schedule a Phase 4.1 tightening pass.
2. **Internal dogfooding.** RoboScope's own install configures SSO against a test IdP before the v1 merge-to-main, exercising every journey (Maya, QA Lead, Sarah, outage) end-to-end.
3. **Release note + migration guide.** Standard version bump + release-notes entry covering: new login flow, Teams migration, offboarding-semantics change, emergency-bypass, break-glass admin preserved.
4. **Post-GA monitoring window (30 days).** Any SSO-related support ticket triggers a triage review. The 30-day auth-ticket-free window is the "v1 is done" gate (Validated-Learning target, MVP Strategy).
5. **60-day Paul-validation checkpoint.** Measure non-engineering-seat login frequency at pilot customers; decide whether Paul earns a Phase 5 story or is permanently cut.

### Success metrics (measurable)

These are the metrics against which Phase 4 v1 is judged post-GA. They draw from and summarize the measurable outcomes in *Success Criteria → Measurable Outcomes*:

| Metric | Target | Measured how |
|---|---|---|
| New-user SSO time-to-first-report | < 60 s | Telemetry on `first_login_at` → first `/reports` access timestamp at pilot customers |
| Team → repo access propagation | 100 % | Automated check at release: user in Team sees all `Repository.team_id` == Team's repos |
| Backend test regressions from Phase 4 | 0 | CI gate: full suite green before merge |
| E2E test regressions from Phase 4 | 0 | CI gate: Playwright suite green before merge |
| OIDC provider coverage | Azure AD + Google + GitHub | Each has a pytest integration test with mock-OIDC fixture |
| Audit events for Phase 4 | All required events captured | FR46, FR47 verified by test |
| Offline boot invariant | 0 outbound calls at boot | CI network-isolation smoke test |
| Auth-related support tickets, 30 days post-GA | 0 | Support queue tag: `auth`, `sso` |
| Non-engineering seat login (60-day checkpoint) | ≥ 3 seats / pilot customer / week, > 30 s on reports view | Telemetry (validates or cuts Paul) |

### Release-gate checklist (copy into the release issue)

- [ ] All 50 FRs have acceptance tests (or explicitly tagged as doc-only where applicable).
- [ ] All 30 NFRs have either automated tests or documented manual-verification procedures.
- [ ] Existing ~555 pytest + 217 Playwright tests green.
- [ ] Windows `windows-latest` offline-ZIP build succeeds.
- [ ] `uv` install of pinned `authlib` succeeds on slim Docker.
- [ ] Prod frontend build passes with all 4 locales (vue-i18n `@|{}` escape check).
- [ ] Paige-reviewed glossary + two Mermaid diagrams (Journey 3) shipped in in-app docs.
- [ ] IdP-admin handoff artifact generator produces a valid PDF + markdown for a test IdP config.
- [ ] Procurement checklist response (Section 4.1 table) reviewed and signed off by someone outside the dev team.

## Open Risks & Decisions Needed

Items that are not yet resolved and require an action before or during v1 implementation.

| # | Item | Owner | Deadline | Impact if unresolved |
|---|---|---|---|---|
| R1 | **Recruit 2 design partners** before v1 cuts from trunk | Thomas / sales | Before sprint-3 merge | High: without real-user feedback, Phase 4.1 tightening pass is mandatory, not optional |
| R2 | **Decide whether to cut Paul permanently or keep the 60-day validation window** after evidence gap was confirmed | Thomas | Pre-GA | Medium: affects Phase 5 roadmap prioritization only |
| R3 | **Confirm whether any existing customer is already blocked on SSO** (anecdotal evidence from sales that would anchor the market-risk mitigation) | Thomas | Pre-GA | Medium: would convert "speculative unblock" to "named unblock" in the procurement-checklist response |
| R4 | **Pick redirect-URI naming convention** across the three IdP providers (each IdP uses different callback-URL conventions) — needs to be locked before the handoff artifact is generated | Backend eng | Sprint 1 | Low-medium: late lock means translating artifact late |
| R5 | **Decide emergency-bypass max duration** (currently 24 h in NFR11) — is this defensible in a procurement review, or should it be shorter (e.g., 4 h) with explicit re-activation? | Thomas | Sprint 1 | Low: easy to change; surfaces in procurement Q&A |

## Glossary

Twelve terms that must be defined and linked consistently wherever they appear in the app, in-app docs, and the IdP-admin handoff artifact. All entries must ship in EN/DE/FR/ES.

| Term | Short definition (English) | Translation note |
|---|---|---|
| **IdP (Identity Provider)** | External system (e.g., Azure AD, Google, GitHub) that authenticates users on RoboScope's behalf. | Never expand the acronym inline after first use; glossary-link every occurrence. |
| **OIDC (OpenID Connect)** | The authentication protocol RoboScope uses to communicate with IdPs. Built on OAuth2. | Distinguish from OAuth2 in the entry — users conflate them. |
| **SSO (Single Sign-On)** | The overall concept: one corporate login grants access across many systems. | Most readers know this; the entry anchors the others. |
| **Claim** | A statement an IdP makes about a user (e.g., `email`, `groups`). Retained as a loanword in DE/FR/ES — do not translate. | Hardest term in the domain; glossary entry must include an example. |
| **Issuer URL** | The base URL of the IdP used for discovery. Not to be confused with a callback URL. | |
| **Redirect URI** | The URL the IdP redirects the browser to after authentication. We use the OIDC-spec term everywhere (never "callback URL"). | Consistency: pick one, use it. |
| **Discovery URL / `.well-known` endpoint** | The endpoint RoboScope queries to learn the IdP's capabilities. | Needed because Sarah's procedure references the literal string `.well-known/openid-configuration`. |
| **Team** | A group of RoboScope users sharing access to a set of Repositories. Introduced in Phase 4. | |
| **Project / Repository** | The unit of test assets RoboScope manages. "Project" and "Repository" are used interchangeably in the code for historical reasons; glossary locks the user-facing term to **Repository**. | |
| **Role inheritance** | How a user's effective role on a Repository is computed from global + Team + project-member layers. | Define with an example, not abstractly. |
| **Break-glass (`Notfallzugang` DE)** | The always-available bootstrap-admin path that works independently of SSO. Used during IdP outages or misconfigurations. | Metaphor does not translate; per-locale term locked at glossary. |
| **Group mapping** | The admin-configured link between an IdP group claim value and a RoboScope Team. The mechanism that turns "Maya was added to `checkout-testers` in Azure AD" into "Maya is a member of the `Checkout-QA` Team in RoboScope." | Separate entry from "Claim" because it is the specific use case Sarah operates on. |

## Appendix A: Hypothesis Personas

Personas considered during PRD discovery but not confirmed by evidence. Not in v1 scope. Listed here so the hypothesis is traceable and can be validated or cut post-GA.

### A.1 Paul — Product Owner / Product Manager

**Hypothesis:** Given Phase 3's visual flow editor and human-readable reports, a non-technical stakeholder (PO, PM, business analyst) will log into RoboScope directly to read test coverage, after SSO removes the username/password barrier.

**Evidence status (as of 2026-04-14):** none. No interview transcript, no support ticket, no telemetry, no lost-deal note currently supports this hypothesis.

**Journey (as sketched during discovery, preserved for future validation):** Paul, Product Owner for a checkout flow, signs in via corporate SSO, views a recently-shared repository's test report via Team membership, deep-links to a specific run URL that he bookmarks for sprint reviews.

**Capabilities Paul's journey would have required (already satisfied by confirmed-persona journeys, so no Paul-specific scope is needed in v1):**
- SSO login (FR7)
- Team-scoped repo visibility for VIEWER role (FR23, FR25)
- Bookmarkable deep-link URLs surviving session expiry (FR12)

**Validation metric (60 days post-GA):**

> At pilot customer installs, ≥ 3 users whose role is explicitly non-engineering (PO/PM/BA/QA non-writer) log into RoboScope at least weekly AND spend > 30 s on a `/reports/*` view.

**Decision rule:**
- If metric **passes** at any pilot install → Paul earns a dedicated Phase 5 story (stakeholder-readable report surfaces, per-role dashboards). PRD for that story is separate.
- If metric **fails** at all pilot installs → Paul is permanently cut; non-engineering stakeholder access is served by in-team communication (Slack, Jira), not by direct RoboScope login.

**Watch for contradicting evidence in either direction:**
- If a lost-deal note, sales call, or support ticket surfaces before v1 cut that names a non-technical user wanting direct access → re-open this appendix as a full persona immediately.
- If no pilot customer is recruited (Risk R1), the metric cannot be evaluated; Paul's decision is deferred to the first deployment that *does* produce telemetry.
