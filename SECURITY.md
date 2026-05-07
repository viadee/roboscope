# Security Policy

## Reporting a Vulnerability

If you believe you've found a security issue in RoboScope, please **do not
open a public GitHub issue**. Instead, send a report to
[security@viadee.de](mailto:security@viadee.de) with:

- A description of the issue and its impact.
- Steps to reproduce (or a proof-of-concept exploit).
- Affected version(s) — RoboScope release tag and/or commit hash.
- Your preferred contact for follow-up.

We aim to acknowledge reports within **2 business days** and to ship a
patch (or a documented mitigation) for high-severity issues within
**14 days** of confirmation. For lower-severity issues we'll coordinate
a release window with you.

If you want to encrypt your report, our PGP key is published at
<https://viadee.de/security.asc>.

## Supported Versions

We patch security issues on the **latest released minor** of RoboScope
(currently the `0.9.x` line). Older minors receive critical fixes only,
and only on request — please reach out via the address above if you are
running an older release and need a backport.

## Known Third-Party Advisories

This section documents upstream advisories that GitHub's Dependabot
flags against our dependency tree but that are **not exploitable in
RoboScope's usage** as of the current release. We track each one and
will pull in the upstream fix as soon as the dependency chain allows.

### `fastmcp` 2.14.x — three advisories, not exploitable in RoboScope

`fastmcp` reaches our dependency tree as a transitive dep of
[`rf-mcp`](https://pypi.org/project/rf-mcp/), which RoboScope auto-starts
on `127.0.0.1:9090` to power keyword discovery, library
recommendations, and the AI `.roboscope ↔ .robot` generation flow.

`rf-mcp 0.31.x` declares `fastmcp >= 2.8.0` (no upper bound), but
`fastmcp 3.x` includes API breaks that `rf-mcp` does not yet support.
We therefore pin `fastmcp < 3` in `backend/pyproject.toml` until
`rf-mcp` ships a release built against `fastmcp >= 3.2.0` — tracked
in [issue #35](https://github.com/viadee/roboscope/issues/35).

The three open advisories on `fastmcp < 3.2.0` are:

| Advisory | Severity | Affected API | RoboScope exposure |
|---|---|---|---|
| [GHSA-vv7q-7jx5-f767](https://github.com/advisories/GHSA-vv7q-7jx5-f767) | critical | `OpenAPIProvider` (SSRF + Path Traversal) | not used — `rf-mcp` exposes keyword-discovery tools, never spins up an OpenAPI-derived MCP server |
| [GHSA-rww4-4w9c-7733](https://github.com/advisories/GHSA-rww4-4w9c-7733) | high | `OAuthProxy` callback (Confused Deputy) | not used — `rf-mcp` has no OAuth proxy flow |
| [GHSA-m8x7-r2rg-vh5g](https://github.com/advisories/GHSA-m8x7-r2rg-vh5g) | medium | `gemini-cli` MCP-tool injection | not used — RoboScope calls LLM providers directly via `httpx`, no gemini-cli integration |

The `rf-mcp` server itself listens only on the loopback interface
(`127.0.0.1`) and is not exposed externally by RoboScope's default
configuration. Operators who deliberately bind `rf-mcp` to a public
interface should track issue #35 and apply the upstream patch as soon
as it lands — until then, a public bind expands the threat model.

If your deployment treats any of these vulnerable code paths as
reachable (e.g., you wired `rf-mcp` into an external MCP gateway), we
recommend pinning `fastmcp >= 3.2.0` manually and accepting the
`rf-mcp` compatibility risk.
