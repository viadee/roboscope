# Story REPO-1: Save loop for non-Git users (commit + push from the UI)

Status: done

Epic: REPO — Repository workflow for non-Git users
Story Key: `repo-1-non-git-save-loop`

## Reported

> Wie funktioniert die git-Logik mit dem Auto-Sync? Wir wollen das so haben, dass ein "nicht git" user ebenfalls damit klar kommt. Was kann er tun und was sind die Grenzen? […] C is the way to go.

(Option C from the audit: real save loop — `commit + push` exposed through the UI.)

## Today's gap

- File edits in the Explorer hit `PUT /explorer/{id}/file` and write to the git working tree, but `git status` after a long editing session shows N modified files that nobody ever commits or pushes. Other team members never see them; the next `Sync` (`git pull`) overwrites or refuses depending on upstream history.
- The UI offers `Sync` (pull) and a misleading `auto_sync` checkbox whose semantics today are "stored, not consumed".
- A non-Git user has no mental model of "it's saved to disk but not yet shared" because the editor's Save button gives a green checkmark either way.

## Goal

A non-Git user should be able to:

1. Open the editor, change files, hit Save (writes to disk — exactly as today).
2. See **somewhere prominent in the Explorer** that "you have N unsaved changes against the repository".
3. Click one button, write a one-line message, hit Save → all dirty files in this repo are committed locally and pushed to the remote, in one atomic operation, with the **logged-in RoboScope user's identity** as the git author.
4. If the push is rejected because the remote moved, get a clear conflict UI offering "Pull and retry" (which performs a `git pull --rebase=false` followed by another push).

That is the entire interaction. No git CLI knowledge required.

## Acceptance Criteria

### Backend

1. **AC1 — `GET /repos/{id}/status`** returns:
   ```json
   {
     "current_branch": "main",
     "ahead": 0,
     "behind": 0,
     "modified": ["tests/login.robot", "settings.resource"],
     "staged": [],
     "untracked": ["new_test.robot"],
     "deleted": [],
     "is_dirty": true
   }
   ```
   Path lists are repository-relative. Non-git repos (`repo_type === 'local'`) return `{is_dirty: false, …}` with empty lists — they have no save-loop concept.

2. **AC2 — `POST /repos/{id}/commit`** body `{message, paths?}`:
   - `message` is required, non-empty.
   - `paths` is optional; when omitted, all modified+untracked files are added.
   - Author/committer identity = `<User.username> <User.email>`. We pass `-c user.email=… -c user.name=…` per command, never write to the repo's `.git/config`, so concurrent commits by different users don't race on the config file.
   - Returns `{commit_hash, message, files: [...]}` on success.
   - Returns `400` when there is nothing to commit.

3. **AC3 — `POST /repos/{id}/push`**:
   - Pushes the current branch to its tracked upstream.
   - On non-fast-forward / rejected: returns `409 Conflict` with `{detail, behind, ahead}` so the client can offer "Pull and retry".
   - On auth failure: returns `502 Bad Gateway` with `{detail: "remote auth failed"}`.

4. **AC4 — `POST /repos/{id}/publish`** (combined):
   - Body `{message, paths?, allow_empty?}`. Performs commit + push as one operation.
   - Same return shape as commit, plus `{pushed: true, conflict: false}`.
   - On commit succeeded but push failed: returns `409` with `{commit_hash, conflict: true, detail}` — the local commit STAYS (lossless); the user can resolve the conflict and retry the push later via the standalone push endpoint.

5. **AC5 — RBAC**: All four endpoints sit behind `require_effective_role(Role.EDITOR)`. Pushing is a write to a shared resource, so VIEWER / RUNNER explicitly cannot.

6. **AC6 — Audit**: All POSTs are auto-logged by the audit middleware; the commit hash and file list end up in `AuditLog.detail`. Read-only `GET /status` is intentionally not audited (high-frequency polling endpoint).

7. **AC7 — Local repos rejected**: All four endpoints return `400` when `repo.repo_type === 'local'`. Local repos have no remote to push to.

8. **AC8 — Concurrency**: A simple `fcntl.flock` on `<local_path>/.git/index.lock` (file-level lock) serialises concurrent commit-or-push requests against the same repo. Two users hitting Publish simultaneously block each other instead of corrupting the index.

