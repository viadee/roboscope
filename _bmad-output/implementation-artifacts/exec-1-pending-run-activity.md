# Story EXEC-1 — Pending-run activity surface

**Type:** BMAD quick story (UX observability)
**Date:** 2026-04-23

## Background

`execute_test_run()` flips `RunStatus.PENDING → RUNNING` synchronously as soon as the single-worker `ThreadPoolExecutor` picks up the task. So today "pending" has two real meanings that the UI can't tell apart:

1. **Queued behind another run.** One run executes at a time; N runs created concurrently go through positions 2..N silently.
2. **Preparing dependencies.** The Docker runner's `prepare()` pulls or builds the image inline; if the user triggered an image rebuild just before launching the run, they may be looking at a "pending" row while environment #X is streaming `docker_build_log` events on the WebSocket — but the run panel today shows only a spinner with no link between the two.

The result: a user whose run sits on pending for 60+ seconds has no way to tell whether to wait or investigate.

## Acceptance Criteria

1. **Given** a run `R` with `status=pending`, **when** the frontend loads the run detail panel, **then** a "Pending activity" box appears and states **why** the run hasn't started yet.
2. **Given** at least one other run `R'` with `created_at < R.created_at` is still in `pending` or `running`, **when** `R`'s pending box renders, **then** it shows a "Queued behind N run(s)" message where N is the exact count of earlier runs still in a non-terminal state.
3. **Given** `R`'s assigned environment has `docker_build_status='building'` OR (effective runner is Docker AND no image tag yet), **when** `R`'s pending box renders, **then** it shows a "Waiting for Docker image build on <env-name>" line and renders the tail of the live build log (using the existing environments-store WebSocket feed; no new subscription).
4. **Given** neither AC2 nor AC3 applies but `R` is still pending, **when** the pending box renders, **then** it falls back to a generic "Warten auf Ausführung" / "Waiting to start" line rather than appearing empty.
5. The pending box auto-refreshes its queue-position count at most every 3 seconds while the run is pending — no thundering-herd if the user leaves the panel open.
6. The pending box disappears as soon as the run's status leaves `pending`.
7. **Backend endpoint** `GET /api/v1/runs/{run_id}/pending-activity` returns the structured payload (`status`, `queue_position`, `ahead_count`, `active_build`, `effective_runner_type`). 404 if the run doesn't exist, 403 if the caller lacks read access on the owning repo, 200 otherwise.
8. **i18n:** new keys in EN/DE/FR/ES. German is the primary locale (user's working language).
9. **Tests:** one backend pytest covering (a) queue position counting, (b) active-build detection when env's `docker_build_status == 'building'`, (c) 404 path.
10. **Docs:** a short paragraph in the in-app docs "Test Execution" section explaining the new pending box.

## Out of scope

- Per-step build-log rendering on the run panel itself — the env's build log already lives on the Environments page; we link to it rather than duplicating the full stream.
- Retrying a pending run. Cancel already works; retry-from-pending is a different UX.
- Pre-empting queue position (drag-to-reorder).
- Notifying the user (toast / browser notification) when the run transitions out of pending. Existing WebSocket `run_status` handler already does that at terminal transitions.
