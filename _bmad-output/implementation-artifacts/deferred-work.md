# Deferred Work

Findings surfaced during reviews that are out of scope for the triggering story.

## From gh-35 (fastmcp bump) review — 2026-06-15

- **Offline-bundle build swallows wheel-download errors** (`scripts/build-mac-and-linux.sh` ~L178/L186, `| grep ... || true`, `2>/dev/null || true`). If a transitive dep is sdist-only or lacks a wheel for a target ABI, the wheel is silently omitted from `wheels/` and the failure only surfaces at the customer's offline `install-mac-and-linux.sh` (`uv pip install --no-index`), which aborts under `set -euo pipefail`. Pre-existing design weakness; the fastmcp 3.x bump widened the transitive surface (added cyclopts, griffelib, jsonref, openapi-pydantic, opentelemetry-api, py-key-value-aio, watchfiles, …). All current new deps ship `py3-none-any` wheels (verified in uv.lock), so no break today — but the build should fail loudly on a missing wheel rather than ship an incomplete bundle. Suggested fix: collect download failures and exit non-zero (or assert wheel count) before packaging.
