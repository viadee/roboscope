Perfect! Now I have a comprehensive view of all the routers. Let me create the structured inventory markdown now:

# DEMO-READINESS FUNCTION INVENTORY: RoboScope Backend

## AUTH & RBAC

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| User login | `POST /api/v1/auth/login` | `auth/router.py::login` | Authenticate via email/password, return access/refresh JWT tokens | UI login form | Rate-limited to 10 attempts/5min/IP; invalid credentials logged per attempt |
| Token refresh | `POST /api/v1/auth/refresh` | `auth/router.py::refresh_token` | Mint new access token from valid refresh token | Auto-refresh in browser; manual POST | Rejects non-refresh token types; inactive users rejected |
| Current user profile | `GET /api/v1/auth/me` | `auth/router.py::get_me` | Retrieve authenticated user + teams + effective roles per repo (Phase 4) | After login; AJAX poll on startup | Teams list, default_team_id, per-repo effective_roles_by_repo returned |
| First-login tutorial | `PATCH /api/v1/auth/me/first-login-complete` | `auth/router.py::patch_first_login_complete` | Mark onboarding walkthrough as dismissed | Dismiss banner after first login | Returns full MeResponse with flag set |
| Password change | `POST /api/v1/auth/change-password` | `auth/router.py::change_password_endpoint` | Rotate current user's password; clears password_change_required flag | Settings > Security > Change Password | Min 8 chars; rejects same-as-current; can be forced on first login (Story SECURITY-1) |
| List users (admin) | `GET /api/v1/auth/users` | `auth/router.py::list_users` | Paginated user list (admin only) | Admin > Users tab | Pagination: skip/limit; soft-deleted users excluded |
| Create user (admin) | `POST /api/v1/auth/users` | `auth/router.py::register_user` | Register new user with initial password (admin only) | Admin > Users > Add User | Conflict on duplicate email; user starts is_active=true |
| Get user (admin) | `GET /api/v1/auth/users/{user_id}` | `auth/router.py::get_user` | Fetch user details (admin only) | Admin > Users > select row | 404 if not found |
| Update user (admin) | `PATCH /api/v1/auth/users/{user_id}` | `auth/router.py::patch_user` | Modify role/is_active/password (admin only); cascade-revoke API tokens on deactivate (Story 5-3) | Admin > Users > edit role/status | Deactivation emits audit event + revokes all active ApiTokens; rejects self-deactivation |
| Delete/deactivate user (admin) | `DELETE /api/v1/auth/users/{user_id}` | `auth/router.py::delete_user` | Soft-delete user + cascade-revoke tokens (Story 5-3) | Admin > Users > delete icon | 404 if already inactive; emits audit with revocation count |
| RBAC role hierarchy | `src/auth/constants.py` | `auth/constants.py` | Role enum: VIEWER(0) < RUNNER(1) < EDITOR(2) < ADMIN(3) | All endpoint guards use `require_role(Role.X)` | API tokens cap at Role; teams inherit role from membership |
| API token auth | `src/auth/service.py` + `auth/dependencies.py` | `auth/service.py`, `auth/dependencies.py` | SHA256-hashed tokens (`rbs_…`) accepted alongside JWT in Authorization header or query param | `POST /webhooks/tokens` to create; pass as Bearer token | Tokens are scoped to user + role; inactive users' tokens rejected |

---

## REPOS & GIT INTEGRATION

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| List repos | `GET /api/v1/repos` | `repos/router.py::get_repos` | User-visible repository list; filtered by team/project membership (Phase 4) | Sidebar on app startup | Empty list if user has no team/project grants |
| Validate branch | `POST /api/v1/repos/validate-branch` | `repos/router.py::validate_branch` | Check if branch exists on remote; suggest main/master fallbacks | During repo creation, branch selector | Returns remote branches list; useful for typo detection |
| Create repo | `POST /api/v1/repos` | `repos/router.py::add_repo` | Register new git/local repo; auto-add creator as editor; dispatch clone task | UI: Repos > Add Repo | Conflict on duplicate name; git repos trigger async clone; sync_status initially "pending" |
| Get repo | `GET /api/v1/repos/{repo_id}` | `repos/router.py::get_repo` | Fetch repository metadata | Click repo in sidebar | 404 if not found |
| Update repo | `PATCH /api/v1/repos/{repo_id}` | `repos/router.py::patch_repo` | Modify name/description/default_branch/environment (effective role = EDITOR) | Repo settings panel | Requires repo-level EDITOR role or global ADMIN |
| Delete repo | `DELETE /api/v1/repos/{repo_id}` | `repos/router.py::remove_repo` | Hard-delete repo (effective role = ADMIN) | Repo settings > Delete | 204 response; all runs + reports orphaned; workspace dir left on disk |
| Assign team (admin) | `PUT /api/v1/repos/{repo_id}/team` | `repos/router.py::assign_team` | Assign repo to team / clear team_id (Story 3-2) | Admin > Repos > reassign team | Emits audit event; team_id=null clears ownership |
| Sync repo | `POST /api/v1/repos/{repo_id}/sync` | `repos/router.py::sync_repo` | Trigger async git fetch/merge from remote | Explorer header: Sync button | Local repos return 200 "skipped"; git repos dispatch `sync_repo` task |
| Get repo status | `GET /api/v1/repos/{repo_id}/status` | `repos/router.py::get_status` | Working-tree + tracking-branch divergence snapshot (untracked/modified/ahead/behind) | Explorer: Save badge count | Read-only; visible to all users; local repos return empty |
| Commit changes | `POST /api/v1/repos/{repo_id}/commit` | `repos/router.py::commit` | Stage paths + commit with user's email/name (Story REPO-1) | UI: Save panel > Commit button | GitOperationError mapped to 400/409/502 HTTP; local repos reject |
| Push changes | `POST /api/v1/repos/{repo_id}/push` | `repos/router.py::push` | Push current branch to tracked upstream | UI: Save panel > Push button | Non-fast-forward → 409 with commit metadata for pull+retry UX |
| Publish (commit+push) | `POST /api/v1/repos/{repo_id}/publish` | `repos/router.py::publish` | Atomic commit + push; on NFR conflict, returns 409 with safe commit hash (Story REPO-1) | UI: Save panel > Publish button | NFR preserves user's work locally; response includes fallback guidance |
| List branches | `GET /api/v1/repos/{repo_id}/branches` | `repos/router.py::get_branches` | Local branches in the repo | Branch selector dropdown | Parsed from `.git/refs/heads/`; empty list for new repos |
| Checkout branch | `POST /api/v1/repos/{repo_id}/checkout` | `repos/router.py::checkout_branch_endpoint` | Switch branch + update repo.default_branch | Branch selector > choose item | Error if branch doesn't exist; git repos only |
| List project members | `GET /api/v1/repos/{repo_id}/members` | `repos/router.py::get_members` | Project-level RBAC: users + their repo-scoped roles | Repo > Members tab | Includes username/email; sorted by role desc |
| Add project member | `POST /api/v1/repos/{repo_id}/members` | `repos/router.py::add_member` | Grant user access to this repo with a role (RUNNER/EDITOR/ADMIN) | Repo > Members > Add button | 409 if already member; returns expanded member object |
| Update member role | `PATCH /api/v1/repos/{repo_id}/members/{member_id}` | `repos/router.py::patch_member` | Modify user's role in this repo | Repo > Members > role dropdown | 404 if member not found in repo |
| Remove member | `DELETE /api/v1/repos/{repo_id}/members/{member_id}` | `repos/router.py::delete_member` | Revoke user's repo access | Repo > Members > delete icon | Idempotent (404 if already removed) |

