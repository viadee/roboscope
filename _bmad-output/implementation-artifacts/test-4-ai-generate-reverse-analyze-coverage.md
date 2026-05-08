# Story TEST-4: AI generate / reverse / analyze / status / accept endpoint coverage

Status: done

Epic: TEST GAPS — backlog from CLAUDE.md "Test gaps (highest risk)"
Story Key: `test-4-ai-generate-reverse-analyze-coverage`

## Reported

CLAUDE.md "Test gaps":

> several AI + Report router endpoints

TEST-3 closed the provider-CRUD half. This story closes the
AI-work surface: the endpoints that actually mint background jobs
(spec→robot generation, robot→spec reverse, failure analysis) and
the lifecycle endpoints (`/status`, `/accept`).

Five endpoints, zero pre-existing router-level tests. Particularly
risky branches that were never exercised:
- `POST /generate` drift-check 409 when `target_file`'s on-disk hash
  differs from `metadata.generation_hash`.
- `POST /accept`'s four 400 reasons (job not completed, no preview,
  no target_path, repo gone).
- Default-vs-explicit `output_path` derivation in `/reverse`.
- `analyze` rejecting reports with zero failed tests.

## Coverage delivered

`tests/ai/test_generate_reverse_analyze.py` — **20 tests** in five classes:

1. **TestGenerate** (6) — happy path dispatches `run_generate` with
   the new job id; missing spec → 404; unknown repo → 404; runner
   forbidden (403); drift 409 when stale `generation_hash`; drift
   bypassed by `force=true`.

2. **TestReverse** (3) — happy path auto-derives `output_path`
   (`.robot` → `.roboscope`), explicit `output_path` honoured,
   missing robot file → 404. Dispatch is asserted to call
   `run_reverse`.

3. **TestAnalyze** (3) — happy path dispatches `run_analyze` with
   the report; unknown report → 404; report with zero failures → 400.

4. **TestJobStatus** (2) — fetches a pending job, 404 on unknown id.

5. **TestAccept** (6) — writes the file to disk on success, 404 on
   unknown job, 400 on each of the three "not ready" branches
   (status != completed, no `result_preview`, no `target_path`),
   runner forbidden (403).

## Testing approach

- The endpoints dispatch via `dispatch_task` which is **module-imported**
  at the top of `src/ai/router.py`. The mock patches the *local*
  binding (`src.ai.router.dispatch_task`), not the source module —
  patching the source has no effect because the import already
  copied the reference. (Cost a re-run to get right; documenting
  it for the next person.)

- `_seed_completed_job` takes the `provider` fixture explicitly
  (the AiJob model has `provider_id NOT NULL`).

- The drift-409 test uses a quoted `generation_hash` in the spec
  YAML — an unquoted `0000000000` parses as the integer 0, which is
  falsy, so the drift branch silently skips. Quoted strings reach
  the comparison and trigger the 409 as intended.

## Verification

`uv run pytest tests/ai/test_generate_reverse_analyze.py` →
20/20 in ~111 s. Combined with TEST-3, the AI router now has
40+ router-level tests.

## Out of scope

- The `run_generate` / `run_reverse` / `run_analyze` task functions
  themselves still rely on a real LLM; the existing
  `tests/ai/test_llm_client.py` covers the LLM client in isolation.
- Drift-rotation when `result_preview` lands and the user accepts
  is exercised end-to-end here only at the file-write level
  (`write_generated_file`); the `update_spec_hash` side-effect for
  `generate` jobs has its own service-layer tests.
