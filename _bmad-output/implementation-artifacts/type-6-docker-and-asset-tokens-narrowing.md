# Story TYPE-6: Mypy strict pass on docker_client + asset_tokens

Status: done

Epic: REFACTOR / SECURITY — backlog from CLAUDE.md "Known open issues"
Story Key: `type-6-docker-and-asset-tokens-narrowing`

## Reported

Continuing the close-look review pass. After TYPE-5 (REPO modules)
and SECURITY-4 (webhook payload extractors), running
`mypy --strict` against the rest of the modules I shipped this
session surfaced two more findings — one defensive, one a real
brittle implementation-detail dependency.

### Finding 1 — `docker_client.py:_resolve_context_host`

```python
ctx = json.loads(out)
if isinstance(ctx, list) and ctx:
    host = ctx[0].get(...).get(...).get("Host", "")
    if host:
        return host
return None
```

`ctx[0]` is `Any` (json.loads returns `Any`); the entire
`.get(...).get(...).get(...)` chain stays `Any`; the function
declares `str | None`. A custom `docker context inspect` plugin or
future schema drift that returns a non-string `Host` (an int, a
list, …) would smuggle that value into our typed return — and
downstream `docker.DockerClient(base_url=host)` would crash with a
confusing error.

**Fix**: isinstance-narrow `ctx[0]` to dict, drop the empty-string
default on the inner `.get()`, isinstance-narrow `host` to str
before returning.

### Finding 2 — `asset_tokens.py:73` brittle `base64.binascii.Error`

```python
except (ValueError, base64.binascii.Error):
    return False
```

`base64` doesn't expose `binascii` in its public API. The attribute
access works at runtime *only* because `base64.py` happens to do
`import binascii` internally. A future Python release that switches
to a lazy import or moves the implementation would break this
catch silently — the verifier would propagate the exception instead
of returning `False`, leading to 500s on certain malformed tokens.

**Fix**: import `binascii` directly and reference its `Error` from
the public module surface.

## Coverage

Two new defensive-edge-case tests in `TestResolveContextHost`:

- `test_returns_none_on_non_string_host` — payload with
  `"Host": 12345`; pre-fix this returned the int as if it were a
  Host URL.
- `test_returns_none_on_non_dict_first_entry` — payload is a list
  whose first element is a string; pre-fix the .get() chain would
  raise `AttributeError`.

11/11 in `test_docker_client.py` (was 9; +2 defensive).
20/20 across `test_docker_client.py + test_asset_tokens.py`.

## Verification

`mypy --strict src/docker_client.py src/reports/asset_tokens.py`
— the 2 real findings are gone (1 cosmetic missing-return-annotation
remains).

## Out of scope

- **Cosmetic mypy churn** (missing return-type annotations on
  internal helpers) — deferred.
- **Pinning `binascii.Error` to the wrapped exceptions of
  `_b64url_decode` directly** — currently the catch is broader
  than needed but the cost is just "we silently `return False` on
  more error classes than absolutely required", which is the
  defensive direction we want anyway.
