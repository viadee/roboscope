# Story TYPE-5: Mypy strict narrowing for the REPO modules

Status: done

Epic: REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `type-5-mypy-narrowing-repos`

## Reported

Continuing the review-after-shipping pass. After running
`mypy --strict src/repos/service.py src/repos/tasks.py …` on the
modules touched in REPO-1..4, mypy flagged 17 issues. Most were
cosmetic (`dict` should be `dict[str, Any]`); two were real
correctness issues:

1. **`service.py:52` — `Path(data.local_path)`** where
   `data.local_path: str | None`. The `RepoCreate.validate_type_fields`
   model validator enforces non-null whenever `repo_type=='local'`,
   but mypy can't see across the validator. A future refactor that
   accidentally bypasses the validator (e.g. constructing a
   `RepoCreate` programmatically with default args) would crash with
   `TypeError: argument should be str, bytes…` deep in `pathlib`.

2. **`tasks.py:41` — `clone_repository(repo.git_url, …)`** where
   `Repository.git_url: Mapped[str | None]`. `clone_repository`
   requires a non-None string. Pydantic + the router both enforce
   that a git-typed repo has a URL, but a stray row from a
   half-failed migration or direct DB edit would crash GitPython's
   internals with a confusing error.

## Fix

1. **Service**: explicit `assert data.local_path is not None` with a
   message naming the validator. If the assertion ever fires, the
   stack trace points exactly at the missing validation.

2. **Task**: defensive early-return that writes
   `sync_status='error'`, `sync_error="No git URL configured"`,
   commits, and returns the standard error dict shape. The UI's
   sync-error badge surfaces the message instead of the user seeing
   a stuck "syncing" state forever.

## Verification

- `mypy --strict src/repos/{service,tasks}.py` — the two
  `incompatible type` errors are gone (the remaining 15 are
  generic-arg / annotation issues unrelated to this story).
- `pytest tests/repos/` — full repos suite still green.

## Out of scope

- **Cosmetic mypy fixes** (`dict[str, Any]` annotations on internal
  return types). Pure annotation churn; deferred to a TYPE-6 batch
  if the team wants `--strict` clean across the codebase.
- **Mypy on the router** — `src/repos/router.py` has 14 missing
  return-type annotations on FastAPI handlers. FastAPI's response
  models infer the type, so the runtime is fine; the lint is a
  style-only finding. Defer.