---

## EXPLORER (Test File Browsing & Editing)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Get file tree | `GET /api/v1/explorer/{repo_id}/tree` | `explorer/router.py::get_tree` | Recursive directory listing with test/resource/other classification | Explorer sidebar tree expansion | Path validation prevents traversal; binary files get `is_binary: true` flag |
| Get file content | `GET /api/v1/explorer/{repo_id}/file?path=…&force=false` | `explorer/router.py::get_file` | Read file; binary detection + `force` param bypasses null-byte check | Double-click file in tree | 403 on traversal attempt; `force=true` ignores binary detection |
| Search in repo | `GET /api/v1/explorer/{repo_id}/search?q=…&file_type=…` | `explorer/router.py::search` | Full-text search across test cases/keywords/files | Explorer: search box | Filters by .robot/.resource/.roboscope optionally |
| List all test cases | `GET /api/v1/explorer/{repo_id}/testcases` | `explorer/router.py::get_testcases` | All test cases indexed by suite + name | Test plan view; Run creation dialog | Includes tags; empty for repos with no .robot files |
| Get project keywords | `GET /api/v1/explorer/{repo_id}/keywords` | `explorer/router.py::get_project_keywords` | User-defined keyword declarations from .robot/.resource files | Keyword autocomplete in editor | Excludes built-in + library keywords |
| Library check | `GET /api/v1/explorer/{repo_id}/library-check?environment_id=…` | `explorer/router.py::library_check` | Cross-reference repo imports vs installed packages + docker image (if set) | Environments tab: diagnostics panel | Missing count for venv + docker separately; builtin libraries auto-pass |
| Create file | `POST /api/v1/explorer/{repo_id}/file` | `explorer/router.py::create_new_file` | Create new .robot/.resource/.roboscope in the repo | Right-click folder > New File | 409 if file exists; 403 on path traversal; auto-creates parent dirs |
| Save file | `PUT /api/v1/explorer/{repo_id}/file` | `explorer/router.py::save_file` | Overwrite file content | Editor save (Ctrl+S) | 404 if file doesn't exist; creates directories if missing |
| Delete file | `DELETE /api/v1/explorer/{repo_id}/file?path=…` | `explorer/router.py::delete_existing_file` | Remove file from repo | Right-click file > Delete | 403 on permission error; 404 if gone; path validation |
| Rename/move file | `POST /api/v1/explorer/{repo_id}/file/rename` | `explorer/router.py::rename_existing_file` | Rename or move file within repo | Right-click file > Rename | 409 if target exists; 403 on traversal; preserves content |
| Open file in editor | `POST /api/v1/explorer/{repo_id}/file/open` | `explorer/router.py::open_file_in_editor` | Launch system default editor (no response body) | Right-click file > Open in Editor | 404 if file gone; 403 on traversal; uses `os.startfile` (Windows) or `open` (macOS/Linux) |
| Open folder in browser | `POST /api/v1/explorer/{repo_id}/folder/open` | `explorer/router.py::open_folder_in_file_browser` | Launch Finder/Explorer/Nautilus | Right-click folder > Open in File Browser | 404 if folder gone; 403 on traversal |

---

