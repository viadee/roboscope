---
status: 'draft'
createdAt: '2026-09-24'
inputDocuments:
  - _bmad-output/planning-artifacts/research/v0.14-functional-gap-brainstorm-2026-09-24.md
  - _bmad-output/planning-artifacts/non-goals-v1-lock.md
  - _bmad-output/implementation-artifacts/deferred-work.md
epic: 'V14 — Close the silent gaps (v0.14.0)'
---

# RoboScope — Epic V14: Close the silent gaps

## Overview

Two features have a UI, a data model, e2e UI tests and in-app docs but no runtime effect:
**schedules never fire** and **environment variables never reach a run**. Three small
gaps sit next to them, all on existing data: tabular report export, per-report delete, and
a diff preview before publishing. Each story is well under a day for one developer, covering
backend, frontend, i18n (EN/DE/FR/ES, with ZH falling back to EN) and tests.

**Out of scope (in flight elsewhere this iteration):** dependency upgrade, own-interpreter
execution, importing an existing venv.

**Suggested order:** V14.1, then V14.2 (both touch `execution/tasks.py`, so land sequentially),
then V14.3, V14.4 and V14.5 (independent, can run in parallel).

## Cross-cutting rules (from CLAUDE.md, apply to every story)

- `db.commit()` before `dispatch_task()`. Task modules import FK models (`import src.auth.models  # noqa: F401`).
- Every user-facing string goes in `frontend/src/i18n/locales/{en,de,fr,es}.ts`. Escape `@ | { }` and verify with a prod build (`npm run build`).
- Dates shown in the UI go through `parseBackendDate`, never `new Date(apiField)`.
- The audit middleware skips responses with status ≥ 400. None of these stories adds a 403 gate that needs a manual audit row.
- Offline only: no new runtime dependencies. APScheduler, GitPython and stdlib `csv` are already present.
- The in-app docs (`frontend/src/docs/content/{en,de,fr,es}.ts`) must describe the real behaviour. Keep top-level section ids identical across locales (Gate 8).

---

## Story V14.1: Scheduled runs actually fire (+ "Run now")

**As a** team lead, **I want** a schedule with a cron expression to start a test run automatically,
**so that** nightly regressions happen without anyone pressing a button.

**Evidence:** `main.py:309-354` has no schedule job, and `execution/models.py:91-104` says "there is no
schedule-trigger path yet". `last_run_at`/`next_run_at` are never written. The docs promise recurring runs (`en.ts:176`).

### Acceptance criteria

- **AC1 (cron validation):** **Given** a schedule create/update request with `cron_expression = "every day"`,
  **when** it is submitted, **then** the API returns 422. **Given** `"0 2 * * 1-5"`, **then** it is stored
  and `next_run_at` is set to the next matching time (naive UTC). Validation uses
  `apscheduler.triggers.cron.CronTrigger.from_crontab`, which is already installed.
- **AC2 (trigger):** **Given** an active schedule whose `next_run_at <= now`, **when** the per-minute
  heartbeat job `run_due_schedules()` runs, **then** it creates an `ExecutionRun` with
  `schedule_id`, `repository_id`, `environment_id`, `target_path`, `branch`, `runner_type`,
  `tags_include` and `tags_exclude` copied from the schedule and `triggered_by = schedule.created_by`.
  It then commits, dispatches `execute_test_run`, and sets `last_run_at = now` and a recomputed `next_run_at`.
- **AC3 (no pile-up):** **Given** the schedule's previous run is still `pending` or `running`, **when**
  the schedule is due, **then** no new run is created, `next_run_at` still advances, and a warning is logged.
- **AC4 (inactive / orphaned):** **Given** `is_active = false`, or a creator who is inactive or deleted, or a deleted repo,
  **when** the schedule is due, **then** no run is created (the latter cases log a warning and advance `next_run_at`).
- **AC5 (security guardrail):** the trigger path does **not** read `schedule.advanced_config` or
  `schedule.variables`, so `test_schedule_trigger_gate_tripwire.py` stays green unchanged.
  Scheduled runs never carry advanced args or modifiers.
