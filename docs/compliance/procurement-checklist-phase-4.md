# RoboScope — Procurement & Security Review Checklist (Phase 4)

**Document status:** canonical response as of Phase 4 Release-Gate (2026-04-22).
**Audience:** Sales/Security-Review liaison answering vendor questionnaires.
**Scope:** RoboScope v0.9.x (the Phase 4 release). Items marked "deferred" identify the concrete successor version — see `_bmad-output/planning-artifacts/non-goals-v1-lock.md` for trigger conditions.

Copy-paste-safe answers — each row is self-contained.

---

## Identity & Access Management

| # | Question | Answer |
|---|---|---|
| 1 | **OIDC (OpenID Connect) support.** Which OIDC providers are supported out of the box? | Azure AD (Entra ID), Google Workspace, GitHub. A "generic OIDC" adapter supports any conformant OIDC 1.0 / OAuth 2.0 authorization-code-flow provider via admin UI configuration. |
| 2 | **SAML 2.0 support.** | **Not in Phase 4.** Explicitly deferred to Phase 4.5 due to `xmlsec` C-dependency incompatibilities with slim Docker images and Windows dev environments. A dedicated Phase 4.5 release will add SAML. Local-login fallback covers any pre-4.5 deployments. |
| 3 | **SCIM 2.0 user/group provisioning.** | **Not in Phase 4.** Deferred to Phase 5. Forward compatibility preserved via stable `external_id` columns on `Team` and `TeamMember`. Phase-4 sync is login-time based on IdP group claims. |
| 4 | **MFA (multi-factor authentication).** | Delegated to the IdP. RoboScope does not maintain credentials beyond the optional local admin account (see §12); all MFA policy, enrollment, and enforcement is the IdP's responsibility. Passes your existing MFA / conditional-access policies through transparently. |
| 5 | **Single Sign-On enforcement.** | Admin setting `hide_local_login_form` (Story 2-5) removes the email/password form from the login page. An emergency bypass toggle (`sso_emergency_bypass`) can re-enable local login for outage recovery (see §15). |
| 6 | **JIT provisioning.** | Yes. First successful SSO login auto-creates the `User` row with VIEWER role. Elevation to RUNNER/EDITOR/ADMIN is explicit — via IdP-group → Team mapping (configured by admin) or direct role grant. |

## RBAC

| # | Question | Answer |
|---|---|---|
| 7 | **Role model.** | Four-level hierarchy: VIEWER (0) < RUNNER (1) < EDITOR (2) < ADMIN (3). User's effective role on a given repository is `MAX(global, team, project)` — additive, never demoting. Team membership can grant but never revoke. |
| 8 | **Fine-grained permissions.** | Not in Phase 4. The four-level hierarchy is the enforcement surface. Finer-grained policies are Vision scope. |
| 9 | **Delegated admin.** | Not in Phase 4 (deferred). ADMIN role is installation-wide today. |
| 10 | **API tokens.** | Supported. `rbs_…` prefixed bearer tokens with a scoped role per token. The scoped role is capped at the owner's global `User.role` at every request; Team grants do NOT elevate API-token access (verified by regression tests in `backend/tests/auth/test_api_token_cap.py`). Tokens are SHA-256 hashed at rest — only the prefix and hash are stored, never the plaintext. |

## Audit & Compliance

| # | Question | Answer |
|---|---|---|
| 11 | **Audit log capture.** | All POST/PUT/PATCH/DELETE requests are auto-logged by audit middleware to `audit_log` with user id, action, resource type/id, IP, timestamp, detail JSON. Phase-4-specific events use a typed `AuditEventType` StrEnum (15 members covering SSO login success/failure, rate limiting, team / team-member / group-mapping lifecycle, repository-team assignment, user deactivation). |
| 12 | **Audit log export.** | CSV and JSON export via `GET /api/v1/audit/export`. Filtered by user, action, resource type, date range. |
| 13 | **Audit log retention.** | Daily APScheduler job enforces `report_retention_days` (configurable, default 90). Phase-4-specific hourly cleanup removes expired `OidcLoginAttempt` rows and stale `RateLimitCounter` rows so auth tables don't grow unbounded (Story 5-5). Audit rows themselves retained per the same retention policy. |
| 14 | **Session invariance on user deactivation.** | Admin flipping `User.is_active` to false (via `PATCH /users/{id}` or `DELETE /users/{id}`) cascade-revokes all of the user's API tokens in the same transaction and emits `user.deactivated` audit with cascade count (Story 5-3). `get_current_user` and `_authenticate_api_token` re-check `is_active` on every request — deactivation propagates at the next request. |
| 15 | **Emergency bypass auditability.** | The `sso_emergency_bypass` toggle has an auto-expiry timestamp (`sso_emergency_bypass_expires_at`). Any activation, deactivation, or auto-expiry is captured in the audit log. |

## Data Protection

