# Demo Scenarios — Area A: Auth, RBAC & Identity

Seed: fresh install; seed admin `admin@roboscope.local` / `admin123`.

---

### Password login + session — A
Happy path: `/login` → enter admin creds → **Anmelden** → `/dashboard`.
Edge cases:
  - Wrong password → inline error (shake), stays on `/login`.
  - **Rate limit**: 10 failed attempts / 5 min / IP → blocked with message.
  - Invalid email format → field validation.
  - Token expiry mid-session → 401 interceptor redirects to `/login`
    (no redirect loop — guarded on `pathname !== '/login'`).
Capture: `auth.spec.ts`.

### RBAC tiers (VIEWER < RUNNER < EDITOR < ADMIN) — A
Demo: create one user per role (Settings → Users), log in as each.
  - VIEWER: Explorer read-only banner; Run button disabled (tooltip
    "RUNNER-Rolle nötig"); no Recorder/Environments cards.
  - RUNNER: can start runs, can't edit files.
  - EDITOR: full editor + recorder + environments.
  - ADMIN: Settings / Identity Providers / Teams / Emergency Bypass.
Edge cases: role downgrade mid-session → next gated action denied.

### API tokens — A (admin)
Happy path: Settings → Tokens → **+ Token** (name, role, expiry) → token
  shown once (`rbs_…`) → use as `Authorization: Bearer` on any API call.
Edge cases: revoke → token rejected; expired token rejected; token capped at
  its scoped role (can't exceed).

### SSO / OIDC (Azure/Google/GitHub/generic) — A (admin)
Happy path: Admin → Identity Providers → **+ New** → fill issuer/client →
  **Dry-Run** (issuer reachable / discovery / JWKS checks) → **Test Login**
  shows decoded claims/groups → enable → SSO button on `/login`.
Edge cases:
  - Bad issuer URL / wrong client secret → dry-run fails with specific error.
  - IdP outage → `/sso-error` with retry + admin contact.
  - State expired (>10 min to consent) → friendly error.
  - First SSO login with no team → `/welcome` "request access" CTA.
Capture: `phase4-sso-login.spec.ts`, `idp-providers.spec.ts`,
  `phase4-accessibility.spec.ts` (axe).

### Teams + group→role mapping — A (admin)
Happy path: Admin → Teams → **+ New** or **Import from IdP groups** → add
  members with per-team roles → assign repos → TeamSwitcher in header.
Edge cases: 0 teams (empty state two CTAs); multi-team user switches context.

### Emergency SSO bypass — A (admin)
Happy path: Admin → Emergency Bypass → Activate (duration) → amber header
  banner with remaining time → Deactivate.
Edge case: bypass expires mid-session → banner disappears.