- **AC6 (Run now):** **Given** a user with effective role ≥ RUNNER on the schedule's repo, **when** they
  click "Run now" on a schedule row (`POST /schedules/{id}/run`), **then** a run is created exactly as in AC2
  (active or not), `last_run_at` updates and `next_run_at` does not change. The UI navigates to or highlights the new run.
- **AC7 (visibility):** the Schedules table shows "Last run" and "Next run" (localised, via `parseBackendDate`).
- **AC8 (restart safety):** after a backend restart, a schedule missed by more than 1 heartbeat fires **once**
  (coalesce) and does not replay every missed slot.

### Files to touch

- `backend/src/execution/service.py`: `compute_next_run(cron, now)`, `create_run_from_schedule(db, schedule, user_id)`, and cron set on create/update
- `backend/src/execution/schemas.py`: `field_validator("cron_expression")` on `ScheduleCreate`/`ScheduleUpdate`; expose `last_run_at`/`next_run_at` on `ScheduleResponse` if missing
- `backend/src/execution/tasks.py` (or new `backend/src/execution/schedule_trigger.py`): `run_due_schedules(now=None)` using `get_sync_session`, with FK imports
- `backend/src/execution/router.py`: `POST /schedules/{schedule_id}/run`
- `backend/src/main.py`: `_scheduler.add_job(run_due_schedules, IntervalTrigger(minutes=1), coalesce=True, misfire_grace_time=60)`
- `frontend/src/api/execution.api.ts`: `runScheduleNow(id)`
- `frontend/src/views/ExecutionView.vue`: "Run now" button plus Last/Next run columns
- `frontend/src/types/domain.types.ts`: `Schedule.last_run_at` / `next_run_at`
- `frontend/src/i18n/locales/{en,de,fr,es}.ts`: `execution.schedules.runNow`, `lastRun`, `nextRun`, `invalidCron`
- `frontend/src/docs/content/{en,de,fr,es}.ts`: one paragraph on scheduling semantics (server time zone, no overlap, runs as the schedule's creator)

### Test plan

- **pytest** `backend/tests/execution/test_schedule_trigger.py`: invalid cron gives 422; valid cron sets `next_run_at`;
  `run_due_schedules(now=…)` creates exactly one run with the copied fields and `schedule_id`; it skips when the previous run is pending;
  it skips inactive schedules; a deactivated creator produces no run; "Run now" does not move `next_run_at`; RUNNER is required.
  Call `run_due_schedules` directly with an injected `now` and patch `dispatch_task`. No sleeps.
- **vitest** `frontend/src/tests/components/ScheduleRunNow.spec.ts`: the button calls `runScheduleNow`; Last/Next run render through `parseBackendDate`.
- **e2e** extend `e2e/tests/scheduling.spec.ts`: create a schedule, click "Run now", and assert that a new run appears in the Runs tab.

---

## Story V14.2: Environment variables: full CRUD and injection into runs

**As a** test author, **I want** to define `BASE_URL` / `API_KEY` on an environment and read them as
`%{BASE_URL}` in my suites, **so that** the same tests run against staging and prod without code edits.

**Evidence:** only `GET` and `POST /environments/{id}/variables` exist (`environments/router.py:751-780`). The UI is read-only
(`EnvironmentsView.vue:416-426`). `decrypt_variable_value` has no caller. `subprocess_runner.py:103` uses
plain `os.environ.copy()`. The docs (`en.ts:1856-1873`) promise injection plus add/edit/delete.

### Acceptance criteria

- **AC1 (CRUD):** `PATCH /environments/{env_id}/variables/{var_id}` (key/value/is_secret) and
  `DELETE /environments/{env_id}/variables/{var_id}`, EDITOR role, same as `POST`. A secret value is re-encrypted on
  update. An update with an **empty** value on a secret keeps the stored value, so the edit form never has to echo a secret.
  The key is validated as an env-var name (`^[A-Za-z_][A-Za-z0-9_]*$`), and a duplicate key in the same env returns 409.
- **AC2 (no secret leak):** `GET …/variables` keeps masking secrets (existing behaviour, `router.py:764`), and no
  response or log line ever contains a decrypted secret.
- **AC3 (subprocess injection):** **Given** env E has `BASE_URL=https://staging` and secret `API_KEY=s3cr3t`, **when**
  a subprocess run uses E, **then** the `robot` child process environment contains both, with the secret decrypted.
  A suite with `Should Be Equal    %{BASE_URL}    https://staging` passes.
- **AC4 (docker injection):** the same variables land in the container `environment=` alongside the existing
  `ROBOT_*` run variables. On a name clash, the environment variable is overridden by the run variable (the more specific source wins).
- **AC5 (reserved names):** variables named `PATH`, `VIRTUAL_ENV`, `PYTHONPATH` or `PYTHONHOME` are rejected at create/update (422)
  so they cannot break venv activation or smuggle in code-loading paths. (Security: `PYTHONPATH` would bypass the
  EXEC `--pythonpath` deny-list.)
- **AC6 (clone):** cloning an environment still copies its variables (existing `service.py:130`, regression-pinned).
- **AC7 (UI):** the Variables section in `EnvironmentsView.vue` gets add, inline edit and delete (with a confirm prompt). A
  secret checkbox hides the value input as a password field, and an edited secret shows "(unchanged)" placeholder text.

### Files to touch

- `backend/src/environments/schemas.py`: `EnvVarUpdate`, key regex plus reserved-name validator on create and update
- `backend/src/environments/service.py`: `update_variable`, `delete_variable`, `resolve_env_vars(db, env_id) -> dict[str, str]` (reuses `decrypt_variable_value`)
- `backend/src/environments/router.py`: PATCH and DELETE routes
- `backend/src/execution/tasks.py`: `_get_env_config()` adds `"env_vars": resolve_env_vars(...)`, and `_get_runner()` passes it through
- `backend/src/execution/runners/subprocess_runner.py`: `__init__(venv_path, extra_env=None)`, `env.update(extra_env)` before the PATH/VIRTUAL_ENV lines, so those still win
- `backend/src/execution/runners/docker_runner.py`: `__init__(image, extra_env=None)`, merged into `env_vars`
- `frontend/src/api/environments.api.ts`: `updateVariable`, `deleteVariable`
- `frontend/src/stores/environments.store.ts`: `createVariable` / `updateVariable` / `deleteVariable` actions
- `frontend/src/views/EnvironmentsView.vue`: editable Variables section
- `frontend/src/i18n/locales/{en,de,fr,es}.ts`: `environments.addVariable`, `editVariable`, `deleteVariableConfirm`, `secret`, `secretUnchanged`, `invalidVarKey`, `reservedVarKey`
- `frontend/src/docs/content/{en,de,fr,es}.ts`: correct the `env-variables` section (actual UI location, `%{NAME}` usage, precedence)

### Test plan

- **pytest** `backend/tests/environments/test_env_variables_crud.py`: PATCH/DELETE happy path, 404 for a variable from another env,
  409 duplicate key, 422 reserved/invalid key, secret re-encrypted and an empty value keeps the old one, VIEWER gets 403.
- **pytest** `backend/tests/execution/test_subprocess_runner.py` (extend): `extra_env` reaches `Popen(env=…)`, and
  PATH/VIRTUAL_ENV are not overridable. `test_docker_runner.py` (extend): the container `environment` contains env vars, and a run variable wins a clash.
  `test_runner_interface_parity.py` stays green.
- **vitest** `frontend/src/tests/components/EnvironmentVariables.spec.ts`: add, edit and delete call the API; a secret renders as a password input.
- **e2e** extend `e2e/tests/environments.spec.ts`: add a variable, edit its value, delete it. The injection path is covered by pytest,
  because e2e would need a real venv run.

---

## Story V14.3: Export report test results as CSV / JSON

**As a** QA lead, **I want** to download a report's test results as CSV or JSON, **so that** I can analyse them in a
spreadsheet or hand them to a TMS without parsing `output.xml`.

**Evidence:** `reports/router.py` offers only `/zip`, `/html` and `/xml-data`, and `ReportDetailView.vue` has only
"Download ZIP". CSV/JSON export is a Phase 5 roadmap item.

### Acceptance criteria

- **AC1:** `GET /reports/{report_id}/export?format=csv` returns `text/csv; charset=utf-8` with a
  `Content-Disposition: attachment; filename=report_<id>_results.csv`. There is one row per `TestResult` with columns
  `suite_name, test_name, long_name, status, duration_seconds, tags, start_time, end_time, error_message`,
  written with stdlib `csv` (proper quoting of commas, quotes and newlines in `error_message`).
- **AC2:** `format=json` returns the same rows as a JSON array (the `TestResultResponse` shape) with a download filename.
- **AC3:** an invalid `format` returns 422 and an unknown report returns 404. Auth is the same as `GET /reports/{id}/tests`.
- **AC4 (CSV injection):** a cell starting with `=`, `+`, `-` or `@` is prefixed with `'` so spreadsheets don't execute it.
- **AC5 (UI):** `ReportDetailView.vue` gets "Export CSV" and "Export JSON" buttons next to "Download ZIP", using the
  same blob-download pattern as `downloadZip()`.

### Files to touch

- `backend/src/reports/router.py`: export route (reuses the query behind `/{report_id}/tests`)
- `frontend/src/api/reports.api.ts`: `exportReportResults(id, format)` returning a Blob
- `frontend/src/views/ReportDetailView.vue`: two buttons
- `frontend/src/i18n/locales/{en,de,fr,es}.ts`: `reportDetail.exportCsv`, `reportDetail.exportJson`

### Test plan

- **pytest** `backend/tests/reports/test_export.py`: CSV header plus row count, quoting of multi-line `error_message`,
  formula-prefix neutralisation, JSON shape, 422 for a bad format, 404 for a missing report.
- **vitest** `frontend/src/tests/components/ReportExport.spec.ts`: each button calls the API with the right format and triggers a download.
- **e2e** extend `e2e/tests/report-detail.spec.ts`: click "Export CSV", then assert `page.waitForEvent('download')` gives a filename ending in `.csv`.

---

## Story V14.4: Delete a single report

**As an** editor, **I want** to delete one obsolete or broken report, **so that** I don't have to choose between
living with clutter and wiping every report (today's only option, ADMIN-only).

**Evidence:** only `DELETE /reports/all` (`reports/router.py:110`) and 24h retention exist, and `reports.api.ts` has only `deleteAllReports`.

### Acceptance criteria

- **AC1:** `DELETE /reports/{report_id}` removes the report and its `TestResult` rows, and deletes the output directory
  (`Path(output_xml_path).parent`) **only if** that directory lies inside the configured reports/runs root. Returns 204, or 404 if the report is missing.
- **AC2 (role):** requires EDITOR. For reports linked to a run, the user needs effective role ≥ EDITOR on that run's repo. Uploaded reports
  (`execution_run_id is None`) use the global EDITOR floor.
- **AC3 (no dup):** the per-report file and DB deletion lives in one helper (`reports/service.py::delete_report`),
  and `delete_all_reports` loops over it, so the two paths cannot drift.
- **AC4 (UI):** a trash icon per row in `ReportsView.vue` and a "Delete report" button in `ReportDetailView.vue`, both with a
  confirm dialog. After deleting from the detail view, the user is navigated to `/reports`.
- **AC5:** the linked `ExecutionRun` is kept, and the run's report link degrades gracefully to "report deleted" rather than giving a 500.

### Files to touch

- `backend/src/reports/service.py`: `delete_report(db, report)` extracted from `router.delete_all_reports`
- `backend/src/reports/router.py`: `DELETE /{report_id}`, and `delete_all_reports` refactored to use the helper
- `frontend/src/api/reports.api.ts`: `deleteReport(id)`
- `frontend/src/views/ReportsView.vue`, `frontend/src/views/ReportDetailView.vue`: delete actions
- `frontend/src/i18n/locales/{en,de,fr,es}.ts`: `reports.deleteReport`, `reports.deleteReportConfirm`, `reports.deleted`

### Test plan

- **pytest** `backend/tests/reports/test_delete_report.py`: DB rows and directory removed; a directory outside the root is NOT removed;
  404; VIEWER gets 403; uploaded report deletable by EDITOR; `DELETE /all` still works (regression).
- **vitest** `frontend/src/tests/components/ReportDelete.spec.ts`: confirming calls `deleteReport` and removes the row, and cancelling does nothing.
- **e2e** extend `e2e/tests/reports.spec.ts`: upload a report, delete it from the list, and assert it is gone after a reload.

---

## Story V14.5: Per-file diff preview in the Publish modal

**As a** test author, **I want** to see what changed in each file before I commit and push, **so that** I don't
publish accidental edits (for example a Flow-Editor normalisation I didn't intend).

**Evidence:** `PublishModal.vue:43-47,167-180` lists paths with checkboxes only, `repos/service.py` has no diff function,
and `RepoStatusResponse` holds path lists only.

### Acceptance criteria

- **AC1:** `GET /repos/{repo_id}/diff?path=<repo-relative>` returns `{ path, status, diff, truncated }`. The `diff` is
  the unified diff of the working tree against `HEAD` (GitPython `repo.git.diff("HEAD", "--", path)`). An untracked
  file returns its full content as an all-added diff, and a deleted file returns an all-removed diff.
- **AC2 (safety):** `path` must resolve inside the repo root (the same traversal guard the explorer uses), otherwise 400.
  A non-git (local) repo returns 409. Output is capped at 200 KB with `truncated: true`, and a binary file returns
  `diff: null` with a `binary` status.
- **AC3 (role):** the same effective role as `GET /repos/{id}/status`.
- **AC4 (UI):** each path row in `PublishModal.vue` gets a "Show changes" toggle that lazily fetches and renders the diff
  in a `<pre>` with `+` and `-` lines coloured via CSS vars from `main.css`. There is no new diff library (offline, no dependency).
- **AC5:** toggling a diff does not change the row's checkbox selection.

### Files to touch

- `backend/src/repos/service.py`: `get_file_diff(local_path, rel_path, max_bytes=200_000)`
- `backend/src/repos/schemas.py`: `FileDiffResponse`
- `backend/src/repos/router.py`: `GET /{repo_id}/diff`
- `frontend/src/api/repos.api.ts`: `getFileDiff(id, path)`
- `frontend/src/components/repos/PublishModal.vue`: toggle and `<pre>` rendering
- `frontend/src/i18n/locales/{en,de,fr,es}.ts`: `repos.publish.showChanges`, `hideChanges`, `diffTruncated`, `binaryFile`

### Test plan

- **pytest** `backend/tests/repos/test_diff.py` (tmp git repo fixture): diff for a modified, untracked and deleted file;
  path traversal (`../etc/passwd`) gives 400; a local repo gives 409; a large file sets `truncated`; a binary file gives `diff: null`.
- **vitest** extend `frontend/src/tests/components/PublishModal.spec.ts`: the toggle fetches once and renders `+`/`-` lines,
  and the checkbox state is unchanged.
- **e2e** extend `e2e/tests/git-sync.spec.ts`: edit a file, open Publish, click "Show changes", and assert the diff contains the new line.

---

## Deferred to v0.15 (from the brainstorm shortlist)

- Saved run templates (G-4). Re-evaluate after V14.1: "Run now" on a paused schedule may cover it.
- JUnit export via `rebot --xunit` (G-15), a natural follow-up to V14.3.
- `%{ENV}` awareness in the Flow Editor (G-12, spec `flow-editor-followups/FE-ENV-environment-variables.md`), pairs with V14.2.
- Inert columns `ExecutionRun.max_retries` / `parallel`: wire them up or remove them from the UI (G-5/G-6).
- Repo delete orphans runs and recordings (G-26, open from the 0.12.1 review).
