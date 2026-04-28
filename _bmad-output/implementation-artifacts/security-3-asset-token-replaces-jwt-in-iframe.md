# Story SECURITY-3: Replace JWT-in-URL with a signed asset token (iframe path)

Status: done

Epic: SECURITY — backlog from CLAUDE.md "Known open issues"
Story Key: `security-3-asset-token-replaces-jwt-in-iframe`

## Reported

CLAUDE.md "Known open issues":

> JWT in download URL

REPORT-1 (`84c8ae6`) closed the anonymous-asset hole by requiring
auth on `/reports/{id}/assets/`. To keep iframe-loaded HTML reports
working it embedded the user's JWT in `<base href="…?token=<JWT>">`.
That works, but the JWT is:
- the user's full access token (15-min TTL, encodes user ID),
- carried in the iframe URL → ends up in browser history,
  bookmarks, share links, and server access logs.

The fix is a purpose-built **asset token**: HMAC-signed with the
server's `SECRET_KEY`, scoped to a single report ID, 1-hour TTL,
no user identity. Any of those URLs leaking out only grants
read-only access to the assets of one report for one hour.

## Bounding for V1

We change *only* the iframe path:

- `/reports/{id}/html` mints an asset token and embeds `?at=<token>`
  in the HTML's `<base href>`.
- `/reports/{id}/assets/{path}` accepts the asset token *in addition
  to* the existing JWT and Bearer auth.

SPA-rendered `<img>` tags (KeywordNode, ReportXmlView) keep using
`getReportAssetUrl` → `?token=<JWT>` for now. They land only in
server logs (img sub-resources don't enter browser history), which
is a smaller exposure surface; a follow-up story can move the SPA
side over to asset tokens once a Pinia cache is wired up.

## Acceptance Criteria

1. **AC1 — Mint helper.** New `src/reports/asset_tokens.py`:
   - `mint_asset_token(report_id: int, ttl_seconds: int = 3600) -> str`
   - `verify_asset_token(token: str, report_id: int) -> bool` —
     returns True iff signature valid AND not expired AND
     report_id matches.
   - Uses HMAC-SHA256 over `f"{report_id}:{expiry}"` with
     `settings.SECRET_KEY`. Token format: base64url
     of `payload.signature`.

2. **AC2 — Asset endpoint accepts the new token.** Behaviour matrix:

   | Header | `?token=` (JWT) | `?at=` (asset) | Result |
   |---|---|---|---|
   | Bearer | — | — | 200 |
   | — | valid JWT | — | 200 |
   | — | — | valid asset, matching report_id | 200 |
   | — | — | valid asset, *wrong* report_id | 401 |
   | — | — | expired asset | 401 |
   | — | — | tampered asset | 401 |
   | — | — | — | 401 |

3. **AC3 — `/html` injects asset token.** The `<base href>` in the
   served HTML reads `…/assets/?at=<asset_token>` instead of
   `…/assets/?token=<jwt>`. Asset URLs resolved by relative paths
   under that base inherit the `?at=…` per RFC 3986 §5.2.2.

4. **AC4 — Existing JWT path stays functional.** The asset endpoint
   still accepts `?token=<jwt>` (used by SPA `<img>` tags). No
   breakage for callers that haven't migrated.

5. **AC5 — Tests.**
   - `test_mint_and_verify_round_trip`
   - `test_verify_rejects_wrong_report_id`
   - `test_verify_rejects_expired`
   - `test_verify_rejects_tampered_signature`
   - `test_verify_rejects_garbage`
   - `test_assets_accepts_asset_token`
   - `test_assets_rejects_asset_token_for_other_report`
   - `test_html_base_href_uses_asset_token_not_jwt`

## Out of scope (V1)

- **Migrating SPA `<img>` tags off JWT.** Needs a Pinia
  `assetTokens` store + per-report fetch + render-after-loaded
  awaiting. Separate story.
- **Revocation.** Asset tokens are stateless — once minted, valid
  until expiry. To revoke, rotate `SECRET_KEY` (which invalidates
  every active access JWT too).
- **Per-user audit on asset reads.** The token doesn't carry user
  identity by design. If we later need that, add the user to the
  payload as a non-cryptographic claim, but auditing every
  screenshot read is its own story.

## Risk notes

- **Clock skew.** `time.time()` on the server is used for both mint
  and verify, so single-host clock drift is harmless. Multi-instance
  deployments only break if instances disagree by > TTL — operations
  problem, not crypto.
- **`SECRET_KEY` rotation.** When the operator rotates the key,
  every minted-but-unexpired asset token instantly invalidates
  (same as JWTs). Acceptable.
- **Token length.** ~120 chars base64url. Long URLs but well below
  any browser / proxy limit.
