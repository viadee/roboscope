# Deferred Work

Findings surfaced during reviews that are out of scope for the triggering story.

## From gh-35 (fastmcp bump) review — 2026-06-15

- **Offline-bundle build swallows wheel-download errors** (`scripts/build-mac-and-linux.sh` ~L178/L186, `| grep ... || true`, `2>/dev/null || true`). If a transitive dep is sdist-only or lacks a wheel for a target ABI, the wheel is silently omitted from `wheels/` and the failure only surfaces at the customer's offline `install-mac-and-linux.sh` (`uv pip install --no-index`), which aborts under `set -euo pipefail`. Pre-existing design weakness; the fastmcp 3.x bump widened the transitive surface (added cyclopts, griffelib, jsonref, openapi-pydantic, opentelemetry-api, py-key-value-aio, watchfiles, …). All current new deps ship `py3-none-any` wheels (verified in uv.lock), so no break today — but the build should fail loudly on a missing wheel rather than ship an incomplete bundle. Suggested fix: collect download failures and exit non-zero (or assert wheel count) before packaging.

## From the security sweep (Dependabot, all 34 alerts) — 2026-06-15

- **starlette CVE GHSA-86qp-5c8j-p5mr (medium) — BLOCKED by FastAPI.** Host-header validation gap poisons `request.url.path`, bypassing path-based security checks. Fix is starlette `1.0.1`, but the latest FastAPI (0.135.4) still pins starlette `0.x` (resolves 0.52.1), so the fix is not reachable without breaking FastAPI. **Low real exposure for RoboScope:** RBAC is FastAPI-dependency-based (not `request.url.path` string matching), and prod runs behind a Host-validating nginx. Re-attempt once a FastAPI release supports starlette 1.x. (Pinning starlette `>=1.0.1` now would break the FastAPI install.)
- **Extension keeps TWO lockfiles** (`extension/package-lock.json` + `extension/yarn.lock`). Both are now patched + kept in sync (npm `overrides` + yarn `resolutions`), but yarn itself warns about mixing package managers, and Dependabot scans both (double alerts). Recommend standardizing on npm (the rest of the repo uses npm; no CI uses the extension lockfiles) and deleting `yarn.lock`. Not done here to avoid an unprompted tooling change.
