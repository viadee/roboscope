# Story AI-2 — AI-generated patch suggestions from failure analysis

**Type:** BMAD quick story (AI productivity)
**Date:** 2026-04-24

## Background

The existing `/ai/analyze` pipeline (Story A1 / A2 in older epics) produces a free-form markdown root-cause analysis: it explains *why* each failed test failed and suggests fix directions in prose. Users have to read the prose and manually translate "suggested fix" into an actual edit in their `.robot` file.

AI-2 closes that last metre: extend the `SYSTEM_PROMPT_ANALYZE` to optionally emit **unified-diff patches** in fenced ```` ```patch ```` blocks alongside the prose. The extractor pulls them out of the stored markdown, structures them with their target file, and surfaces them as copy-to-clipboard chunks in the Report detail view. No new DB column needed — everything rides on the existing `result_preview` text field.

## Acceptance Criteria

1. **Given** the analysis task calls the LLM, **when** the LLM includes one or more ```` ```patch ```` blocks whose body looks like a unified diff, **then** each block is extracted and returned on the `AiJobResponse` as `suggested_patches: [{file_path, unified_diff}]`.
2. **Given** the LLM returns prose only (no patch blocks), **then** `suggested_patches` is `[]` and the prose rendering is unchanged.
3. **Given** a patch block is malformed (no `--- a/<path>` header), **then** the extractor silently skips it rather than corrupting the whole response.
4. **Given** a valid analysis has suggested patches, **when** the user views the Report detail page, **then** a dedicated "Suggested patches" section lists each patch with its target file path, a monospace diff preview, and a "Copy patch" button.
5. **Given** clipboard access is unavailable, **when** the user clicks "Copy patch", **then** the button silently no-ops (no toast spam). The patch body is always visible for manual copy as a fallback.
6. **System prompt** — `SYSTEM_PROMPT_ANALYZE` gains one paragraph instructing the LLM to produce patches in standard unified-diff format inside ```` ```patch ```` fences, using `a/<repo-relative-path>` and `b/<repo-relative-path>` headers. Keep it optional: if the LLM can't identify a concrete line-level fix, no patch block.
7. **i18n** keys in EN/DE/FR/ES for the new section.
8. **Tests** — 5 pytest cases covering: single-patch extraction, multi-patch extraction, malformed-header skip, no-patch-blocks empty, patch with unicode content.

## Out of scope

- Applying the patch automatically (future AI-3 story). User copies → pastes into editor manually; safer first cut.
- Validating that the patch target file exists in the repo (the LLM can hallucinate paths — a separate check is future work).
- Extracting patches from the `generate` / `reverse` flows (different use case, unchanged prompt).
- New DB column for structured patch storage — `result_preview` stays the source of truth; the structured list is computed on read.
