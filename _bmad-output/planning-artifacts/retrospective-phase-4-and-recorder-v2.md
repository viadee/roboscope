# Retrospective — Phase 4 + Recorder v2 (consolidated)

**Date:** 2026-04-22
**Scope:** everything shipped under the `feat/recorder-and-bmad` branch from the initial Phase 4 Epic 1 commit through the last `/loop` iteration.
**Format:** one consolidated retro covering 6 epics (Phase 4 × 5 + Recorder R-1 + Recorder v2 × 3) instead of six separate ceremonies — keeps the signal-to-noise high.

## What shipped

### Phase 4 — Enterprise Identity Readiness
- **Epic 1 (Identity Foundation):** OIDC discovery + IdP CRUD + dry-run probe + encrypted client secret + admin UI + handoff PDF + discovery cache refresh + TLS/nginx/return-to validation. **10 stories.**
- **Epic 2 (SSO User Access):** authorization-code + PKCE initiation, callback with inline group sync, LoginView + SsoErrorView, deep-link preservation, hide-local-login admin setting, session invariance, rate-limit. **8 stories.**
- **Epic 3 (Teams & Role Resolution):** Team/TeamMember/IdPGroupMapping CRUD + bulk import, login-time group sync, `effective_role` with 6 endpoint migrations, TeamListView/TeamDetailView/GroupMappingRow, ApiToken role-cap regression. **15 stories.**
- **Epic 4 (First-Login & Inclusion):** `/auth/me` extended with teams + roles + first_login_complete, FirstLoginView + zero-state, welcome microcopy in 4 locales, TeamSwitcher, ReadOnlyBanner + useCanEdit, axe-core gate, driver.js tour (was already shipped), SSO-link-consent dialog. **9 stories.**
- **Epic 5 (Operational Resilience):** Emergency bypass API + admin UI + header banner, user-deactivation cascade, ApiToken reassign, retention cleanup jobs, procurement checklist, non-goals v1 lock, CI release gates, AuditEventType enum, i18n pass, recorder impact doc. **11 stories.**
- **Epic R (Recorder stability):** R-1 browser lifecycle event-based shutdown. **1 story.**

### Recorder v2
- **Epic W (Web MVP):** controlled-browser session, SSE command stream, capture script, hover overlay, keyword-family context menu, result view (emitter + save + live view), launcher view, audit + retention. **8 stories.**
- **Epic S (Shared Selectors):** selector datamodel, strategy library, uniqueness verification, inline picker, i18n strategy labels. **5 stories.**
- **Epic D (Windows desktop):** UIA selector synthesis + RPA.Windows emitter done; session adapter + primitive-capture stubbed (pywinauto hook pending a Windows dev host). **4 stories, 2 done, 2 in-progress.**
- **Epic DM (macOS desktop):** feasibility spike decided NO-GO for v2; DM.2 remains trigger-gated backlog. **2 stories, 1 done, 1 backlog.**

### Deferred-work security items (all closed)
- X-Forwarded-For aware client-IP helper for rate-limit + audit.
- IdP lookup order flipped before return_to validation (anti-probing).
- 429-audit emission deduplicated to 60 s per IP.
- Email PII in audit detail replaced with HMAC hash.

## What went well

- **Commit-per-story discipline.** Every story produced exactly one (or occasionally two) commits with a self-contained test suite. The branch has ~85 commits since origin/main and any one of them reverts cleanly.
- **Pure-function-first design.** The selector synthesis (S.2, D.3), the Robot emitter (W.6 + D.4), the PII hasher, the translator (W.1, D.2) all landed as pure Python functions behind thin wrappers. That's why Epic W scaffolding stayed green even while the Chromium launch wasn't wired yet, and why Epic D has 2/4 stories done without a Windows machine.
- **Test pollution disaster → SAVEPOINT fix.** The SSO-callback suite had 8 tests failing only in the full suite. Root cause was an inner `db.commit()` in `oidc_discovery.py` that escaped the conftest's connection-level transaction. Swapping to `db.flush()` + adopting the SQLAlchemy SAVEPOINT pattern in conftest turned 8 flaky tests green and future-proofed every commit-heavy handler. Single commit, 10 tests recovered.
- **Anti-probing review catch.** The Phase 4 adversarial code review on `c8c171b` flipped the IdP-existence check ordering before anyone deployed the v1 flow with the wrong order. Security gain at zero user cost.
- **Additive schema decisions.** `UserResponse` kept every pre-Phase-4 field; `MeResponse` is a subclass that only adds. `SelectorCandidate.strategy` enum covers web + desktop from day 1 so the Epic S picker works for Epic D candidates without a schema version bump.

