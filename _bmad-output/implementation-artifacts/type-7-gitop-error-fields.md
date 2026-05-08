# Story TYPE-7: Declare GitOperationError's conflict-recovery fields

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `type-7-gitop-error-fields`

## Reported

Continuing the close-look pass — this iteration audits
`# type: ignore` comments in the modules I touched, since they
often hide real design issues.

`backend/src/repos/service.py` had two `# type: ignore[attr-defined]`
comments and `backend/src/repos/router.py` had a matching
`getattr(e, "commit_hash", None)` defensive read. Pattern:

```python
# service.py
try:
    push_result = push_branch(local_path)
except GitOperationError as e:
    e.commit_hash = commit_result["commit_hash"]   # type: ignore[attr-defined]
    e.committed_files = commit_result["files"]    # type: ignore[attr-defined]
    raise

# router.py
except GitOperationError as e:
    commit_hash = getattr(e, "commit_hash", None)
    committed_files = getattr(e, "committed_files", None)
    ...
```

The intent is "commit landed locally; tell the router to surface
the commit hash + files so the user's work isn't lost on a 409
push-conflict response." The implementation worked at runtime but
was held together by tape:

- The exception didn't declare the fields, so writers needed
  `# type: ignore[attr-defined]`.
- The reader needed `getattr(e, ..., None)` because the static
  analyser couldn't see the attrs either.
- A future refactor could rename one side and the other side
  silently keeps reading `None`.

## Fix

Declared the optional fields directly on
`GitOperationError.__init__`:

```python
def __init__(self, kind: str, message: str):
    super().__init__(message)
    self.kind = kind
    self.commit_hash: str | None = None
    self.committed_files: list[str] | None = None
```

The two `# type: ignore[attr-defined]` comments are gone. The
router reads `e.commit_hash` / `e.committed_files` directly — no
more `getattr(...)` shuffle. The intent of the recovery path is
now self-documenting on the exception class.

## Verification

- `grep -rn "type: ignore\[attr-defined\]" src/repos/` — 0 matches
  in code, 1 in a docstring (which is correct — the new docstring
  references the pattern that was eliminated).
- `tests/repos/test_save_loop.py` — 17/17 still green. The
  publish-with-conflict test path exercises exactly the field-read
  the router does.

## Out of scope

- **The other type-ignore comments** (`auth/dependencies.py:119`
  re: `_auth_via_api_token`, the various `arg-type` ignores around
  header-string-to-int conversion). They're cleaner with the
  current code shape than the alternative refactors would be.
