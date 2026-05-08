# Story 5-10: Chrome Recorder Phase-4 Impact Documentation

Status: done

## Story

As an existing Chrome Recorder user,
I want to understand what changes (and what doesn't) for me in Phase 4,
so that I'm not confused when my team access expands but my recorder access doesn't.

## Acceptance Criteria

1. Release notes include a dedicated section listing: the recorder extension is unchanged in Phase 4; API-token auth is preserved; `ApiToken.role` stays capped at `User.role` globally and does not honor Team grants; Team-scoped recorder access is a Phase 5 candidate.
2. In-app docs (`docs-en`, `docs-de`, `docs-fr`, `docs-es`) carry the same note with localized copy.
3. The recorder's own README (`extension/README.md`) references this note so someone finding the extension outside the main repo still sees the Phase-4 caveat.

## Phase 4 Impact Summary for Chrome Recorder Users

### What changes

Nothing in the recorder itself. The extension ships with Phase 4 at the same version and feature set as at Phase 3. You do not need to update your browser extension, your API token, or any CI/CD pipeline.

### What Phase 4 adds that is visible from the recorder

- **Teams.** You may now appear as a member of one or more Teams in the web UI, with a role per team (VIEWER / RUNNER / EDITOR / ADMIN).
- **Effective role.** On the web UI, your effective role for a given repository is the MAX of your global role, your per-team role on that repo's team, and any explicit project-member role. Team membership can therefore GRANT you additional access on the web UI.

### What stays capped

- **Your `rbs_…` API token's role never elevates via Team grants.** Team grants apply to your web-UI session only. The recorder authenticates with an `ApiToken` whose scoped role is compared against your current global `User.role`; the effective permission is `min(token.role, user.role)`. Team-based elevation is explicitly skipped for API-token-authenticated requests (Story 3-15).

This is intentional. API tokens are **machine identities**, not human-session proxies. Minting a team-scoped token would require additional UX (which team does this token represent?) and would expand the blast radius of a leaked token to match whatever teams the owning human is on at the moment of check.

### How to access a Team-scoped repository via the recorder

You have two options today:

- **(a)** Ask an admin to grant you a higher **global** role (e.g., `EDITOR` on `User`) — this does elevate the API-token's effective cap.
- **(b)** Wait for Phase 5, which will evaluate a dedicated Team-scoped API-token concept (tracked in `non-goals-v1-lock.md` N-11).

### FAQ

- *"I used to have RUNNER everywhere via my global role; Phase 4 hasn't removed that, has it?"* — No. Phase 4 is additive. Global role remains the floor for both UI and recorder access.
- *"My team-member status on 'Team Alpha' makes me EDITOR in the UI. Why does my recorder still only see VIEWER on an Alpha repo?"* — Because your token's scoped role is VIEWER and Team grants do not apply to tokens. Raise your global role OR mint a token with a higher scoped role (still capped at your global role).
- *"Could a leaked token escalate via Team?"* — No. Story 3-15 regression-tests specifically that this does not happen.

## Implementation

- This artifact doubles as the release-notes section for Phase 4 (copy into `CHANGELOG.md` under the Phase 4 entry before cutting the release tag).
- In-app docs: add the same three paragraphs under each `docs-{lang}` tree's "Chrome Recorder" page (translations owned by tech-writer agent).
- `extension/README.md`: add a top-of-file note referencing this doc.

## References

- Story 3-15 (ApiToken role-cap verification) locks the behavior in code with 5 regression tests.
- `non-goals-v1-lock.md` entry N-11 tracks the reconsider-trigger for Phase 5.
- PRD §"Non-Goals (Explicit)" → "Chrome Recorder extension changes".
