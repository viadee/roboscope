# Story REPO-4: Webhooks pull before triggering the run

Status: done

Epic: REPO — Repository workflow for non-Git users
Story Key: `repo-4-webhook-pre-sync`

## Reported

REPO-2's deferred items called this out:

> **Webhook-triggered sync**. The `POST /webhooks/git` inbound endpoint
> already creates a test run on push; making it ALSO sync first is a
> separate decision (today the run uses whatever's already on disk,
> which means push-triggered runs may run an older copy on a slow
> machine).

REPO-3 added the per-repo `pre_run_sync` flag, but it's opt-in. A user
with the flag *off* who relies on the inbound git webhook to trigger
runs would still see runs against stale checkouts — ironic, since the
push event *is* the proof that origin moved.

## The implementation, in two lines

`backend/src/task_executor.py` uses
`ThreadPoolExecutor(max_workers=1)` — every dispatched task runs
serially in FIFO order. So the webhook handler simply dispatches
`sync_repo(repo.id)` *before* `execute_test_run(run.id)` and the
single-worker queue guarantees the sync finishes first. No new
columns, no orchestration, no double-pull guards.

## Acceptance Criteria

1. **AC1 — Order-guaranteed dispatch.** `git_webhook_inbound` in
   `backend/src/webhooks/router.py`: when the matched repo is
   `repo_type == 'git'` with a `git_url`, dispatch
   `sync_repo(repo.id)` *before* dispatching `execute_test_run(run.id)`.
   The serialised executor pulls origin to completion before the run
   starts.

2. **AC2 — Failure isolation.** A `TaskDispatchError` on the sync
   dispatch must NOT abort the run dispatch — log a WARNING and proceed
   with whatever's on disk. (Same philosophy as REPO-3's
   "fall through on pull failure".)

3. **AC3 — Local repos exempt.** `repo_type == 'local'` skips the
   sync — there's nothing to pull.

4. **AC4 — No double-pull when `pre_run_sync` is on.** If the repo
   *also* has `pre_run_sync=True`, the in-`execute_test_run` pre-sync
   runs *again* and is a near-no-op (working copy already up-to-date).
   We accept the second pull as cheap rather than build a "we already
   synced this run" signalling channel between tasks.

5. **AC5 — Tests.**
   - `test_webhook_dispatches_sync_before_run` — verify dispatch
     order via a list-of-calls patch on `dispatch_task`.
   - `test_webhook_skips_sync_for_local_repo` — `repo_type='local'`
     dispatches only the run.
   - `test_webhook_run_proceeds_when_sync_dispatch_fails` — patch
     dispatch_task to raise on the first call and succeed on the
     second; verify the run still gets dispatched.

## Out of scope (V1)

- **Branch-specific sync**. If the webhook payload's branch is
  `feat/foo` but the working copy is checked out on `main`, we sync
  `main`, not `feat/foo`. That's a pre-existing limitation: the run
  itself doesn't checkout `run.branch` either (`run.branch` is only
  used for telemetry today). Fixing branch-aware checkout is a
  larger story.
- **Webhook-side latency budget**. The HTTP response returns
  immediately after dispatching both tasks. We don't wait for the
  pull to finish before responding. GitHub/GitLab senders therefore
  see the same low-latency 200 they always have.
- **Retries / DLQ**. The serial executor currently has no retry —
  if the worker thread crashes, the in-flight task is lost. Out of
  scope here; covered separately by Phase-5 distributed-execution
  work.

## Risk notes

- **Pre-run-sync race window**: if a *manual* `POST /repos/{id}/sync`
  fires concurrently with a webhook, both end up dispatching
  `sync_repo` for the same repo. They run serially (max_workers=1),
  so no working-tree race — just two pulls back-to-back, the second
  is a near no-op. Safe.
- **Queue starvation**: a stuck `sync_repo` (e.g. credential prompt
  hang) would block the run behind it. The existing
  `sync_repository` already returns `"error: ..."` on
  `GitCommandError` rather than hanging, so the practical risk is
  bounded by GitPython's own timeouts. Not addressing here.
