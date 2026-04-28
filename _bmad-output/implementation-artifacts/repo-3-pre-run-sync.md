# Story REPO-3: Pre-run sync — pull latest before each test run

Status: done

## Adversarial review fixes applied

**M1 — ThreadPoolExecutor leak negated the timeout.** The first cut used
`with concurrent.futures.ThreadPoolExecutor(...) as pool:`. Python's
context-manager exit calls `shutdown(wait=True)`, which blocks until
the leaked pull thread finishes — directly defeating the wall-clock
timeout we just imposed. Fix: explicit pool + `shutdown(wait=False)`
in a `finally` clause. Test
`TestTimeoutDoesNotBlockOnPoolShutdown::test_timeout_returns_promptly`
asserts the function returns within 3 s when the underlying pull would
take 5 s.

**M2 — sync_status not flipped, racing the auto-sync scheduler.** The
first cut only *read* `sync_status`. The REPO-2 5-min scheduler reads
the same field; if it ticked while pre-run-sync's pull was in flight
it would dispatch its own `git pull` on the same working copy.
Fix: `sync_for_run(repo, session, timeout_seconds)` now flips
`sync_status='syncing'` before the pull and writes
`'success'`/`'error'` after, exactly like the existing `sync_repo`
task. New tests under `TestSyncStatusFlipping` cover all four state
transitions.

Epic: REPO — Repository workflow for non-Git users
Story Key: `repo-3-pre-run-sync`

## Reported

REPO-2 made `auto_sync` actually pull on a 5-min schedule. That covers "the
checkout is *roughly* fresh." Some users — CI-style flows, push-and-run
demos, "I just changed one assertion and want to re-run" — need
*guaranteed* fresh: pull `origin/<default_branch>` *now*, then run.

REPO-2 explicitly deferred this:

> **Pre-run sync** ("pull before each test run"). Orthogonal concern. The
> 5-min heartbeat already gives the runner a reasonably fresh checkout in
> most cases. If a run truly demands "latest right now," the user can hit
> the explicit Sync button.

REPO-3 adds the toggle so a user doesn't have to remember the manual step.

## Acceptance Criteria

1. **AC1 — New per-repo flag.** `Repository.pre_run_sync: bool` (default
   `False`). Composes with `auto_sync` — they're independent: a repo can
   have neither, either, or both.

2. **AC2 — Lightweight migration.** `_migrate_sqlite()` and
   `_migrate_postgres()` in `database.py` add the column when missing
   (`ALTER TABLE repositories ADD COLUMN pre_run_sync BOOLEAN DEFAULT 0`
   for SQLite, `DEFAULT FALSE` for Postgres). No Alembic migration —
   matches the existing project convention.

3. **AC3 — Pure helper.** `sync_for_run(repo, timeout_seconds=60)` in
   `src/repos/service.py`:
   - For `repo_type == 'local'` or `pre_run_sync == False`: returns
     `("skipped", None)` immediately — no work.
   - For `repo_type == 'git'` and `pre_run_sync == True`: invokes
     `sync_repository(local_path, default_branch)` under a wall-clock
     timeout. Returns `("ok", "<short message>")` on success,
     `("error", "<reason>")` on git failure, `("timeout", "<seconds>s")`
     on timeout.
   - **Never raises.** A pre-run sync failure must NOT abort the test
     run — the runner falls through with whatever's on disk and the run
     surfaces the warning in `error_message` *only if* the run itself
     also fails. The fresh-pull is best-effort.

