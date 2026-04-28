# Story SECURITY-1: Force the seed admin to change the default password on first login

Status: done — revised after user feedback (no more forced modal)

## Post-merge revision (2026-04-28)

User feedback: *"in vielen lokalen fällen ist es irrelevant. nimm
diesen force change raus, und zeig das nur irgendwo an (nicht als
fehler, eher als gelber hinweis)"*

The blocking modal was the wrong shape — it makes a single-user
local install feel broken. Walked back to a non-blocking yellow
banner.

**What stayed (backend):**
- `User.password_change_required` column + migration.
- `ensure_admin_exists` still sets the flag on fresh and legacy admins.
- Login still emits a WARNING to `roboscope.auth` so the operator
  sees the unfinished rotation in their log stream.
- `POST /auth/change-password` endpoint is still there — useful as a
  general self-service feature, not just for forced rotation.

**What changed (frontend):**
- `ForcePasswordChangeModal.vue` → renamed to `ChangePasswordModal.vue`
  and made *opt-in* (caller controls `v-model`).
- New `DefaultPasswordBanner.vue` shown at the top of the app layout
  when the flag is true. Yellow, dismissable per-session via
  `sessionStorage`. Click → opens the (now opt-in) modal.
- i18n keys renamed: `auth.forcePwChange.*` → `auth.pwChange.*`;
  added `auth.defaultPwBanner.*` for the new banner.
- Mounted `DefaultPasswordBanner` between `AppHeader` and the main
  content slot in `DefaultLayout.vue`. Removed the old layout-level
  forced modal mount.

The 12 backend tests stay green — the API surface and DB behaviour
didn't change.

Epic: SECURITY — backlog from CLAUDE.md "Known open issues"
Story Key: `security-1-force-default-admin-password-change`

## Reported

CLAUDE.md "Known open issues" lists:

> default-credentials probe on login

The seed admin is hard-coded as `admin@roboscope.local` /
`admin123` (`backend/src/auth/service.py:130`). On any deployment
where ops forgot to change the default password, an attacker can
just try those credentials. We have no current mechanism to detect
or force a change.

## The fix

1. Mark the seed admin with a new flag `password_change_required=True`.
2. Surface the flag in `/auth/me`.
3. Add `POST /auth/change-password` (current + new password). On
   success, clear the flag.
4. Frontend gates the rest of the app behind a forced
   change-password modal whenever the flag is `true` for the
   logged-in user.
5. Server logs a `WARNING` when login succeeds with
   `password_change_required=True` (so the operator sees the
   reminder in their logs).

This pattern composes with the existing `first_login_complete` Phase-4
flag — they're orthogonal: `password_change_required` blocks app
access; `first_login_complete` only gates the welcome UI.

## Acceptance Criteria

1. **AC1 — Column.** `User.password_change_required: bool` (default
   `False`). Migration adds the column for SQLite + Postgres in the
   existing lightweight-migration block.

2. **AC2 — Seed admin marked.** `ensure_admin_exists` sets
   `password_change_required=True` so a fresh deployment lands on
   the modal immediately.

3. **AC3 — Endpoint.** `POST /auth/change-password` accepts
   `{current_password, new_password}` JSON. Validation:
   - `current_password` must verify against the hash, else 401.
   - `new_password` must be ≥ 8 chars and not equal to
     `current_password`, else 422.
   - On success: `hashed_password` updated,
     `password_change_required = False`, audit event
     `auth.password_changed` written.

4. **AC4 — Surface in /auth/me.** `UserResponse.password_change_required: bool`
   added. Existing clients ignoring the new field still work.

5. **AC5 — Server log warning.** When a user with
   `password_change_required=True` authenticates,
   `roboscope.auth` logs a `WARNING`:
   `Login by user=<email> with password_change_required=True — operator must complete the rotation.`

6. **AC6 — Frontend modal.** A new `ForcePasswordChangeModal.vue`
   blocks app interaction when the flag is `true`. Mounted at the
   layout level so it fires on every authenticated page. After a
   successful change it hides itself and the auth store's user
   object reflects the cleared flag.

7. **AC7 — i18n.** Modal text + change-password labels translated
   in EN/DE/FR/ES.

8. **AC8 — Tests.**
   - `test_seed_admin_starts_with_password_change_required` — fresh DB,
     `ensure_admin_exists`, assert the seed admin row has the flag.
   - `test_change_password_clears_flag` — happy path through the
     endpoint.
   - `test_change_password_rejects_wrong_current` — 401.
   - `test_change_password_rejects_short_new` — 422.
   - `test_change_password_rejects_same_as_current` — 422 (defensive
     against "I'll change it back later" pattern).
   - `test_login_logs_warning_when_flag_set` — capture loglevel.
   - `test_me_includes_flag` — both states.

## Out of scope (V1)

- **Password complexity policy** (uppercase / digits / symbol). Pure
  length floor for V1. A configurable policy is a follow-up.
- **Force change on every user**, not just the seed admin. Some
  organisations actually want predictable demo-instance
  credentials. We only force on the seed admin.
- **Rate limiting on `/auth/change-password`**. Already covered by
  the global rate limiter (`@limiter.limit(...)`) — reuse it, don't
  invent a new layer.
- **Refuse to start with default password env-vars unset**. That's
  a deploy-time check — separate story.

## Risk notes

- **Existing deployments where the admin already changed their
  password but never set the new flag.** They wouldn't have the flag
  set on their row, so the modal never fires. Correct — they're not
  using defaults.
- **Existing seed admins from before this story.** They DO have the
  default password and now also need the flag. The migration block
  detects this case: when `ensure_admin_exists` runs and finds an
  existing admin row whose `verify_password("admin123", hash)` is
  true, it flips the flag on. This is a one-shot pessimistic
  upgrade — safe because `verify_password` is constant-time bcrypt.

## Implementation phases

This is one story, one commit. No need for phased delivery.