## EXECUTION (Test Runs, Schedules, Cancellation, Healing)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Start test run | `POST /api/v1/runs` | `execution/router.py::start_run` | Create + dispatch execution; env's default_runner_type overrides subprocess request | UI: Test panel > Run button | Rate-limited 20/min; task dispatch failure sets status=ERROR; RUNNER role required |
| List runs | `GET /api/v1/runs?page=…&repository_id=…&status=…` | `execution/router.py::get_runs` | Paginated execution history | Runs tab / Reports view | Filters by repo + status; 100 items max per page |
| Get run detail | `GET /api/v1/runs/{run_id}` | `execution/router.py::get_run_detail` | Full execution record: status/duration/error_message/output_dir | Click run in list | 404 if not found |
| Get run pending activity | `GET /api/v1/runs/{run_id}/pending-activity` | `execution/router.py::get_run_pending_activity` | Queue position / ahead_count / active Docker build status + log tail (Story EXEC-1) | Run detail panel, polling while pending | Emits for all statuses; only meaningful when status=PENDING |
| Selector health diagnosis | `GET /api/v1/runs/{run_id}/selector-health` | `execution/router.py::get_run_selector_health` | Extract failed locators from run output; cross-ref with v2 recorder sidecar candidates (Story SH-1) | Run failure > Selector Health panel | Returns empty list if no sidecar or output |
| Get heal report | `GET /api/v1/runs/{run_id}/heal-report` | `execution/router.py::get_run_heal_report` | Parse heal_audit.jsonl; categorize heals as confirmed/suspect based on test outcome (Story SH-2) | Run detail > Heal Report tab | All-zero totals if no heal audit file |
| Apply heal patch | `POST /api/v1/runs/{run_id}/heal-report/{heal_index}/apply` | `execution/router.py::apply_heal_patch` | Write confirmed heal swap into .robot file; idempotent; preserves rbs comment ID (Story SH-4) | Heal Report > Copy Patch button | 409 if line is ambiguous or missing; 400 if outcome≠confirmed; emits audit |
| Cancel run | `POST /api/v1/runs/{run_id}/cancel` | `execution/router.py::cancel_run_endpoint` | Abort pending/running execution; kill subprocess/container | Run detail > Cancel button | Sets status=CANCELLED; kills active runner process |
| Cancel all runs | `POST /api/v1/runs/cancel-all` | `execution/router.py::cancel_all_runs` | Bulk cancel all pending+running (RUNNER role) | Admin panel > Kill All Runs | Returns count; best-effort subprocess kill |
| Retry run | `POST /api/v1/runs/{run_id}/retry` | `execution/router.py::retry_run_endpoint` | Clone failed/errored/timed-out run + re-dispatch | Run detail > Retry button | Creates new run row; copies test spec + environment |
| Get run stdout/stderr | `GET /api/v1/runs/{run_id}/output?stream=…` | `execution/router.py::get_run_output` | Stream test runner logs as plain text | Run detail > Logs tab | Returns "" if output_dir or log file missing |
| Get run report | `GET /api/v1/runs/{run_id}/report` | `execution/router.py::get_run_report` | Fetch linked report ID (if output.xml parsed) | Run detail > Report link | Returns `{report_id: null}` if no parsed report |
| Create schedule | `POST /api/v1/schedules` | `execution/router.py::add_schedule` | Define cron-triggered recurring run | Schedules tab > Create button | Cron syntax validated; EDITOR role required |
| List schedules | `GET /api/v1/schedules` | `execution/router.py::get_schedules` | All active + inactive schedules | Schedules tab | Includes is_enabled flag |
| Update schedule | `PATCH /api/v1/schedules/{schedule_id}` | `execution/router.py::patch_schedule` | Modify cron/description/is_enabled | Schedule row > edit | EDITOR role required |
| Delete schedule | `DELETE /api/v1/schedules/{schedule_id}` | `execution/router.py::remove_schedule` | Remove schedule (not runs it created) | Schedule row > delete | EDITOR role required |
| Toggle schedule | `POST /api/v1/schedules/{schedule_id}/toggle` | `execution/router.py::toggle_schedule_endpoint` | Enable/disable without re-editing | Schedule row > toggle checkbox | Idempotent on repeated calls |

---

## ENVIRONMENTS (venv/uv, Package Management, Browser Provisioning)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| List environments | `GET /api/v1/environments` | `environments/router.py::get_environments` | All venv + docker environments | Environments tab | Includes venv_path, docker_image, build status |
| Create environment | `POST /api/v1/environments` | `environments/router.py::add_environment` | Provision new venv with python version validation | Environments > Create button | Python version normalized; compatibility warnings returned; task dispatch creates venv |
| Setup default environment | `POST /api/v1/environments/setup-default` | `environments/router.py::setup_default_environment` | Auto-create roboscope-default with RF batteries + detect Docker | First run; Setup wizard | Conflict if already exists; queues venv create + package installs |
| Get environment | `GET /api/v1/environments/{env_id}` | `environments/router.py::get_env` | Fetch environment details | Environment detail view | 404 if not found |
| Update environment | `PATCH /api/v1/environments/{env_id}` | `environments/router.py::patch_env` | Modify name/description/default_runner_type/is_default | Environment settings > edit | EDITOR role required |
| Delete environment | `DELETE /api/v1/environments/{env_id}` | `environments/router.py::remove_env` | Remove venv + docker image | Environment > delete icon | ADMIN role required; soft-delete (workspace stays on disk) |
| Clone environment | `POST /api/v1/environments/{env_id}/clone?new_name=…` | `environments/router.py::clone_env` | Duplicate environment + package list | Environment row > Clone | Venv creation + package installs queued; idempotent name check |
| Get Dockerfile | `GET /api/v1/environments/{env_id}/dockerfile` | `environments/router.py::get_dockerfile` | Generate Dockerfile for manual build | Environment > View Dockerfile | 400 if no packages; text/plain response |
| Trigger Docker build | `POST /api/v1/environments/{env_id}/docker-build` | `environments/router.py::docker_build` | Dispatch async image build | Environment > Build Docker Image | Sets docker_build_status="building"; queues task; image_tag returned |
| Dismiss Docker error | `POST /api/v1/environments/{env_id}/docker-build-dismiss` | `environments/router.py::dismiss_docker_build_error` | Clear build status/error display | Build panel > dismiss button | Clears docker_build_status + docker_build_error |
| List packages | `GET /api/v1/environments/{env_id}/packages` | `environments/router.py::get_packages` | Packages + status (installed/pending/failed) + rfbrowser init flag | Environment > Packages tab | Detects browser variant (standard vs batteries) |
| Get installed packages | `GET /api/v1/environments/{env_id}/packages/installed` | `environments/router.py::get_installed_packages` | Raw pip list output (name/version) | Package inspector view | Aggregated from venv (if exists) |
| Get RF libraries | `GET /api/v1/environments/{env_id}/packages/rf-libraries` | `environments/router.py::get_rf_libraries` | Installed packages identified as RF keyword libraries (known + heuristic) | Library autocomplete source | Uses library_mapping heuristics for unknown packages |
| Get popular packages | `GET /api/v1/environments/packages/popular` | `environments/router.py::get_popular_packages` | Curated RF library list | Package installer dialog | Includes "shipped_with_roboscope" flag for vendored libraries |
| Search PyPI | `GET /api/v1/environments/packages/search?q=…` | `environments/router.py::search_packages` | Search PyPI by name | Package installer > search box | Query min 2 chars, max 100; returns summary/version |
| Install package | `POST /api/v1/environments/{env_id}/packages` | `environments/router.py::install_package` | Add package to venv; conflict check for browser variants | Environment > Packages > Install | Conflict on competing browser (seleniumlibrary vs browser-batteries); task dispatch installs |
| Upgrade package | `POST /api/v1/environments/{env_id}/packages/{package_name}/upgrade` | `environments/router.py::upgrade_package` | Clear version constraint + re-install latest | Package row > upgrade icon | Sets install_status="pending" |
| Retry package install | `POST /api/v1/environments/{env_id}/packages/{package_name}/retry` | `environments/router.py::retry_package_install` | Retry failed installation | Package row > retry button | Clears install_error; re-queues task |
| Uninstall package | `DELETE /api/v1/environments/{env_id}/packages/{package_name}` | `environments/router.py::uninstall_package` | Remove package from venv | Package row > delete | Task dispatch uninstalls; removes DB record |
| rfbrowser init | `POST /api/v1/environments/{env_id}/rfbrowser-init` | `environments/router.py::run_rfbrowser_init` | Manual `rfbrowser init` trigger for standard browser library | Browser library > init button | 400 if browser not installed; dispatches background task |
| List environment variables | `GET /api/v1/environments/{env_id}/variables` | `environments/router.py::get_variables` | Env vars (secret values masked as `********`) | Environment > Variables tab | Includes is_secret flag; secrets never returned in plaintext |
| Create environment variable | `POST /api/v1/environments/{env_id}/variables` | `environments/router.py::create_variable` | Add env var; encrypt if is_secret=true (Fernet via SECRET_KEY) | Environment > Variables > Add button | Secrets stored encrypted; legacy plaintext still decrypts |