### Frontend

9. **AC9 — Status badge**: When the user is in the Explorer of a Git repo with `is_dirty === true`, a primary-coloured badge `Save N changes` appears in the page header next to the repo name. Clicking it opens the Save modal.

10. **AC10 — Save modal**: Lists `modified`, `untracked`, and `deleted` paths with checkboxes (default: all checked). Commit-message input (max 200 chars, required). Cancel + Save buttons. On Save → `POST /repos/{id}/publish` → success toast `"Saved N changes (a1b2c3d)"` and the badge disappears.

11. **AC11 — Conflict UI**: A `409` from publish renders a different state on the modal: header "Remote moved on", explanatory copy "Your commit was saved locally but couldn't be pushed because someone else pushed first", a "Pull latest changes" button (calls `/sync` then re-tries `/push`), and a "Cancel" that dismisses the modal (the local commit stays).

12. **AC12 — i18n EN/DE/FR/ES**: Every new user-facing string has 4 locale entries.

13. **AC13 — RBAC honoured client-side**: VIEWER / RUNNER do not see the badge. The button is gated on the same `effective_role` used elsewhere (the user store already exposes `effective_roles_by_repo`).

### Tests

14. **AC14 — Backend integration tests** with a temp bare repo as the upstream:
    - `test_status_returns_modified_paths`
    - `test_commit_records_user_identity` (committer email matches `User.email`)
    - `test_commit_with_no_changes_returns_400`
    - `test_push_succeeds_when_fast_forward`
    - `test_push_returns_409_on_non_fast_forward` (creates a divergent state by pushing from a sibling clone)
    - `test_publish_combined_succeeds`
    - `test_publish_keeps_local_commit_on_push_conflict`
    - `test_endpoints_require_editor_role` (RUNNER → 403)
    - `test_local_repo_returns_400`

15. **AC15 — Frontend Vitest** for `PublishModal.vue`: happy path, conflict path, no-changes empty state.

16. **AC16 — All existing suites still green** (`make test-backend`, `make test-frontend`).

### Documentation

17. **AC17 — In-app docs updated**: The misleading "Auto-Sync — pulls before each test run" paragraph in `frontend/src/docs/content/{en,de,fr,es}.ts` is replaced. The new section explains:
    - The save loop (Save edits → click "Save N changes" → enter message → commit + push).
    - What `auto_sync` actually does today (nothing in the executor — it's a placeholder for future scheduled-pull functionality).
    - That `Sync` is pull-only and may overwrite local edits if the user hasn't published them.

## Out of scope (V1)

- **Diff viewer** (preview each modified file's change in the modal). Listing paths is enough for V1; users can switch to the editor for the actual diff via tab.
- **Per-file commit messages** / multiple commits in one Save. One commit per Save action. Power users who want fine-grained history can do that on the CLI.
- **Branch creation from the UI**. Stay on the existing branch; switching is already handled by the Branch dropdown.
- **`Stash` / "discard my changes"**. Possible follow-up; the foot-gun is real (you cannot undo a discard) so let's leave it for a deliberate design pass.
- **Conflict resolution beyond "pull-first-then-push"**. If the pull itself fails (merge conflict), we surface the git error verbatim and tell the user "this needs CLI / outside help". Building a 3-way merge UI is a much bigger project.
- **Honouring `auto_sync` finally**. Decoupled: that's a separate story (REPO-2) about the scheduler, since the orthogonal claim "pull before run" needs its own design.

## Risk notes

- **Push auth without UI**: relies on whatever the host's git config provides. If the user supplied `https://oauth2:<token>@github.com/foo/bar.git` as `git_url`, push works; if SSH, the host's SSH config / agent must have the right key. We surface auth failures as `502` so the user knows it's not their fault — but we cannot help them set up auth from inside RoboScope, that's a host-config concern.
- **Identity privacy**: the User's email goes into commit metadata visible to the entire team's git history. That's the standard expectation for any "save in a shared repo" tool, but worth a one-line note in the docs.
- **Non-fast-forward pushes do happen**: the conflict path is the most likely failure mode. Tests must cover it.
