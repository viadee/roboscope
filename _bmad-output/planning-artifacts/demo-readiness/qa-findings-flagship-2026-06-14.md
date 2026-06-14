# QA Findings — Flagship subsystems: Recorder / Heal / Debugger (2026-06-14)

BMAD QA edge-case audit. Fix status:

| ID | Sev | Subsystem | Finding | Status |
|---|---|---|---|---|
| C1 | CRITICAL | Heal | Sidecar `quality_score` (0–100) used directly as confidence → `60.0 >= 0.7` always true → threshold gate bypassed for ALL sidecar candidates (defeats the core heal safety invariant on recorded tests). | ✅ fixed (Pass 15: normalize /100 in candidate_finder; first vendored unit tests added) |
| H1 | HIGH | Heal | `get_run_heal_report` (any authed user) + `apply_heal_patch` (global EDITOR) bypass per-repo effective-role RBAC — global EDITOR w/o repo grant can write .robot files cross-repo. | ✅ fixed (Pass 15: `require_effective_role_for_run` VIEWER/EDITOR, mirrors cancel/retry) |
| C2 | CRITICAL* | Heal | Heal "success" recorded the instant the swapped keyword returns; relies entirely on the report layer reclassifying via output.xml. Missing output.xml → `unknown` (apply still rejects it, but UI doesn't flag it as suspect). | ⏳ follow-up (surface `unknown` distinctly; apply gate already rejects non-confirmed) |
| H2 | HIGH | Recorder | SSE single-subscriber documented but unenforced → two tabs split one SimpleQueue. | ✅ fixed (Pass 20: per-session active-subscriber flag; 2nd subscriber → 409; +2 tests) |
| H3 | HIGH | Debugger | `output_xml_walker` only descends `<kw>` → misses failures inside FOR/IF/TRY/WHILE → DEBUG-2 breakpoint lands at wrong line. | ✅ fixed (Pass 16: recurse FOR/IF/TRY/WHILE/iter/branch/group; +4 tests) |
| H4 | HIGH | Debugger | Racy start dedup → duplicate sessions + orphan subprocesses on double-click. | ✅ fixed (Pass 19: atomic in-lock dedup raises DuplicateDebugSessionError before spawn; +2 tests) |
| H5 | HIGH | Recorder | `_is_already_disambiguated` treats any `>>` as nth-safe → chained multi-match selectors skip the nth wrap → strict-mode replay crash. | ✅ fixed (Pass 18: only real nth markers count; +3 tests) |
| M1 | MED | Debugger | Path-traversal guard uses `startswith` (sibling-dir bypass). | ✅ fixed (Pass 16: relative_to) |
| M2 | MED | Recorder | Only first `Go To`/`New Page` gets `wait_until=domcontentloaded`; later navigations inherit `load` → hang on ad-heavy pages. | ✅ fixed (Pass 17: every Go To gets wait_until) |
| M3 | MED | Heal | `_should_retry` substring match (`timeout`, `locator(`) over-triggers heals on non-selector failures. | ✅ fixed (Pass 17: selector-resolution signatures only) |
| M4 | MED | Recorder | Restart-after-crash can tear down the queue → restarted browser with a dead stream. | ⏳ follow-up |
| M5 | MED | Heal | `_split_iframe_wrap` mismatches `>>`/`>>>` separators → heal silently won't fire for hand-edited iframe selectors. | ⏳ follow-up |
| L1/L2 | LOW | Recorder/Debug | Legacy generator unescaped + literal `***` secret; debug port TOCTOU. | ⏳ follow-up |

`*` C2: the apply gate already rejects any non-`confirmed` heal, so it is not exploitable for a bad on-disk write; the residual is a UI clarity gap.

**Coverage note:** the vendored RoboScopeHeal library had ZERO unit tests; Pass 15 adds the first (`tests/execution/test_heal_confidence_scale.py`). `backend/tests/debug/` is empty — the debugger fixes (H3/H4/M1) will add the first debug-walker/dedup tests.

New tests: `tests/execution/test_heal_confidence_scale.py` (C1, 3). Existing heal apply/report regression: 20 passed.
