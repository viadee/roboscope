# Phase 4 Non-Goals — v1 Lock (Story 5-11)

**Status:** locked at Phase 4 Release-Gate (2026-04-22).
**Change control:** any addition to or removal from this list requires a PRD amendment — not a sprint-scope conversation.

Source: `prd.md` Section "Non-Goals (Explicit)" + Phase 4 implementation retrospective.

Each entry has:
- **Rationale** — the reason the item was cut from v1.
- **Deferred to** — the concrete successor version (Phase 4.5 / Phase 5 / Vision / deleted).
- **Reconsider if** — the explicit trigger that would promote the item back into scope.

---

## N-1. SAML 2.0

- **Rationale.** `xmlsec` C-dependency breaks `uv` install on slim Docker images and on Windows dev environments (NFR21). Isolating into its own phase protects the v1 cut from build-infrastructure risk.
- **Deferred to.** Phase 4.5.
- **Reconsider if.** A named design partner commits to SAML-only IdP *before* Phase 5 kickoff OR `xmlsec` becomes a pure-Python dependency.

## N-2. SCIM 2.0 user/group provisioning

- **Rationale.** Significant surface area (pagination, delete-detection, service-account auth); Phase 4 v1 preserves forward compatibility via stable `external_id` on `Team` and `TeamMember`.
- **Deferred to.** Phase 5.
- **Reconsider if.** ≥ 2 enterprise customers require automated provisioning in RFQ; OR compliance team requires sub-24h deprovisioning propagation (currently: next login).

## N-3. Per-user local-login override

- **Rationale.** The single installation-wide `sso_emergency_bypass` toggle (NFR11, FR39–41) delivers the same outage-recovery outcome with one-third of the implementation surface.
- **Deferred to.** **Deleted.** Not a Phase 5 candidate.
- **Reconsider if.** Support ticket volume on "can't log in during outage for just me" exceeds 5 / quarter post-GA.

## N-4. Silent token renewal via iframe or refresh tokens

- **Rationale.** Boring `return_to`-redirect re-auth (FR12–13) gives Paul's bookmarkable-URL journey everything it needs at zero CSP and session-management cost.
- **Deferred to.** **Deleted.** Not a Phase 5 candidate.
- **Reconsider if.** Persona research confirms a power-user segment with >10 re-auths/day.

## N-5. Multi-team-per-repository

- **Rationale.** One team per repository in v1 avoids ambiguity in `MAX()` role resolution and keeps the data model migrateable.
- **Deferred to.** Phase 5.
- **Reconsider if.** Support-ticket tag `multi-team-repo` accumulates ≥ 10 distinct users post-GA.

## N-6. Real-time deprovisioning / webhook-driven IdP-group sync

- **Rationale.** Login-time sync only. Procurement's immediate-revocation need is met by `is_active=false` (FR42 — implemented in Story 5-3 with ApiToken cascade). Real-time sync is SCIM-territory.
- **Deferred to.** Phase 5 (bundled with N-2 SCIM).
- **Reconsider if.** Procurement/compliance raises sub-hour revocation as a gating RFQ requirement.

## N-7. Paul the Product Owner persona

- **Rationale.** No interview, ticket, or telemetry evidence currently supports the Paul persona. Moved to PRD Appendix A (hypothesis).
- **Deferred to.** 60-day post-GA validation checkpoint decides.
- **Reconsider if.** At pilot customers, ≥ 3 non-engineering seats / customer / week log in and spend > 30 s on the reports view (measured via telemetry on `first_login_at` → `/reports` access).

## N-8. Self-service Team-admin UI beyond CRUD + membership

- **Rationale.** v1 covers Anita's canonical workflow (PRD Journey 2) without Team-level settings, custom notification rules, or Team-scoped dashboards.
- **Deferred to.** Phase 5.
- **Reconsider if.** Enterprise-customer feedback groups ≥ 3 Team-settings asks into a coherent theme.

## N-9. Additional OIDC providers beyond Azure AD / Google / GitHub

- **Rationale.** Okta, Keycloak, and generic OIDC ship via the admin-config abstraction already introduced in v1 — no v1 engineering blocker, just test-matrix expansion.
- **Deferred to.** Phase 5.
- **Reconsider if.** Design-partner RFQ names a specific provider not covered by the generic `oidc_generic` adapter.

## N-10. Organization-level hierarchy, fine-grained permission policies, delegated admin

- **Rationale.** Vision scope (see PRD → Product Scope → Vision).
- **Deferred to.** Vision.
- **Reconsider if.** A customer crosses 500 active users AND documents a "flat Team list is unmanageable" problem.

## N-11. Chrome Recorder extension changes (ApiToken semantics)

- **Rationale.** Chrome Recorder extension is explicitly not part of Phase 4. API-token-based authentication preserved unchanged (FR30, NFR28). Because `ApiToken.role` remains capped at `User.role` globally (not at `effective_role`), recorder users with Team-granted elevation will see a **smaller effective permission set via the recorder than via their SSO session**. This is a deliberate design decision (API tokens are machine identities, not human-session proxies). Verified by Story 3-15 regression test.
- **Deferred to.** Post-GA decision (Phase 5 candidate).
- **Reconsider if.** Support tickets tagged `recorder-team-scope` ≥ N (precise threshold TBD at 30-day review). If ≥ threshold → promote to a Phase-5 story. Else → cut.

---

## Phase 5 kickoff handoff

This section becomes the **explicit starting-point backlog** for Phase 5:

1. N-2 SCIM 2.0 + N-6 real-time deprovisioning (bundled).
2. N-1 SAML 2.0 (ships as Phase 4.5 release train).
3. N-5 multi-team-per-repo (only if N-5 reconsider-trigger fires).
4. N-8 self-service Team-admin UI (only if N-8 reconsider-trigger fires).
5. N-9 additional OIDC providers (test-matrix expansion, low risk).
6. N-11 recorder-Team-scope **IF** N-11 reconsider-trigger fires.

Items N-3, N-4 are **permanently deleted** unless a re-trigger fires first.
N-7 and N-10 are evidence-gated: validate first, promote only if the trigger condition materialises.

---

## Change log

- **2026-04-22** — Locked at Phase 4 Release-Gate. No drift during Phase 4 implementation (verified by Story 3-15 regression test for N-11 and by Story 5-3 cascade revocation for N-6's "login-time only" claim). (Story 5-11.)
