# Story REPO-2: Auto-Sync that actually pulls on a schedule

Status: done

Epic: REPO — Repository workflow for non-Git users
Story Key: `repo-2-auto-sync-scheduled-pull`

## Reported

REPO-1's audit established that `auto_sync` (bool) and `sync_interval_minutes` (int) on the `Repository` model are stored but never consumed. The follow-up REPO-2 makes them real: a background scheduler periodically pulls every git repo whose checkbox is on and whose last sync is older than its interval.

## Acceptance Criteria

1. **AC1 — Pure helper.** `due_repos(db, now)` in `src/repos/service.py` returns the list of `Repository` rows that should be synced right now:
   - `repo_type == 'git'`
   - `auto_sync == True`
   - `last_synced_at IS NULL` **OR** `last_synced_at < now - sync_interval_minutes`
   - `git_url` non-null (defensive — a repo with `auto_sync=True` but no URL would crash the dispatch task).

2. **AC2 — Scheduler job.** `main.py` registers an APScheduler interval job at lifespan start that fires **every 5 minutes**, calls `due_repos(db, now)`, dispatches `sync_repo(repo_id)` for each result, logs counts at INFO. The 5-minute heartbeat is a deliberate compromise: a user who set `sync_interval_minutes=15` expects to wait at most ~15 min for a pull; finer granularity gains nothing because individual repo intervals are coarser.

3. **AC3 — Concurrency**. If the same repo's previous auto-sync is still running (`sync_status == 'syncing'`), skip it this tick — `dispatch_task` doesn't natively de-duplicate, so the helper queries `last_synced_at` and the scheduler also gates on `sync_status != 'syncing'`.

4. **AC4 — Lifespan-safe shutdown**. The job is registered on the existing `_scheduler` instance in `main.py` (next to the retention + OIDC + Phase-4 cleanup jobs). The shutdown path already calls `_scheduler.shutdown(wait=False)`, so no extra teardown work.

5. **AC5 — Audit invisibility.** Auto-sync invocations don't go through the HTTP middleware, so they would NOT be auto-audited. We don't need an explicit audit entry — manual sync via `POST /repos/{id}/sync` already records the user-triggered case, and a 5-minute heartbeat audit row would drown the log. (Mention in the story-out-of-scope.)

6. **AC6 — Tests.**
   - `test_due_repos_picks_never_synced` — `last_synced_at IS NULL` always due
   - `test_due_repos_picks_overdue` — `last_synced_at` older than interval → due
   - `test_due_repos_skips_recent` — `last_synced_at` within interval → not due
   - `test_due_repos_skips_local_repo` — `repo_type='local'` excluded
   - `test_due_repos_skips_auto_sync_off` — `auto_sync=False` excluded
   - `test_due_repos_skips_in_flight` — `sync_status='syncing'` excluded
   - `test_due_repos_skips_no_git_url` — `git_url IS NULL` excluded (defensive)

7. **AC7 — In-app docs corrected**. REPO-1 left the docs honestly saying "Auto-Sync is a placeholder for a future scheduled-pull feature." That sentence is now obsolete. Replace with the new behaviour: "When enabled, RoboScope pulls in the background every `sync_interval_minutes`. The scheduler runs at most every 5 min, so very short intervals are rounded up." Updated in EN/DE/FR/ES.

## Out of scope (V1)

- **Pre-run sync** ("pull before each test run"). Orthogonal concern. The 5-min heartbeat already gives the runner a reasonably fresh checkout in most cases. If a run truly demands "latest right now," the user can hit the explicit Sync button.
- **Webhook-triggered sync**. The `POST /webhooks/git` inbound endpoint already creates a test run on push; making it ALSO sync first is a separate decision (today the run uses whatever's already on disk, which means push-triggered runs may run an older copy on a slow machine).
- **Auditing every auto-sync**. The 5-min heartbeat would generate hundreds of audit rows per day per repo. We'd need a separate "scheduled sync log" surface to make that signal vs noise. Defer.
- **Conflict resolution on auto-sync**. If a user's local edits conflict with the upstream pull, the existing `sync_repo` task already catches the GitCommandError and writes `sync_error` to the row — the UI badge surfaces it. Not changing that behaviour here.

## Risk notes

- **Scheduler vs. test isolation**: tests for `due_repos` should NOT trigger the scheduler — they exercise the helper as a pure DB query. The scheduler's actual firing is implicitly tested via the existing manual-sync endpoint test (which dispatches the same `sync_repo` task).
- **Time math**: SQLite doesn't natively understand `last_synced_at + interval minutes`. The simplest portable approach is to filter in Python over the candidate set (auto_sync=True repos), then compute the boundary in code — for a project that's never seen >100 repos, the in-Python filter is fine.