---

## REPORTS (Output Parsing, Asset Serving, Export)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| List reports | `GET /api/v1/reports?page=…&repository_id=…` | `reports/router.py::get_reports` | Paginated report metadata (no test results) | Reports tab | Filters by repo; excludes orphaned archive reports |
| Delete all reports | `DELETE /api/v1/reports/all` | `reports/router.py::delete_all_reports` | Hard-delete all report rows + output directories (ADMIN only) | Admin panel > Purge Reports | Returns count + dirs_cleaned |
| Upload archive | `POST /api/v1/reports/upload` | `reports/router.py::upload_archive` | Ingest offline report ZIP (output.xml mandatory) | Reports > Upload button | Zip Slip validation; 500MB limit (Content-Length pre-check + streaming); parses XML |
| Compare reports | `GET /api/v1/reports/compare?report_a=…&report_b=…` | `reports/router.py::compare` | Side-by-side test result diff | Reports > select two > Compare | Returns pass/fail deltas + slowest tests |
| Get unique tests | `GET /api/v1/reports/tests/unique?search=…&limit=…` | `reports/router.py::get_unique_tests` | All unique test names + latest status + run count | Test history panel | Limit 50–200; optional search filter |
| Get test history | `GET /api/v1/reports/tests/history?test_name=…&suite_name=…&days=…` | `reports/router.py::get_test_history_endpoint` | Pass/fail timeline for one test | Click test in history > trend chart | Days 1–365; optional suite filter |
| Detect missing libraries | `GET /api/v1/reports/{report_id}/missing-libraries` | `reports/router.py::get_missing_libraries` | Parse failed tests for "library not found" errors + suggestions | Report detail > Diagnostics panel | Regex patterns for Robot/Browser/Playwright errors |
| Get report detail | `GET /api/v1/reports/{report_id}` | `reports/router.py::get_report_detail` | Full report + test results + optional diagnostic banner (Story EXECUTE-1) | Click report in list | Includes diagnostic detection (missing rfbrowser, etc.) |
| Get report HTML | `GET /api/v1/reports/{report_id}/html?token=…` | `reports/router.py::get_report_html` | 302-redirect to asset URL with minted short-lived token (Story SECURITY-3) | Report > view HTML button | Needs JWT or query token; redirects to `/assets/report.html?at=…` |
| Get report asset | `GET /api/v1/reports/{report_id}/assets/{file_path}?at=…` | `reports/router.py::get_report_asset` | Serve file from report output dir (screenshots, etc.) with auth (asset token OR JWT) | Iframe loads report.html; links resolve to assets | Path-traversal guard via relative_to(); base href injection on HTML files |
| Download report ZIP | `GET /api/v1/reports/{report_id}/zip?token=…` | `reports/router.py::get_report_zip` | Stream entire report directory as ZIP archive | Report > Download ZIP | Uses StreamingResponse; auth required (token or Bearer) |
| Get XML data | `GET /api/v1/reports/{report_id}/xml-data` | `reports/router.py::get_report_xml_data` | Deep-parsed output.xml with full keyword hierarchy + execution logs | Advanced KPI view | Uses defusedxml for XXE hardening; 404 if file missing |
| Get report tests | `GET /api/v1/reports/{report_id}/tests?status=…` | `reports/router.py::get_report_tests` | Individual test results (optional status filter: PASSED/FAILED/SKIPPED) | Report > Tests tab | Sorted by execution order |

---

