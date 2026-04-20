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
