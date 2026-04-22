# Deferred Work

## Deferred from: code review of 1-1-database-migration-for-phase-4-models (2026-04-15)

- Role strings hardcoded as `"viewer"` without `Role` constants in `teams/models.py` and `auth/models.py` — pre-existing pattern across codebase; harmonize when Role enum is formalized.
- Dual migration paths (`database.py` ad-hoc + Alembic) not fully idempotent — pre-existing pattern; Phase-4 extends it consistently; address holistically if divergence causes issues in CI.
- No TTL cleanup mechanism for `OidcLoginAttempt` rows — cleanup job scoped to Story 1.9 (discovery-cache-refresh-apscheduler-job).
- `IdentityProvider.provider_type` has no `CHECK` constraint or enum validation — service-layer validation concern; add when the OIDC flow service (Story 2.x) is implemented.
- `scopes` / `group_claim_name` stored as space-delimited strings without documented parse contract — design concern for service layer; add a property accessor / validation when Story 1.3 (IdP CRUD API) is implemented.

## Deferred from: code review of 1-6-admin-ui-idp-provider-list-view (2026-04-20)

- W1: AC7 color-contrast rule disabled in axe scan — brand color `--color-primary: #3B7DD8` fails WCAG AA 4.5:1 project-wide (sidebar, footer, buttons). Design-system issue, out of scope for Story 1.6. Structural a11y still enforced. Needs a dedicated design-system phase to remediate.
- W2: Router `minRole` guard skips check when `auth.user` is null — if `fetchCurrentUser` throws without logging out, a non-admin can briefly reach the admin URL and see a 403 toast instead of being redirected. Backend enforces 403; existing project-wide guard pattern.
- W3: Sidebar does not reactively hide when the admin role is demoted server-side — project-wide existing pattern; `navItems` is a computed but auth.user only updates on refresh/navigation.
- W4: `lastDryRunResult` in the store is never cleared between runs across different IdPs — planted for Story 1.7 to consume via a "last result" pane. Clear or scope-per-id when that surfaces.
- W5: E2E `cleanAllIdps` silently no-ops on `!listRes.ok()` — if the admin token ever gets rejected, test cleanup masquerades as clean. Low impact; CI flake vector only.

## Deferred from: code review of 1-5-encrypted-client-secret-storage (2026-04-17)

