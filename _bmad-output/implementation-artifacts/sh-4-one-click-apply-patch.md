# Story SH-4 — One-click apply-patch

**Type:** BMAD quick story (SH follow-up)
**Date:** 2026-04-24

## Background

SH-2 ends with the user copying a unified diff to their clipboard. SH-4 adds the obvious next step: a single API call + button that writes the swap directly into the `.robot` file. The safety contract stays intact — the action is only available on **confirmed** heals (suspect heals are excluded server-side too, not just in the UI).

## Acceptance Criteria

1. **Endpoint** `POST /api/v1/runs/{run_id}/heal-report/{heal_index}/apply` — accepts no body, returns `{file_path, line_number, applied}`. Requires **editor+**.
2. **Idempotent**: re-applying the same heal is a 200 with `applied: false` when the file already contains the healed selector on that line.
3. **Safety gates (rollback)**:
   - a. The target heal must be present in the audit (index bounds).
   - b. The heal's `outcome` must be `confirmed`. Suspect / unknown / skipped → 400.
   - c. The target `.robot` file must exist inside the run's repository root (same path-traversal guard as `/recordings/save`).
   - d. The *exact* line containing the original selector must be findable. If it appears multiple times or not at all in the file, **abort without writing** — never guess.
4. **Atomic write**: write to a temp file, `os.replace` to the target. A crash mid-write must not leave a half-written file.
5. The write is audited via `AuditEventType.HEAL_PATCH_APPLIED`.
6. **Frontend**: `RunHealReport.vue` confirmed-heal row gains an "Apply patch" button next to "Copy patch". Click → call endpoint → on success, flip row's badge to `✅ applied`. On 409 (line not found) or 400 (suspect/unknown), show the localised error inline.
7. **i18n** in EN/DE/FR/ES.
8. **Tests** — apply success, idempotent re-apply, suspect rejected, out-of-bounds index 404, missing file 404, ambiguous line 409.

## Out of scope

- Preview-before-apply diff modal. The patch body is already visible inline from SH-2; adding a modal is UI bloat.
- Undo / revert endpoint. Users `git diff` / `git checkout` to unwind; the audit log says who + when.
- Multi-patch bulk apply. One click = one patch.
