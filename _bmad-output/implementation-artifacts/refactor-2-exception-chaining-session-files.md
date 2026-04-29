# Story REFACTOR-2: B904 exception chaining in session-touched files

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `refactor-2-exception-chaining-session-files`

## Reported

After DEVEX-1 unblocked ruff in this loop session, B904 surfaced 62
findings: `raise ... from err` / `raise ... from None` is missing on
exceptions raised inside `except` blocks. Without the chain marker,
the original cause is hidden in `__context__` rather than `__cause__`,
and the traceback printer hides it behind:

> "During handling of the above exception, another exception
>  occurred"

— which obscures whether the second exception is a deliberate
translation or a bug in the handler.

This story applies the chain marker to **the modules I added or
substantially changed in this loop session** (16 of the 62 findings).
The other 46 are in older code; they're worth fixing too but each
file deserves its own scrutiny pass.

## Coverage

### `src/repos/service.py` — REPO-1 commit/push helpers (8 spots)

```diff
- raise GitOperationError("not_a_repo", "not a git repository")
+ raise GitOperationError("not_a_repo", "not a git repository") from None

- raise GitOperationError("other", f"git add failed: {e}")
+ raise GitOperationError("other", f"git add failed: {e}") from e
```

`from None` where the original (e.g. `InvalidGitRepositoryError`)
adds nothing; `from e` everywhere `as e` was bound — preserves the
GitCommandError's full output for ops debugging.

### `src/auth/router.py` — SECURITY-1 change-password (3 spots)

`change_password` raises `ValueError("wrong_current"|"too_short"|
"same_as_current")`. Each branch's `HTTPException(...)` now chains
with `from e`. Plus the existing `decode_token` 401 chains
`from None` (the JWT decode error message has no useful context for
a 401 response).

### `src/repos/router.py` — REPO-1 publish/commit/push routes (4 spots)

`raise _gitop_to_http(e)` and `raise HTTPException(409, …)` paths
now chain `from e` — when the publish endpoint surfaces a
non-fast-forward 409, the operator following the trace can see
which Git error caused it.

### `src/webhooks/router.py` — REPO-4 / earlier webhook CRUD (2 spots)

`except ValueError as e: raise HTTPException(422, detail=str(e))`
in webhook create + update — both chain.

## Verification

- `ruff check src/repos/{service,router}.py src/auth/{service,router}.py src/webhooks/router.py --select B904`
  — all checks passed.
- `pytest tests/repos/test_save_loop.py` — 17/17 still green
  (the chain change is observation-only — it doesn't alter the
  HTTP response or the exception's message).

## Out of scope

- The remaining 46 B904 findings in `src/explorer/`,
  `src/environments/`, `src/reports/`, etc. Each file warrants
  the same kind of scrutiny pass — not blocked by this story but
  not strictly within the loop's "session-shipped code" scope.
