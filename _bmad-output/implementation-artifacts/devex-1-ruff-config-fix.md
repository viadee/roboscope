# Story DEVEX-1: Repair the ruff config (`make lint` was broken)

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `devex-1-ruff-config-fix`

## Reported

Continuing the close-look pass — running `ruff check src/` from
inside the backend hit:

```
ruff failed
  Cause: Failed to parse pyproject.toml
  Cause: TOML parse error
unknown field `extend-immutable-calls`, expected one of `allowed-confusables`, …
```

Two real bugs:

### B1 — `extend-immutable-calls` at the wrong nesting level

The config had `extend-immutable-calls` directly under
`[tool.ruff.lint]`. Ruff <0.15 accepted that as a top-level
shortcut; ruff 0.15+ moved it under `[tool.ruff.lint.flake8-bugbear]`
and rejects the old form with a fatal parse error.

`make lint` therefore failed before linting a single file. The
checks were silently never running on this repo.

### B2 — Project-local role-gating factories not whitelisted

Once ruff was running, B008 ("Do not perform function call in
argument defaults") fired 100 times against patterns like:

```python
_current_user: User = Depends(require_role(Role.EDITOR))
```

`Depends(...)` is whitelisted (immutable-call). The *inner*
`require_role(Role.EDITOR)` is a factory that builds the dependency
callable; calling it at function-definition time is the intended
FastAPI pattern, but ruff doesn't know that.

100 false positives drowned out the 421 real findings.

## Fix

`backend/pyproject.toml`:

```diff
 [tool.ruff.lint]
 select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM"]
-extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", ...]

+[tool.ruff.lint.flake8-bugbear]
+# Mark FastAPI dep-injection helpers as immutable so B008 doesn't
+# fire on every router signature. Nested under flake8-bugbear
+# because ruff 0.15+ rejects the option at top-level
+# [tool.ruff.lint] (the older flat form silently broke `make lint`
+# until this was moved).
+extend-immutable-calls = [
+    "fastapi.Depends",
+    "fastapi.Query",
+    "fastapi.Header",
+    "fastapi.Path",
+    # Project-local role-gating factories called inside `Depends(...)`
+    "src.auth.dependencies.require_role",
+    "src.auth.dependencies.require_effective_role",
+    "src.auth.dependencies.require_effective_role_for_run",
+]
```

## Verification

- `cd backend && .venv/bin/ruff check src/` — no parse error.
- Total findings: 523 → 421 (102 B008 false positives eliminated).
- `make lint` now actually runs the linters instead of failing on
  config parse.
- `tests/repos/test_save_loop.py + test_pre_run_sync.py` — 31/31
  sanity check still green; the config change has zero behaviour
  impact.

## Out of scope

- **Fixing the remaining 421 ruff findings** — most are import
  sorting (I001) and `raise ... from err` chaining (B904). The B904
  refactor is the highest-value follow-up (preserves exception
  context); deferred to its own story.
- **Pre-commit hook to enforce ruff** — would catch this earlier;
  separate devex story.
