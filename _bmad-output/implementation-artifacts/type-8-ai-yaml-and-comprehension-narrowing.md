# Story TYPE-8: Mypy strict on AI router + service

Status: done

Epic: REFACTOR / SECURITY — backlog from CLAUDE.md "Known open issues"
Story Key: `type-8-ai-yaml-and-comprehension-narrowing`

## Reported

Continuing the close-look mypy pass. Two real findings in the AI
module (after filtering cosmetic `dict` → `dict[str, Any]` churn):

### Finding 1 — `service.py:parse_spec`

```python
def parse_spec(content: str) -> dict:
    return yaml.safe_load(content)
```

`yaml.safe_load` returns `Any`. The function declares `dict`. If the
spec content is well-formed YAML but doesn't decode to a mapping
(top-level list, scalar, or `None` for an empty file), downstream
`parsed.get(...)` calls in the router would crash with
`AttributeError: 'list' object has no attribute 'get'` —
confusing for the user trying to upload an empty spec.

### Finding 2 — `router.py:get_rf_keywords` comprehension

```python
return RfKeywordSearchResponse(
    results=[
        {"name": r.get("name", ""), "library": r.get("library", ""), ...}
        for r in results
    ]
)
```

The comprehension produces `list[dict[str, Any]]`; the response
field is `list[RfKeywordResult]`. Runtime works because Pydantic
auto-coerces dict→nested-model on `BaseModel.__init__`, but a
strictening of the model's validators (or a nested model with
required fields) would silently break.

## Fix

1. **`parse_spec`** — runtime guard:
   ```python
   parsed = yaml.safe_load(content)
   if not isinstance(parsed, dict):
       raise ValueError("Spec must be a YAML mapping at the top level …")
   return parsed
   ```
   The existing `validate_spec` callers already wrap with try/except,
   so the new error surfaces cleanly through the existing
   error-message channel.

2. **Comprehension** — build typed `RfKeywordResult` instances
   directly:
   ```python
   results=[
       RfKeywordResult(
           name=r.get("name", ""),
           library=r.get("library", ""),
           doc=r.get("doc", ""),
           args=r.get("args", []),
       )
       for r in results
   ]
   ```
   `RfKeywordResult` was already in `src.ai.schemas`; just imported
   into the router.

## Verification

- `mypy --strict src/ai/router.py src/ai/service.py` — both
  `no-any-return` and `incompatible type` errors are gone (cosmetic
  findings remain — generic-arg / annotation churn).
- AI router suite still green; the comprehension change is
  behaviour-equivalent (Pydantic coerces dicts identically), and
  the new `parse_spec` guard surfaces a cleaner error for malformed
  specs that wouldn't have parsed correctly anyway.

## Out of scope

- The `import yaml` lacks type stubs (`Library stubs not installed`)
  — installing `types-PyYAML` would close the warning. Cosmetic;
  defer.
- Other `dict` annotations (`dict[Any, Any]` everywhere) — pure
  annotation churn; defer.
