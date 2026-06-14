# QA Findings — AI / Reports / TaskExecutor (2026-06-14)

BMAD QA edge-case audit of the next-highest-risk untested paths. Fix status:

| ID | Sev | Finding | Status |
|---|---|---|---|
| C1 | CRITICAL | `write_generated_file` had no path containment → a spec `target_file: ../../../x` writes arbitrary files (traversal). | ✅ fixed (`_contained_target` resolve+relative_to in write + update_spec_hash) |
| C2 | CRITICAL | `_strip_code_fences` only stripped a line-0 opening fence + last-line closing fence → an LLM prose preamble left a dangling fence → unparsable .robot. | ✅ fixed (extract balanced fenced block, tolerate prose) |
| H1 | HIGH | `_parse_suite` used a descendant iterator → nested suite names flattened → same-named tests in different suites collided. | ✅ fixed (recurse direct child suites, build dotted path) |
| H2 | HIGH | `_parse_test` used a `.//tag` descendant axis → pulled keyword-level tags into test tags. | ✅ fixed (read only the test's own tags container / pre-RF7 flat tag) |
| H4 | HIGH | Malformed LLM JSON (empty `choices` / missing content) → opaque IndexError/KeyError job failure. | ✅ fixed (validate → clear RuntimeError) |
| M1 | MED | AI dispatch-failure path used `db.flush()` not commit (job could strand pending). | ✅ fixed (commit on all 3 dispatch except paths) |
| H3 | HIGH | Rotated/invalid SECRET_KEY → AI key decrypt raises opaque InvalidToken; no "re-enter key" path. | ⏳ follow-up (typed error + consolidate ai/encryption into src/encryption) |
| M2 | MED | `delete_all_reports` orphans archive dirs on partial rmtree failure. | ⏳ follow-up |
| M3 | MED | `call_llm` fixed 300s timeout, no connect-timeout → a misconfigured provider freezes the single worker for 5 min. | ⏳ follow-up (httpx connect timeout + clear "provider unreachable") |
| M4 | MED | No spec/robot size cap before sending to the LLM. | ⏳ follow-up |
| L1/L2/L3 | LOW | zip-slip startswith (latent, not exploitable); is_encrypted broad except; RF7 duration-0 (known/tested). | ⏳ follow-up |

New tests: `tests/ai/test_ai_robustness.py` (C1, C2), `tests/ai/test_llm_client.py::TestEmptyContentHandling` (H4), `tests/reports/test_parser_hierarchy.py` (H1, H2). Affected-file regression: AI 76 passed + 49 robustness/llm; reports 26 passed.
