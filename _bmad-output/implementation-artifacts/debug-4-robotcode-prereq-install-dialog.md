# Story DEBUG-4: RobotCode prereq detection + in-dialog install

Status: done

Epic: Interactive Robot Framework Debugger
Story Key: `debug-4-robotcode-prereq-install-dialog`
Depends on: DEBUG-1, DEBUG-2, DEBUG-3

## Story

As a Runner-role user clicking the `🐞 Debug` button or `▶ Bis hier ausführen` for the first time on a project,
I want a clear dialog telling me that RobotCode is not yet installed in the project's Python environment, with a one-click install or cancel,
so that I don't see a generic 500 toast and have to go figure out what `robotcode` is and how to install it manually.

## Background

`backend/src/debug/robot_debug_session.py::_spawn` looks for the `robotcode` binary at `<venv>/bin/robotcode` (or `<venv>/Scripts/robotcode.exe` on Windows). When missing, it raises `DebugSessionStartFailed("`robotcode` binary not found...")`. The DEBUG-2 router currently catches that as a 502 with a generic `"Could not start debug session: ..."` toast — useless for a fresh user who has no idea that RoboScope's debugger is RobotCode and that they need to install it.

## Acceptance Criteria

1. **AC1 — Backend prereq detection.** Before spawning the session, both `_start_from_run` and `_start_from_step` call `check_robotcode_available(env.venv_path)`. If `False`, return HTTP **424 Failed Dependency** with `detail = {code: "robotcode_not_installed", repo_id, env_id, package: "robotcode", message: "..."}`. The session is NOT spawned and NOT audited.

2. **AC2 — Backend install endpoint.** `POST /api/v1/debug/sessions/install-prerequisites` body `{repo_id: int}`. RBAC: RUNNER+. Resolves repo's default environment, runs `uv pip install robotcode` into the venv via `asyncio.create_subprocess_exec`, with a 300s timeout. Returns `{already_installed: bool, log_tail: str | null}`. 500 on install failure with stderr tail in `detail`.

3. **AC3 — Audit.** New `DEBUG_ROBOTCODE_INSTALLED` event emitted on successful install with `{repo_id, env_id, package, exit_code: 0}` payload. Failed installs are logged at WARN but not audited (consistent with other failed-action handling — audit captures successful state changes).

4. **AC4 — Frontend dialog.** `DebugPrereqDialog.vue` modal with localized title, body, and two buttons: `Install` (primary) and `Cancel`. Triggered when either entry point catches a 424. While installing: button disabled + spinner + "Installiere…" copy. On success: dialog closes, original debug-start request is automatically retried. On install failure: error toast with the log tail trimmed to fit, dialog stays open so the user can try again or cancel.

5. **AC5 — Both entry points wired.** RunDetailPanel `🐞 Debug` (DEBUG-2) AND FlowEditor `▶ Bis hier ausführen` (DEBUG-3) both surface the dialog. Single shared component + store action.

6. **AC6 — i18n EN/DE/FR/ES.** Keys: `debug.prereq.{title, body, install, cancel, installing, installFailed, installSuccess}`. Native-quality translations.

7. **AC7 — Tests.**
   - Backend: `tests/debug/test_prereq.py` — `check_robotcode_available` true/false, `install_robotcode` happy + non-zero exit + timeout (mocked `asyncio.create_subprocess_exec`). Router test: 424 path on missing binary, install endpoint happy path + already-installed branch.
   - Frontend: store test for the 424 catch + retry-after-install flow.

## Out of scope

- Installing other prereqs (Browser library, RPA libraries, etc.). DEBUG-4 is RobotCode-specific.
- Auto-detecting available updates. Once installed, stays installed.
- Choosing the package source (custom index URLs etc.). Default PyPI via uv.

## Dev notes

- `check_robotcode_available` is a pure path check — fast enough to inline before spawn, no caching needed.
- Use the existing `pip_install_cmd(venv_path, "robotcode")` builder; it goes through uv per project convention.
- The 424 status code is a deliberate match for "Failed Dependency" — semantically closer than 412 (Precondition Failed) which usually refers to request preconditions.
- `robotcode` (umbrella) pulls in `robotcode-cli` (CLI) + `robotcode-debugger` (DAP server). Installing the umbrella is friendlier than picking individual subpackages.
- Frontend: the dialog should NOT auto-retry on cancel; cancel returns the user to the prior view (run detail or flow editor) without starting a session.