## STATS & ANALYSIS (KPI Aggregation, Flaky Quarantine, Heatmaps)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Get overview KPI | `GET /api/v1/stats/overview?days=…&repository_id=…` | `stats/router.py::overview` | Pass rate / fail rate / total tests / avg duration | Dashboard KPI cards | Days 1–365; optional repo filter; defaults 30 days |
| Get success rate | `GET /api/v1/stats/success-rate?days=…&repository_id=…` | `stats/router.py::success_rate` | Trend points (date/success_percent) | Dashboard line chart | Used for SLA tracking |
| Get trends | `GET /api/v1/stats/trends?days=…&repository_id=…` | `stats/router.py::trends` | Trend points (pass/fail/error counts per day) | Dashboard stacked bar chart | Aggregated across all runs in period |
| Get heal rate | `GET /api/v1/stats/heal-rate?days=…&repository_id=…` | `stats/router.py::heal_rate` | Heals per day + confirmation rate (Story SH-6) | Healing metrics panel | Empty if no heals in window |
| Get flaky tests | `GET /api/v1/stats/flaky?days=…&min_runs=…&repository_id=…` | `stats/router.py::flaky_tests` | Tests with mixed pass/fail (min_runs threshold); quarantine status merged in (Story FLAKY-1) | Flaky Tests tab | Min runs 2–infinite; merges quarantine flag |
| List quarantine | `GET /api/v1/stats/quarantine?repository_id=…` | `stats/router.py::list_flaky_quarantine` | Quarantined flaky tests; optional repo filter | Flaky Tests > Quarantine panel | Sorted by ID descending |
| Add quarantine | `POST /api/v1/stats/quarantine` | `stats/router.py::add_flaky_quarantine` | Mark test as quarantined (Story FLAKY-1); idempotent (repo_id, suite_name, test_name) | Flaky test row > Quarantine button | Emits audit event if first time; returns existing if duplicate |
| Remove quarantine | `DELETE /api/v1/stats/quarantine/{quarantine_id}` | `stats/router.py::remove_flaky_quarantine` | Unquarantine test | Quarantine list > delete icon | Emits audit event |
| Get duration stats | `GET /api/v1/stats/duration?days=…&repository_id=…&limit=…` | `stats/router.py::duration_stats` | Slowest tests (avg + max duration) | Duration KPI panel | Limit 1–100; defaults 20 |
| Get heatmap | `GET /api/v1/stats/heatmap?days=…&repository_id=…&limit=…` | `stats/router.py::heatmap` | Failure heatmap (test × day grid) | Heatmap visualization | Days 1–90; limit 1–100; hand-rolled CSS grid |
| Aggregate KPIs | `POST /api/v1/stats/aggregate?days=…` | `stats/router.py::aggregate_kpis` | Trigger background KPI aggregation from ExecutionRun → KpiRecord | Admin panel > recalculate | Days 1–3650; idempotent |
| Get data status | `GET /api/v1/stats/data-status` | `stats/router.py::data_status` | Last aggregation date vs last finished run (staleness indicator) | Dashboard > data status badge | Useful for staleness detection |
| Available KPIs | `GET /api/v1/stats/analysis/kpis` | `stats/router.py::available_kpis` | Metadata for all available KPIs (ID, name, description) | Analysis builder | Returns AVAILABLE_KPIS enum |
| Create analysis | `POST /api/v1/stats/analysis` | `stats/router.py::create_analysis_endpoint` | Create analysis job + dispatch background computation (Story PHASE-5) | Analysis > Create New button | Rate-limited 10/min; validates KPI IDs; RUNNER role required |
| List analyses | `GET /api/v1/stats/analysis?page=…&page_size=…` | `stats/router.py::list_analyses_endpoint` | Paginated analysis records (without results blob) | Analysis history list | Includes status/progress fields |
| Get analysis | `GET /api/v1/stats/analysis/{analysis_id}` | `stats/router.py::get_analysis_endpoint` | Full analysis with results JSON | Analysis detail view | 404 if not found |

---

## AI GENERATION & ANALYSIS (LLM, Prompts, Spec/Test Gen, Reverse)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| List providers | `GET /api/v1/ai/providers` | `ai/router.py::get_providers` | All configured LLM providers (OpenAI/Anthropic/OpenRouter/Ollama) | Admin > AI Settings > Providers | API keys never returned in response |
| Create provider | `POST /api/v1/ai/providers` | `ai/router.py::add_provider` | Register new LLM provider with API key (Fernet-encrypted) (ADMIN) | Admin > AI Settings > Add Provider | Encrypts api_key_encrypted via Fernet; temperature clamped per-provider |
| Update provider | `PATCH /api/v1/ai/providers/{provider_id}` | `ai/router.py::edit_provider` | Modify provider config (ADMIN) | Provider row > edit | Rejects unknown provider types |
| Delete provider | `DELETE /api/v1/ai/providers/{provider_id}` | `ai/router.py::remove_provider` | Remove provider (ADMIN) | Provider row > delete | 404 if not found |
| Generate robot | `POST /api/v1/ai/generate` | `ai/router.py::generate_robot` | Transform .roboscope spec → .robot file via LLM (Story GEN-1); drift detection (force override) | Spec editor > Generate button | Drift check (generation_hash vs current file hash) unless force=true; EDITOR role |
| Reverse robot | `POST /api/v1/ai/reverse` | `ai/router.py::reverse_robot` | Extract .roboscope spec from existing .robot file (Story REVERSE-1) | .robot file > Reverse to Spec button | Spec path auto-derived if not provided; EDITOR role |
| Analyze failures | `POST /api/v1/ai/analyze` | `ai/router.py::analyze_failures` | AI failure analysis on report; extract suggested patches (Story AI-2) | Report > Analyze button | Requires report with failed tests; returns analysis + patch suggestions |
| Job status | `GET /api/v1/ai/status/{job_id}` | `ai/router.py::job_status` | Poll job status (pending/running/completed/failed) + result_preview + error_message | Async polling while job runs | Returns full job record for UI consumption |
| Accept job | `POST /api/v1/ai/accept` | `ai/router.py::accept_job` | Finalize job result: write .robot/spec file to repo; update generation_hash (Story GEN-1) | Generated preview > Accept button | 400 if not completed or no result; writes file atomically; EDITOR role |
| Validate spec | `POST /api/v1/ai/validate` | `ai/router.py::validate_spec_endpoint` | Validate .roboscope YAML syntax + count test cases | Spec editor > validate button | Returns valid/errors/test_count |
| Drift check | `GET /api/v1/ai/drift/{repo_id}` | `ai/router.py::drift_check` | Scan repo for .roboscope/.robot pairs with generation_hash mismatches | Repo > Maintenance > Drift Check | Lists files that have drifted post-generation |
| rf-knowledge status | `GET /api/v1/ai/rf-knowledge/status` | `ai/router.py::rf_knowledge_status` | Check if rf-mcp server is configured + available | AI Settings > rf-mcp status badge | Returns available flag + server URL |
| Search keywords | `GET /api/v1/ai/rf-knowledge/keywords?q=…&repo_id=…` | `ai/router.py::rf_knowledge_keywords` | Search Robot Framework keywords via rf-mcp; optionally import repo's custom keywords first (async) | Keyword autocomplete | If repo_id provided, custom keywords discoverable |
| Invalidate keyword cache | `POST /api/v1/ai/rf-knowledge/keywords/invalidate` | `ai/router.py::rf_knowledge_invalidate_cache` | Clear cached keyword list for repo so next search re-scans | Repo > refresh keyword cache button | Async endpoint |
| Recommend libraries | `POST /api/v1/ai/rf-knowledge/recommend` | `ai/router.py::rf_knowledge_recommend` | Get library recommendations for a test description via rf-mcp (async) | Spec editor > Recommend Libraries button | Async; returns library list |
| rf-mcp status | `GET /api/v1/ai/rf-mcp/status` | `ai/router.py::rf_mcp_status` | Detailed rf-mcp server status (running/port/pid/error) (async) | Admin > AI Settings > rf-mcp panel | Resolves environment name from ID |
| rf-mcp setup | `POST /api/v1/ai/rf-mcp/setup` | `ai/router.py::rf_mcp_setup` | Start rf-mcp server with environment for library discovery (ADMIN) (async) | Admin > AI Settings > Start rf-mcp button | Validates environment; queues background start task; persists auto-start settings |
| rf-mcp stop | `POST /api/v1/ai/rf-mcp/stop` | `ai/router.py::rf_mcp_stop` | Stop managed rf-mcp server (ADMIN) (async) | Admin > AI Settings > Stop rf-mcp button | Disables auto-start; clears persisted config |
| Xray export | `POST /api/v1/ai/xray/export` | `ai/router.py::xray_export` | Convert .roboscope spec content to Xray JSON format (EDITOR) | Spec editor > Export to Xray button | YAML parse error → 400; EDITOR role |
| Xray import | `POST /api/v1/ai/xray/import` | `ai/router.py::xray_import` | Convert Xray JSON to .roboscope v2 YAML (EDITOR) | Xray integration > import flow (EDITOR) | Returns YAML as string; EDITOR role |

