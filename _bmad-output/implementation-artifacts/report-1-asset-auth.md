# Story REPORT-1: Lock down `/reports/{id}/assets/` (no more anonymous reads)

Status: done

Epic: SECURITY — backlog from CLAUDE.md "Known open issues"
Story Key: `report-1-asset-auth`

## Reported

CLAUDE.md lists this as the first item under "Known open issues":

> unauthenticated `/reports/{id}/assets/`

The endpoint at `backend/src/reports/router.py:409` serves
screenshots and any other file from the run's output directory. Auth
is documented as **optional** today — the path-traversal check is the
only gate. Anyone who knows or guesses the report ID can pull
screenshots, terminal logs, etc.

## The fix, in one sentence

Reuse `_authenticate_flexible(token, credentials, db)` — the same
helper that already guards `/reports/{id}/html` and `/reports/{id}/zip`
— so the asset endpoint accepts either a Bearer header or a
`?token=<jwt>` query parameter and rejects everything else.

## Why query-token is enough

The two anonymous-asset code paths today are:

1. **Iframe-loaded HTML reports**. `/reports/{id}/html` already
   authenticates via `?token=<jwt>` and rewrites the HTML to inject
   `<base href="/api/v1/reports/{id}/assets/">`. Per RFC 3986 §5.2.2
   (Transform References), a relative URL with no query inherits the
   *base* URL's query. So changing the base to
   `<base href="/api/v1/reports/{id}/assets/?token={raw_token}">`
   propagates the JWT into every relative asset request the browser
   makes from inside that iframe — without rewriting individual
   `<img src>` tags.

2. **SPA-rendered `<img>` tags** in `KeywordNode.vue` and
   `ReportXmlView.vue` (via `getReportAssetUrl`). These currently
   build a URL with no auth. Update the helper to append the JWT
   from `localStorage`.

We accept that the JWT lands in browser history / server access logs
under this scheme — that's already true for `/zip` and `/html`.
CLAUDE.md tracks "JWT in download URL" as a separate, larger issue;
introducing a purpose-built short-lived asset token is out of scope
here.

## Acceptance Criteria

1. **AC1 — Endpoint requires auth.** `GET /reports/{id}/assets/{path}`
   calls `_authenticate_flexible(token, credentials, db)` *before* any
   path / file logic. No `?token` and no Bearer → 401.

2. **AC2 — HTML report embeds JWT in `<base href>`**. The
   `/reports/{id}/html` handler already has `raw_token` in scope after
   `_authenticate_flexible`. Surface it from the helper (refactor to
   return `(user, raw_token)`) and inject into the base tag URL.

3. **AC3 — SPA `getReportAssetUrl` injects JWT.** `frontend/src/api/reports.api.ts`
   helper reads the access token from localStorage (same key the
   axios interceptor uses) and appends `?token=...` to the returned
   URL. The two existing call sites (KeywordNode, ReportXmlView)
   need no changes — they call `getReportAssetUrl()` and use the
   string directly.

4. **AC4 — Path traversal still rejected.** The existing
   `requested_path.relative_to(output_dir)` check stays; auth is
   layered *on top*.

5. **AC5 — Tests.**
   - `test_asset_endpoint_rejects_anonymous` — no token, no Bearer → 401.
   - `test_asset_endpoint_accepts_query_token` — valid `?token=<jwt>` → 200.
   - `test_asset_endpoint_accepts_bearer` — valid `Authorization:` header → 200.
   - `test_asset_endpoint_rejects_invalid_token` — garbage `?token=` → 401.
   - `test_asset_endpoint_rejects_expired_token` — past-expiry token → 401.
   - `test_asset_endpoint_path_traversal_still_blocked` — auth'd
     traversal attempt → 403 (regression guard for AC4).
   - `test_html_report_base_href_contains_token` — render the HTML
     and assert the `<base href>` query includes the access token.

## Out of scope (V1)

- **Purpose-built asset token** with HMAC signature, short TTL, no
  user identity. Right answer in the long run; a separate story.
- **Audit log entry** for every asset fetch. Could drown the audit
  table on a single screenshot-heavy report. Defer.
- **Per-report ACL** (only members of the run's team can read its
  assets). Layered on top of auth, not replacing it. Defer.
- **CSRF on `/assets/`**. GETs are safe-by-method; the JWT in the
  URL is the cap.

## Risk notes

- **JWT exposure in browser history / server logs**. Pre-existing
  for `/html` and `/zip`. The token's 15-minute access-token TTL
  bounds the blast radius. This story doesn't make it worse.
- **localStorage read in `getReportAssetUrl`**. The function is
  called synchronously during template render. `localStorage.getItem`
  is synchronous in the browser, so no async churn — but if
  `localStorage` is unavailable (rare; some embedded contexts), the
  helper falls back to the un-tokenised URL and the request 401s
  as expected.
