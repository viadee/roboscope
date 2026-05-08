# Story SECURITY-4: Defensive typing on webhook payload extraction

Status: done

Epic: SECURITY / REFACTOR — backlog from CLAUDE.md "Known open issues"
Story Key: `security-4-webhook-payload-defensive-typing`

## Reported

Continuing the mypy-strict review-after-shipping pass (TYPE-5
covered the REPO modules). Three more real type-correctness bugs
in `src/webhooks/router.py` extractor helpers.

`POST /webhooks/git` accepts payloads from external providers
(GitHub, GitLab, attackers). The two helper functions
`_extract_git_url` and `_extract_branch` declared `str | None`
return types but implemented:

```python
ref = payload.get("ref", "")
if ref.startswith("refs/heads/"):    # AttributeError if ref is not a str
    return ref[len("refs/heads/"):]

# and
for key in ("clone_url", ...):
    if key in repo:
        return repo[key]               # returns Any, not str
```

A malformed (or hostile) payload like `{"ref": 42}` would crash the
endpoint with `AttributeError: 'int' object has no attribute
'startswith'`. The asset endpoint pre-existing tests exercised happy
paths only — none provided a non-string `ref`.

## Fix

Both helpers now use `isinstance(value, str)` guards:

```python
ref = payload.get("ref")
if isinstance(ref, str) and ref.startswith("refs/heads/"):
    return ref[len("refs/heads/"):]
return None
```

`_extract_git_url` does `value = repo.get(key); if isinstance(value, str): return value`
for both GitHub and GitLab key sets.

## Coverage

New `TestPayloadExtractors` class — 8 tests:
- 2× happy-path string returns (GitHub `clone_url`, GitLab
  `git_http_url`)
- 2× malformed-payload returns None (non-string clone_url,
  non-dict repository)
- 2× branch-extractor happy path (`refs/heads/main`,
  `refs/heads/feat/foo`)
- 2× branch-extractor defensive (non-branch ref like
  `refs/tags/v1.0`, missing ref, non-string ref including int /
  None / list — pre-fix this crashed with AttributeError)

## Verification

- `mypy --strict src/webhooks/router.py` — the 3
  `no-any-return` errors are gone (16 cosmetic findings remain,
  all `dict` should be `dict[str, Any]`-style annotation churn).
- `tests/webhooks/test_webhooks.py` 43/43 green incl. 8 new tests.
- The pre-existing `TestGitWebhookInbound` tests still pass — the
  guards only narrow types, they don't change happy-path behaviour.

## Out of scope

- **Validating webhook signatures** before parsing payloads. The
  current design has `# TODO: secret verification` comments around
  the inbound endpoint; that's a separate hardening story.
- **The remaining `dict` → `dict[str, Any]` churn** flagged by
  mypy. Cosmetic, deferred.