---

## RECORDING (Chrome Recorder v2, Capture, Playback, Flow Generation)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Create recording session (v1) | `POST /api/v1/recordings` | `recording/router.py::create_recording_endpoint` | Provision new recording for extension or Playwright | Extension > new recording button OR web recorder create | Rate-limited 20/min; RUNNER role |
| List recordings (v1) | `GET /api/v1/recordings?page=…&repository_id=…&status=…` | `recording/router.py::list_recordings_endpoint` | Paginated v1 recording sessions | Recordings tab | Filters by repo + status |
| Get recording (v1) | `GET /api/v1/recordings/{recording_id}` | `recording/router.py::get_recording_endpoint` | Fetch recording details | Click recording in list | 404 if not found |
| Delete recording (v1) | `DELETE /api/v1/recordings/{recording_id}` | `recording/router.py::delete_recording_endpoint` | Remove recording + generated .robot (EDITOR) | Recording > delete icon | EDITOR role |
| Start recording (v1) | `POST /api/v1/recordings/{recording_id}/start` | `recording/router.py::start_recording_endpoint` | Transition to RECORDING state (ready for events) | Extension > start recording | Must be PENDING; RUNNER role |
| Start browser (v1) | `POST /api/v1/recordings/{recording_id}/start-browser` | `recording/router.py::start_browser_recording_endpoint` | Launch headed Chromium for in-app recording (Story W.1) (v1 predecessor) | Web recorder > launch browser | Dispatches Playwright task; fails if ROBOSCOPE_RECORDER_DISABLED set; headless check via $DISPLAY |
| Append event (v1) | `POST /api/v1/recordings/{recording_id}/event` | `recording/router.py::append_event_endpoint` | Add user action (click/type/scroll) to recording | Extension posts events | Must be RECORDING; broadcasts via WebSocket |
| Stop recording (v1) | `POST /api/v1/recordings/{recording_id}/stop` | `recording/router.py::stop_recording_endpoint` | End capture; optionally dispatch .robot generation | Extension > stop button | Sends stop signal to Playwright if running; generates robot if requested |
| Cancel recording (v1) | `POST /api/v1/recordings/{recording_id}/cancel` | `recording/router.py::cancel_recording_endpoint` | Abort recording without saving | Recording > cancel | Must not be COMPLETED/FAILED |
| Get generated .robot (v1) | `GET /api/v1/recordings/{recording_id}/robot` | `recording/router.py::get_generated_robot` | Download generated test file | Recording detail > view .robot button | 404 if not generated; plain text response |
| Get recording events (v1) | `GET /api/v1/recordings/{recording_id}/events` | `recording/router.py::get_recording_events` | Captured events JSON | Recording detail > events panel | Parses JSON from events_json; returns array |
| Recorder capabilities (v2) | `GET /api/v1/recordings/sessions/capabilities` | `recording/router.py::v2_recorder_capabilities` | Report which transports the backend host can drive (Story DEPLOY-1) | Recorder launcher transport selection | Checks $DISPLAY/$WAYLAND_DISPLAY on Linux; always yes on macOS/Windows |
| Create v2 session | `POST /api/v1/recordings/sessions` | `recording/router.py::v2_create_session` | Provision v2 RecordingSession for web/desktop transport (Story W.1 stub + W.8) | Recorder launcher > select transport > create | Effective-role check inline; auto-aborts other user's active sessions (AR-10) |
| Save recorded flow (v2) | `POST /api/v1/recordings/save` | `recording/router.py::v2_save_flow` | Serialize RecordedFlow to .robot + emit .rbs.json sidecar (Story W.6) | Recorder UI > Save & Save button (Story RECORDER-VIS-1) | Path-traversal guard; validates against RecordedFlow schema; emits audit |
| Start browser (v2) | `POST /api/v1/recordings/sessions/{session_id}/start-browser` | `recording/router.py::v2_start_browser` | Launch Chromium / UIA for v2 session (Story W.1 full + D.1) | Recorder UI > launch browser | URL scheme validation (http/https only); dispatches v2_recorder or desktop task |
| Restart browser (v2) | `POST /api/v1/recordings/sessions/{session_id}/restart-browser` | `recording/router.py::v2_restart_browser` | Restart Chromium without dropping captured commands (Story RECORDER-VIS-1) | Recorder UI > restart browser icon | Waits 5s for previous task to vacate; returns 409 if timeout; emits lifecycle events |
| Abort v2 session | `DELETE /api/v1/recordings/sessions/{session_id}` | `recording/router.py::v2_abort_session` | Cancel active v2 session; signal stop to active tasks | Recorder UI > abort session | Signals both v2 + desktop tasks (no-op if already dead); emits audit |
| Reset stuck sessions | `POST /api/v1/recordings/sessions/reset` | `recording/router.py::v2_reset_stuck_sessions` | Panic button: cleanup all stuck RECORDING sessions for current user (Story RECORDER-RESET-1) | Recorder UI > reset panic button (if sessions orphaned) | Idempotent; best-effort signal to dead tasks; returns aborted count |
| v2 command stream (SSE) | `GET /api/v1/recordings/sessions/{session_id}/commands` | `recording/router.py::v2_command_stream` | Single-subscriber server-sent event stream of RecordedCommand + LifecycleEvent (Story W.2) | Recorder live view | Auth via query `?token=<jwt>` OR Authorization header; returns 409 if 2nd subscriber |