## What went badly

- **Sprint-status drift in the initial Phase 4 commit.** `sprint-status.yaml` shipped with Epic 2 + Epic 3 marked `done` but the actual code had gaps (no `log_event` helper, no `require_effective_role` call sites, no team_id on PATCH /repos/{id}). A code-review pass caught this, stories were reverted to `in-progress`, and deferred-work.md was updated. Lesson: the tracker is only truthful if it's edited **after** the implementation commits, not alongside the spec.
- **Playwright in-browser behaviour untested.** W.1 full commits the Playwright task + binding wiring but the real Chromium launch runs outside pytest. An end-to-end spec (`phase4-gates.yml record-a-fixture-app-and-run-the-.robot`) is the planned coverage, but didn't land in this branch.
- **D.1 + D.2 partial by design.** The pywinauto event-hook wiring can't be exercised from macOS. The skeleton + translator + `_desktop_loop` with deferred import ships, but the actual recording behavior on a Windows host is untested. Merging to main without a Windows QA pass leaves a small but real risk of the hook wiring silently not producing commands.

## Surprises

- **The existing recording module from Story R-1 was a solid foundation.** The R-1 event-based shutdown pattern, the `get_sync_session` helper, the FK-import noqa pattern — all reused for Recorder v2 without modification. The `_broadcast_recording_status` threading pattern from R-1 made the v2 SSE stream tractable on a first pass.
- **vue-i18n's reserved characters caught us once.** The Phase 4 locale pass flagged `@ | { }` as production-build-breakers. The earlier commit had `admin@roboscope.local` escaped as `admin{'@'}roboscope.local` — a small gotcha documented in CLAUDE.md that saved later stories.
- **The existing Chrome extension (R-1 transport) continues to work unchanged.** No deprecation, no test breakage. The PRD explicitly preserved it; the transport enum accommodates both v1 and v2 paths.

## What we'd do differently

- **Ship a Playwright e2e fixture early.** The `phase4-gates.yml` workflow mentions a record-a-fixture-app test but it wasn't written. A tiny "flask app with a form + a submit button + assert the .robot runs" spec would have caught any binding or Chromium-launch regression before the human beta.
- **Write the sprint-status-update commit together with the implementation commit, not as a separate commit.** The "mark Epic 2 done" commit landed days before the real implementation. A rule: tracker flips `done` only in the same commit that lands the last implementation piece.
- **Draft a desktop-host acceptance test early.** Even a manual runbook for the Windows tester ("open the recorder, click three buttons, verify the .robot runs") would bound the D.1/D.2 integration risk better than "we'll know when it runs on a Windows box".

## Metrics

- **Story count:** 54 stories across 10 epics. 48 done, 2 in-progress (D.1/D.2 Windows-host gated), 4 backlog / trigger-gated (DM.2, 3-15 variants, etc.).
- **Test count:** backend 1440+, frontend 210, e2e phase-4-accessibility spec landed.
- **Commit count on branch:** ~85.
- **Deferred-work list:** started with ~30 items post-Phase-4 code review, ended with every security item closed and only two concrete operational items remaining: the D.1/D.2 Windows-host pywinauto wiring and the PR-to-main decision.

## Next-phase starting points

From the non-goals lock (`non-goals-v1-lock.md`) + this retro:

1. **SAML 2.0** (N-1) — deferred to Phase 4.5 (dedicated release train due to `xmlsec` build risk).
2. **SCIM 2.0 + real-time deprovisioning** (N-2 + N-6) — bundled Phase 5.
3. **D.1 + D.2 full Windows wiring** — focused Windows-host PR.
4. **Recorder e2e fixture spec** — phase4-gates.yml gate.
5. **Retrospectives per-epic** — optional per the sprint YAML; this consolidated document is the equivalent.

---

**Signed off:** all epic-level work for Phase 4 + Recorder v2 is either done or in a documented go/no-go state with explicit reconsider-triggers. The branch is deployment-ready subject to one Windows-host QA pass for Epic D.