- W1: `test_client_secret_not_in_response_body` uses `"client_secret" not in resp.json()` which only checks top-level dict keys — brittle if a future response shape nests the IdP under a `data` envelope. Current schema is flat and the `SECRET not in resp.text` check catches string-level leaks, so low-value to tighten now.
- W2: No logger.warning / metric when `get_decrypted_client_secret` falls through to the legacy-plaintext branch — silent degradation. Revisit once SECRET_KEY rotation tooling is designed (likely Story 5.x hardening).
- W3: `test_client_secret_not_in_logs` uses `caplog` which is root-logger + thread-local by default. Background daemon-thread logs (e.g., audit middleware's `logger.debug` on exception) and any future logger with `propagate=False` would slip through. No known current leak; tighten when a daemon-thread logger actually touches secrets.
- W4: Audit middleware swallows ALL exceptions at `middleware.py:110, 125` — there is no regression test that an audit row actually lands for a successful request. Out of scope for Story 1.5; separate audit-middleware health concern.
- W5: Legacy-fallback test does not assert `idp.client_secret_encrypted` stays plaintext after commit. Would only matter if a SQLAlchemy event hook were later added to auto-encrypt on flush. Not present today.

## Deferred from: code review of 1-4-dry-run-probe-endpoint (2026-04-17)

- W1: Service/router persistence pattern — `probe_idp_discovery` does `db.flush()` + `db.refresh(idp)` inside the service, commit happens in the router. If the router's commit fails after the probe returned, the `DryRunProbeResponse` reports success but the DB mutation is rolled back. Project-wide convention; commit failure on these columns is extremely unlikely. Revisit if any phase-4 service hits a real commit race.
- W2: No rate limiting on `POST /{idp_id}/dry-run` — admin-only endpoint can trigger unlimited outbound HTTP, viable as a port-scanner via timing. Consistent with other IdP endpoints; rate-limit policy for admin endpoints is a cross-cutting decision owned by Story 2.8 (SSO rate limiting).
- W3: `test_dry_run_rbac_forbidden` calls `/1/dry-run` without seeding an IdP at id=1 — relies on RBAC dependency firing before handler body. Works today; project pattern (same as Story 1-3 review finding). Low regression risk.
- W4: `except httpx.HTTPError` block catches `httpx.InvalidURL`/`UnsupportedProtocol` and surfaces the "Check firewall and egress rules" detail — operator gets misleading guidance for what is actually a malformed `issuer_url`. Pydantic validates URL format on API input; impact is minimal for the common flow.
- W5: `issuer_url` whitespace/newline not normalised — Pydantic validator only checks `startswith("http")`, so `"https://idp.local\n"` survives. Produces `httpx.InvalidURL` at probe time (caught by W4 path). Low-probability legacy-data issue.

## Deferred from: code review of 1-3-identity-provider-crud-api (2026-04-16)

- W1: Audit middleware logs `client_secret` in plaintext in `AuditLog` for POST/PATCH to IdP endpoints — pre-existing behavior; requires a sanitization layer in the audit middleware to redact sensitive fields before persisting.
- W2: `scopes` and `group_claim_name` fields have no format or pattern validation beyond max_length — future hardening, low immediate risk.
- W3: `test_delete_idp` has no assertion that related `idp_group_mappings`/`oidc_login_attempts` rows are CASCADE-deleted — verify once those tables have data populated (Story 2.x scope).
- W4: No 404 tests for PATCH and DELETE on non-existent IdP resource — nice-to-have, not required to ship.
- W5: Deletion of an enabled (`is_enabled=True`) IdP is not guarded at the application layer — could interrupt active OIDC flows; gate deletion on `is_enabled=False` check when IdP enable/disable is wired up in Story 1.7.

## Deferred from: code review of 1-2-mock-oidc-test-fixture (2026-04-15)

- Module-level RSA keygen runs on every pytest collection (~50-300ms cost even for non-OIDC tests) — spec Task 2 explicitly prescribes import-time generation for hermetic tests; revisit if CI collection becomes slow.
- `handle_token` ignores request body — no validation of `grant_type` / `code` / PKCE verifier; masks client-side bugs. Extend when Story 2.1/2.2 callback handler tests need request-param assertions.
- `conftest.py` re-export in `tests/fixtures/` only auto-applies fixtures to subtree — tests outside `tests/fixtures/` must import directly. Revisit when SSO integration tests land in `tests/auth/`.
- respx async-interception path not exercised — 4 smoke tests all use sync `httpx`; production SSO callback in Story 2.1+ will use `AsyncOAuth2Client`. Covered implicitly by Story 2.1+ integration tests.
- Token response lacks `refresh_token` and `scope` fields — authlib clients may trigger warnings or skipped code paths. Add when a consumer needs them.
- `with_claims()` cannot un-set a default — no way to test "missing claim" rejection path of consumer. Add negative-test support when Story 2.2 needs it.
- `_build_claims()` clears `_pending_claims` on every call — second token exchange silently returns defaults, masking multi-exchange test bugs. Revisit when refresh/re-auth tests are written.
- `_CLIENT_ID` hardcoded as `aud` — any SUT configured with a different client_id will fail audience validation. Parameterize when Story 1.3 IdP CRUD defines real client_ids.

## Deferred from: code review of 1-10-tls-nginx-csp-return-to-validation (2026-04-21)

- SSRF via `jwks_uri` to internal network ranges — `_validate_https` only checks `http://` prefix; hostile discovery doc can point JWKS to AWS IMDS or RFC-1918 addresses. Pre-existing in Story 1-4 probe code.
- No rate limiting on `GET /auth/sso/{idp_id}/login` — unauthenticated endpoint triggers discovery fetch on cold cache; DoS vector. Story 2-8 covers SSO rate limiting.
- `_MAX_RESPONSE_SIZE` check fires after full body is buffered — hostile IdP can exhaust process memory. Pre-existing in `_fetch_json_object`.
- `get_or_fetch_discovery` concurrent calls race — two simultaneous login requests both see stale cache, issue duplicate outbound fetches, and conflict on DB commit. Story 2-1 concern.
- `///evil.com` safety relies on `urlparse` returning empty scheme — no explicit triple-slash guard; correct today but fragile across future Python versions.
- `_ALLOW_INSECURE_IDP` evaluated at module import — `monkeypatch.setenv` after import does not update the flag; blocks test isolation for the insecure-IDP code path.
- Naive/aware datetime mismatch in discovery cache TTL — works on SQLite; PostgreSQL with `TIMESTAMP WITH TIME ZONE` may silently compute wrong TTL delta.
- HSTS `preload` directive on `server_name _` catch-all — production deployments must set `server_name` to canonical domain or preload propagates to arbitrary hostnames.

## Deferred from: code review of 1-9-discovery-cache-refresh-apscheduler-job (2026-04-21)

- Concurrent refresh race condition (manual endpoint + scheduled job on same IdP simultaneously) — acceptable for admin-only tooling with few IdPs; revisit if multi-IdP prod deployments show conflicts.
- Cache JSON schema validation missing in `get_or_fetch_discovery()` — Story 2-1 is responsible for validating the returned discovery doc before using OIDC endpoints.
- APScheduler non-retry on unhandled exception from `refresh_discovery_cache()` — pre-existing APScheduler behavior; job must be manually re-triggered after a session-level failure.

## Deferred from: code review of 1-7-admin-ui-idp-provider-edit-view-with-inline-dryrunpanel (2026-04-21)

- Scope chips silent deduplication — no user feedback when a duplicate scope is entered; UX polish for a future story.
- `initialForm` diverges from server truth after a failed PATCH during dry-run — low-risk in practice as stale detection uses `lastDryRunAtForm`; revisit if multi-step edit flows expose a bug.
- Missing Vitest coverage for stale revert paths — no test exercises reverting a mutated field back to its dry-run snapshot value, or multi-field mutation sequences.
- `loadExisting()` silent failure — if `getIdp()` throws, the form renders empty without an error banner; consistent with other views but should get an error state in a UI-polish pass.

## Deferred from: code review of 2-1-oidc-authorization-code-flow-initiation (2026-04-21)

- Stale `OidcLoginAttempt` rows never purged — every initiation INSERTs a row; no reaper deletes `expires_at < now()`. Retention belongs in Story 5-5 APScheduler jobs.
- `get_or_fetch_discovery` commits the outer session mid-request (`backend/src/auth/oidc_discovery.py:300`) — leaks transactional ownership from the caller; fixing it changes semantics for the `discovery_refresh` scheduler. Story 1-9 architectural issue.
- Handoff generator emits `/auth/sso/callback` instead of `/api/v1/auth/sso/callback` (`backend/src/auth/handoff_generator.py:220`) — admins using the artifact to register the IdP get `redirect_uri_mismatch` on callback. Story 1-8 bug, pre-existing.
- Naive/aware datetime mixing in discovery cache TTL check (`backend/src/auth/oidc_discovery.py:290-292`) — cross-cutting timezone issue; migrate columns to `DateTime(timezone=True)` in a dedicated pass.
- Broad `except Exception` in `get_or_fetch_discovery` (`backend/src/auth/oidc_discovery.py:304`) — masks programming errors as "IdP unreachable". Narrow to `httpx.HTTPError`, `json.JSONDecodeError`, `OSError`.
- `request.base_url` used to derive `redirect_uri` trusts the `Host` header — matches the spec for Story 2-1, but production deployments should gain `TrustedHostMiddleware` or a `settings.public_base_url`. Separate hardening item.
- `SsoProviderPublic.provider_type` typed as `str` rather than `Literal[...]` — schema refinement, not a bug.
- `/providers` returns ORM objects with `from_attributes=True` — currently safe (3 scalar columns), but if someone adds a relationship to `SsoProviderPublic` it could detach-load. Project to tuple form if/when that becomes a concern.
- Route ordering fragility if `idp_id: int` is ever changed to `str` — would let `/sso/providers/login` match the dynamic route. Add regression test only when schema changes.

## Deferred from: code review of 2-2-sso-callback-handler-with-inline-group-sync (2026-04-21)

- `get_or_fetch_discovery` inner `db.commit()` (re-noted; first raised in Story 2-1 review) — architectural cleanup of `oidc_discovery.py:300`.
- Hardcoded `token_endpoint_auth_method="client_secret_post"` — extend `IdentityProvider` with a per-IdP auth method to support `client_secret_basic` and public-client PKCE (required by some Keycloak / Azure AD B2C configs).
- Broad `except Exception` in `_exchange_code` — narrow to `OAuthError`/`OAuth2Error` after an audit of the authlib error taxonomy; right now programming bugs get reported as "token.invalid".
- Response-size caps on token and JWKS fetches — mirror Story 2-1's `_MAX_RESPONSE_SIZE = 1_000_000` via custom httpx transport.
- JWKS cache per IdP — every callback currently fetches JWKS; hot-path DoS surface + upstream rate-limiting risk.
- JWKS rotation mid-flow + 304 Not Modified handling — retry-once on signature-invalid after bypass-cache refetch.
- Group claim dotted-path traversal (Keycloak `resource_access.<client>.roles` pattern) and non-list group shapes (space-separated strings).
- N+1 manual-grant check in `_sync_team_memberships` — batch SELECT for manual rows per user.
- Team FK violation when team deleted mid-flow and SQLite `PRAGMA foreign_keys=OFF` — JOIN mappings against `teams` during sync.
- Non-deterministic role ordering when `IdPGroupMapping` pairs collide on the same team — pick highest-privilege deterministically.
- Email case-sensitivity collision (SQLite default + Postgres without `citext`) — migration job + case-insensitive unique index.
- X-Forwarded-For IP extraction for audit rows (affects all `log_event` callers; not Story 2-2 specific).
- Email PII in `sso.login.success` audit `detail` — consider hashing / omitting for long retention policies.
- Cookies not cleared on failure redirect — `delete_cookie` on error path.
- `Pragma: no-cache` header on callback redirect — complements `Cache-Control: no-store`.
- `SameSite=Lax` vs future `response_mode=form_post` support — document as unsupported today.
- `secure=True` cookies silently dropped over HTTP in dev — detect `X-Forwarded-Proto` and warn.
- `TeamMember.source` / `IdPGroupMapping.role` — replace magic strings with enums validated at write time.
- Empty `team.member.synced_from_idp` audit event emitted when no changes — log-noise cleanup.
- AC6 commit-order numbered-sequence contradicts the spec's own reference snippet — spec author to clarify; impl follows the reference.