---

## SETTINGS & CONFIG (Admin Settings, Docker, SSO Emergency Bypass)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| List settings | `GET /api/v1/settings?category=…` | `settings/router.py::get_settings` | All app settings (optional category filter) (ADMIN) | Admin > Settings tab | Category filter optional |
| Update settings | `PATCH /api/v1/settings` | `settings/router.py::patch_settings` | Bulk settings update (ADMIN) | Settings form > save | ADMIN role required |
| Get Docker status | `GET /api/v1/settings/docker-status` | `settings/router.py::get_docker_status` | Docker daemon info + container/image counts (ADMIN) | Admin > Docker Status panel | 200 with `connected: false` + error if Docker unavailable |
| SSO emergency bypass status | `GET /api/v1/settings/sso-emergency-bypass` | `settings/router.py::get_emergency_bypass_status` | Check if bypass is active + expiry time (ADMIN) | Admin > SSO panel > bypass status | Returns max_hours + current expiry |
| Activate emergency bypass | `POST /api/v1/settings/sso-emergency-bypass` | `settings/router.py::activate_emergency_bypass` | Enable local login fallback for `hours` (Story 5-1) (ADMIN) | Admin > SSO panel > activate button | Rejects duration > SSO_EMERGENCY_BYPASS_MAX_HOURS; emits audit |
| Deactivate emergency bypass | `DELETE /api/v1/settings/sso-emergency-bypass` | `settings/router.py::deactivate_emergency_bypass` | Disable emergency bypass (ADMIN) | Admin > SSO panel > deactivate button | Idempotent; emits audit if was active |

---

## WEBHOOKS & API TOKENS (Git Triggers, Event Subscriptions, CI/CD Auth)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Create API token | `POST /api/v1/webhooks/tokens` | `webhooks/router.py::create_token` | Mint new CI/CD token (rbs_…) with expiry + role cap (ADMIN) | Admin > API Tokens > Create | Plaintext shown once; SHA256-hashed in DB; auto-expires after `expires_in_days` |
| List API tokens | `GET /api/v1/webhooks/tokens` | `webhooks/router.py::get_tokens` | All active tokens (plaintext never returned) (ADMIN) | Admin > API Tokens tab | Includes created_by, expires_at, is_active |
| Revoke token | `DELETE /api/v1/webhooks/tokens/{token_id}` | `webhooks/router.py::delete_token` | Deactivate token (ADMIN) | Token row > revoke | Idempotent; 404 if not found |
| Reassign token | `POST /api/v1/webhooks/tokens/{token_id}/reassign` | `webhooks/router.py::reassign_token` | Transfer token to new owner; re-cap at owner's role (Story 5-4) (ADMIN) | Token row > reassign user | Role cap tightening-only (no elevation); emits audit |
| Get available events | `GET /api/v1/webhooks/events` | `webhooks/router.py::get_available_events` | List of event types webhooks can subscribe to (e.g. run.completed, repository.synced) | Webhook creation > event selector | Static list from VALID_EVENTS |
| Create webhook | `POST /api/v1/webhooks/hooks` | `webhooks/router.py::create_hook` | Create webhook subscription for repo (EDITOR) | Repo > Webhooks > Create | URL SSRF validation (RFC1918 + localhost blocked unless enabled) |
| List webhooks | `GET /api/v1/webhooks/hooks?repository_id=…` | `webhooks/router.py::get_hooks` | All webhooks (optional repo filter) | Webhooks tab | Secret never returned; has_secret flag instead |
| Get webhook | `GET /api/v1/webhooks/hooks/{webhook_id}` | `webhooks/router.py::get_hook` | Webhook details | Webhook row detail panel | 404 if not found |
| Update webhook | `PATCH /api/v1/webhooks/hooks/{webhook_id}` | `webhooks/router.py::update_hook` | Modify URL/events/is_active (EDITOR) | Webhook > edit button | EDITOR role required |
| Delete webhook | `DELETE /api/v1/webhooks/hooks/{webhook_id}` | `webhooks/router.py::delete_hook` | Remove webhook (EDITOR) | Webhook > delete icon | EDITOR role required |
| Test webhook | `POST /api/v1/webhooks/hooks/{webhook_id}/test` | `webhooks/router.py::test_hook` | Send test ping to webhook URL (EDITOR) | Webhook > test button | Sends sample payload; returns status code + response time |
| Get deliveries | `GET /api/v1/webhooks/hooks/{webhook_id}/deliveries?limit=…` | `webhooks/router.py::get_deliveries` | Recent webhook delivery history (status + response) | Webhook > deliveries tab | Limit 1–100 |
| Git webhook inbound | `POST /api/v1/webhooks/git` | `webhooks/router.py::git_webhook_inbound` | GitHub/GitLab push webhook receiver (unauthenticated; HMAC verification future) | External git provider > push event | Matches repo by git_url (tries with/without .git suffix); auto-triggers run if matched |