| # | Question | Answer |
|---|---|---|
| 16 | **Data residency.** | Self-hosted — you pick the region. Docker images run on your infrastructure; there is no hosted SaaS control plane. |
| 17 | **Secret encryption at rest.** | Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) keyed from the `SECRET_KEY` environment variable. Applied to: `IdentityProvider.client_secret_encrypted`, `OidcLoginAttempt.pkce_verifier`, `Environment` env-vars flagged `is_secret=True`. Legacy plaintext values continue to decrypt without re-keying (graceful migration). |
| 18 | **Secret encryption in transit.** | TLS 1.2+ enforced on outbound IdP calls via a dedicated `ssl.SSLContext` (NFR13, Story 1-10). Production nginx reverse-proxy configured with HSTS, per-request CSP nonces, and `frame-ancestors 'none'`. Inbound TLS termination is the operator's responsibility (nginx config provided). |
| 19 | **Password storage.** | bcrypt (work factor 12) via `passlib`. Used only for the initial admin seed account and any local-login users that remain after SSO is configured. |
| 20 | **PII minimisation.** | Only the `email` and `username` from the OIDC claims are persisted on `User`. `email_verified=true` is required before a new user row is created (Story 2-2). No profile photos, no refresh-token storage (intentional — redirect re-auth instead). |

## Availability / Operational

| # | Question | Answer |
|---|---|---|
| 21 | **Session timeout configurability.** | JWT access tokens default to 15 minutes, refresh tokens to 7 days. Both are env-var configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`). `get_current_user` re-checks `is_active` every request so deactivation takes effect within the next request (no cache). |
| 22 | **IdP-outage behavior.** | JWT validation is stateless — existing sessions continue during an IdP outage. New logins fail gracefully with a localized error code (`idp.unreachable`) and the configured `admin_contact_email`. An admin can toggle `sso_emergency_bypass` to temporarily re-enable local login; the bypass auto-expires at `sso_emergency_bypass_expires_at`. |
| 23 | **Offline boot.** | Zero outbound calls at boot (NFR15/AR16). The IdP discovery cache refresh is deferred 24 h after boot so air-gapped / restricted-egress installations do not crash on startup. Verified by `tests/test_boot_invariant.py`. |
| 24 | **Rate limiting.** | Per-IP failure window on SSO endpoints (configurable threshold, 5-min window) with 429 + `Retry-After`. Currently trusts `request.client.host`; deployments behind a proxy should terminate TLS at the reverse proxy and ensure the proxy's `X-Forwarded-For` is enabled (the XFF-aware helper is tracked as a Phase 5 hardening item in `deferred-work.md`). |

## Supply Chain / Build

| # | Question | Answer |
|---|---|---|
| 25 | **SBOM (Software Bill of Materials).** | Generated per release by the existing release pipeline (SPDX + CycloneDX formats). Python dependencies locked via `uv.lock`; frontend via `package-lock.json`. |
| 26 | **Reproducible builds.** | Yes — Docker multi-stage builds with pinned base image digests, frozen lock files. Offline wheel bundles resolved for Linux + macOS + Windows in the release-tasks flow. |
| 27 | **Third-party OIDC library.** | `authlib` (maintained, widely used, pure Python). `cryptography` (hazmat backend, OpenSSL-backed). `respx` for test hermeticity (dev-only). |

## Non-Goals (explicit — see `non-goals-v1-lock.md` for full rationale)

| # | Capability | Phase-4 Status | Target |
|---|---|---|---|
| N-1 | SAML 2.0 | Not included | Phase 4.5 |
| N-2 | SCIM 2.0 | Not included | Phase 5 |
| N-3 | Per-user local-login override | Deleted | (trigger-gated reconsider) |
| N-4 | Silent token renewal (iframe / refresh) | Deleted | (trigger-gated reconsider) |
| N-5 | Multi-team-per-repository | Not included | Phase 5 (if trigger fires) |
| N-6 | Real-time deprovisioning / SCIM push | Not included | Phase 5 (bundled with SCIM) |
| N-9 | Okta / Keycloak adapters | Not included (generic OIDC works) | Phase 5 test-matrix expansion |

---

## Appendix A — Standards & Specifications

- OIDC 1.0 Authorization Code Flow + PKCE (RFC 7636)
- ID-token verification: RS256/ES256 pinned (no `HS*`, no `none`), issuer + audience + `azp` (per OIDC Core §3.1.3.7 for multi-value aud), nonce, `email_verified=true`, signature against JWKS
- Bearer token: RFC 6750
- TLS: 1.2+ enforced on outbound IdP connections
- Cookie flags: `HttpOnly`, `Secure`, `SameSite=Lax` on callback-set session cookies

## Appendix B — Security contact

Security issues should be reported to the email listed in the repository `SECURITY.md` (if present) or opened as a private advisory on the GitHub project `viadee/roboscope`.

## Change log

- 2026-04-22 — Created at Phase 4 Release-Gate (Story 5-8). Synced to: commits `4ca7d0f` (identity foundation), `c8c171b` (Epics 2+3), `4403dad` (Story 5-3 deactivation cascade), `ec3094f` (Story 3-15 API-token cap), `d55efda` (non-goals lock).