4. **AC4 — Wired into execution dispatch.** `execute_test_run()` in
   `src/execution/tasks.py` calls `sync_for_run(repo)` *after* the
   repository row is loaded (line ~270) and *before* `runner.prepare()`
   (line ~279). On `("ok", msg)`: log INFO + update `repo.last_synced_at`
   + commit. On `("error", reason)` or `("timeout", _)`: log WARNING,
   leave `last_synced_at` alone (so the scheduler's next tick will retry).

5. **AC5 — Concurrency**. If a manual sync is in flight
   (`sync_status == 'syncing'`), pre-run sync is skipped this iteration —
   we don't want two `git pull`s racing on the same working copy.
   `sync_for_run` returns `("skipped", "another sync in progress")`.

6. **AC6 — API surface.**
   - `RepoCreate.pre_run_sync: bool = False` (defaults so existing
     clients don't need to know about the field).
   - `RepoUpdate.pre_run_sync: bool | None = None` — `null` = "don't
     change," matches the existing convention for the other patch fields.
   - `RepoResponse.pre_run_sync: bool` — always echoed back.

7. **AC7 — Frontend.** Repository card in `ReposView.vue` shows the
   toggle alongside the existing Auto-Sync row, with the same
   `auth.hasMinRole('editor')` gating. Label: "Pre-run sync" (en) /
   "Pre-run-Sync" (de) / "Synchro avant exécution" (fr) / "Sincronizar
   antes de ejecutar" (es). Help-text below: "Always pulls the latest
   commit before running tests in this repository — adds a few seconds
   per run."

8. **AC8 — Tests (backend).**
   - `test_sync_for_run_local_repo_skips` — `repo_type='local'` returns
     `("skipped", _)`.
   - `test_sync_for_run_flag_off_skips` — `pre_run_sync=False` returns
     `("skipped", _)`.
   - `test_sync_for_run_in_flight_skips` — `sync_status='syncing'`
     returns `("skipped", _)`.
   - `test_sync_for_run_success_updates_last_synced` — happy path against
     a bare-repo + working-clone fixture, verifies `last_synced_at` is
     updated.
   - `test_sync_for_run_swallows_git_error` — bad URL / bare-repo pull
     surfaces `("error", _)` without raising.
   - `test_sync_for_run_respects_timeout` — slow `git pull` (mocked to
     sleep > timeout) returns `("timeout", _)`.
   - `test_execute_test_run_invokes_pre_sync_when_enabled` — integration
     test patching `sync_for_run` to verify it's called from
     `execute_test_run` only when the flag is on.

9. **AC9 — Tests (frontend).** No new Vitest needed — the toggle is a
   trivial checkbox bound to the existing `repo.pre_run_sync` and the
   existing `updateRepo()` action. Existing
   `frontend/src/views/__tests__/ReposView.spec.ts` (if any) is not
   broken.

10. **AC10 — In-app docs.** EN/DE/FR/ES `frontend/src/docs/content/*.ts`
    Auto-Sync section gets a new paragraph distinguishing the two:
    > Auto-Sync runs in the background every X minutes. Pre-run sync
    > additionally pulls *just before* each test run — pick this if your
    > tests must run against the very latest commit.

## Out of scope (V1)

- **Pre-run sync on `POST /webhooks/git`**: webhook-triggered runs
  already run with whatever's on disk. Adding pre-run sync to that path
  is double-syncing if the same push also triggered the webhook
  (origin already has the commit, the working copy may not). Defer to
  REPO-4.
- **Per-run override**: "this one run, sync first." The toggle is
  per-repo, not per-run. UI complexity not warranted yet.
- **Cancel-on-pull-conflict**: if pull fails because the user has
  uncommitted local changes, the run continues with the un-pulled state.
  Surfacing "your run was stale because you have unpushed local edits"
  belongs in the save-loop UI (REPO-1).
- **Distributed-runner sync coordination**: when multi-worker execution
  lands (Phase 5), pre-run sync per worker means N pulls per run — fine
  for now, optimise later.

## Risk notes

- **Wall-clock timeout vs. interrupt safety**: GitPython's
  `origin.pull()` can hang on TLS handshake. We use
  `concurrent.futures.ThreadPoolExecutor.submit(...).result(timeout=…)`
  to bound the wait. The pull thread is leaked on timeout — it will
  eventually finish and write to the repo while the run is already
  starting. Mitigation: subsequent pulls are idempotent, and the runner
  reads files lazily (via `runner.execute`) so the late-arriving pull
  may even land before robot starts. We log the timeout for ops.
- **Schedule + pre-run double-pull**: if the 5-min scheduler ticks
  exactly when a run starts, both paths could race. Mitigation: AC5 —
  pre-run sync skips when `sync_status == 'syncing'`, the scheduler also
  skips in-flight repos.
- **Fresh checkout corrupting an in-progress run**: tests are loaded
  by `runner.execute`, not `runner.prepare`. A pull mid-run could
  technically swap files under us. In practice runner.execute reads the
  Robot Framework files at start, before subprocess spawn — so the only
  risk window is microseconds. Not addressing in V1.