---

## AUDIT & COMPLIANCE (Event Logging, Retention, PII Hashing)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| List audit logs | `GET /api/v1/audit?page=…&user_id=…&action=…&resource_type=…&date_from=…&date_to=…` | `audit/router.py::get_audit_logs` | Paginated audit log with filters (ADMIN) | Admin > Audit Log tab | All POST/PUT/PATCH/DELETE auto-logged; rich filter set |
| Export audit as CSV | `GET /api/v1/audit/export?…filters…` | `audit/router.py::export_audit` | Bulk audit export with same filters (ADMIN) | Audit tab > export button | Streaming CSV response; includes all filtered rows |
| Get filter options | `GET /api/v1/audit/filters` | `audit/router.py::get_filter_options` | Available action + resource_type values (ADMIN) | Audit filter dropdowns | Distinct values from AuditLog table |
| Trigger retention | `POST /api/v1/audit/retention/run?dry_run=…` | `audit/router.py::trigger_retention` | Manually enforce data retention (ADMIN) (Story COMPLIANCE-1) | Admin panel > run retention button | Dry-run mode previews deletions; report_retention_days from settings |
| Auto-retention scheduler | Background task via APScheduler | `audit/retention.py` + `main.py` | 24h-scheduled enforcement of report/run age limits | Auto-runs per schedule | Configurable retention_days; soft-deletes (files left on disk) |
| Audit middleware | Sync middleware in FastAPI request pipeline | `middleware/audit.py` | Auto-log all POST/PUT/PATCH/DELETE + user/IP/detail | Every data-mutating request | Captures method/path/status/user_id/ip_address |

---

## HEALTH & INFRASTRUCTURE (Status Checks, Encryption, WebSocket, Tasks)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Health check | `GET /health` | `main.py` | Deep health check: DB SELECT 1, returns 503 if outage | Frontend keeps-alive / LB probe | Returns 200 OK or 503 Service Unavailable |
| Metrics endpoint | `GET /metrics` (Prometheus format, if enabled) | N/A (future Phase 5) | Prometheus-compatible metrics (Phase 5 feature) | Monitoring system scrape | Not yet implemented |
| WebSocket notifications | `WS /ws?token=<jwt>` | `websocket/manager.py` | Real-time event broadcast (run status, build progress, etc.) | Frontend auto-connects on app load | Token required; bad token → close code 4401; one connection per user (pooled) |
| Background task dispatch | `dispatch_task(func, *args, **kwargs)` | `task_executor.py` | Queue work to ThreadPoolExecutor(max_workers=1) + return Future | All long-running ops (clone, build, execute, analysis) | FIFO ordering; single-threaded; db.commit() MUST precede dispatch |
| Secret encryption | `encrypt_value() / decrypt_value()` | `encryption.py` | Fernet-encrypt env vars + LLM API keys; legacy plaintext gracefully decrypts | Store is_secret=True env vars | Derives from SECRET_KEY; rotating key orphans encrypted data |

---

## TEAMS & MULTI-TENANCY (Phase 4 Organizations)

| Feature | API Endpoint / Mechanism | Source File(s) | One-line Description | Demo Entry Point | Notable Edge Cases |
|---------|--------------------------|-----------------|---------------------|------------------|--------------------|
| Team CRUD | `/api/v1/teams` endpoints | `teams/router.py` | Create/read/update/delete teams; members inherit role from team (Story 3-1 + 3-2) | Admin > Teams tab | Teams own repositories; users get effective_roles per repo from team + project membership |
| Team members | `/api/v1/teams/{team_id}/members` endpoints | `teams/router.py` | Add/remove team members with role (ADMIN) | Team > Members tab | Role inherited by all repos owned by team |
| Group mappings (SSO) | `/api/group-mappings` endpoints (idp_router.py stub) | `auth/idp_router.py` | Map IdP groups to Roboscope teams for SSO (Story 4-5) | Admin > SSO > group mappings | Auto-add users from IdP groups (future Phase 4.5 work) |

---

## NOTES & BOUNDARIES

### Architectural Constraints (Must-Demonstrate Edge Cases)
1. **ThreadPoolExecutor(max_workers=1)** — all background tasks FIFO; cannot be "optimized" to N workers
2. **Sync-only FastAPI handlers** — no `async def` routes; WebSocket I/O via captured `_event_loop`
3. **db.commit() BEFORE dispatch_task()** — background thread uses separate session; uncommitted rows invisible
4. **FK-resolution imports in tasks.py** — each task module must import `src.auth.models`, `src.repos.models`, etc.
5. **WebSocket broadcast from bg thread** — use `asyncio.run_coroutine_threadsafe()`, never `asyncio.run()`
6. **Offline-first** — no CDN, no external API calls; air-gapped deployments must work
7. **Secrets never logged** — LLM keys, passwords, JWT, Fernet payloads masked in logs

### Cross-Cutting Features Requiring Demo
- **Auth boundaries** — VIEWER/RUNNER/EDITOR/ADMIN role enforcement; project-level overrides (Phase 4)
- **Audit trail** — all mutations logged; audit middleware auto-capture; retention enforced
- **Error state rendering** — every endpoint has 400/401/403/404/409/422/429/500/502/503 paths
- **Concurrency** — cancelled runs mid-execution; restart browser without dropping commands; stuck session cleanup
- **Large data** — reports > 500MB rejected; upload streaming; async ZIP download
- **Malformed input** — invalid YAML specs, path traversal attempts, binary files, circular refs, null bytes
- **Git conflicts** — non-fast-forward push returns 409 with safe commit metadata; user-initiated pull+retry
- **Secrets handling** — env vars encrypted at rest; decrypted at runner dispatch; legacy plaintext still works
- **Asset auth** — report assets require short-lived scoped tokens OR JWT; path-traversal guard on all asset paths

---

**Total Feature Count: 180+ endpoints/mechanisms covering all backend domains.**