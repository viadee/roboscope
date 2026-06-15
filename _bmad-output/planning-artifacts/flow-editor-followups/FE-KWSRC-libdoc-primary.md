# Story FE-KWSRC: libdoc-per-env as the universal keyword source

- **Status:** Planned
- **Priority:** P2
- **Parent:** Flow Editor — Verification & Hardening (deferred item: shrink the
  static fallback map)

## Context
Winston's guidance: "the static fallback map is Sisyphos — it ages faster than
you can maintain it; libdoc-per-env makes it superfluous. Shrink, don't grow."
The libdoc-per-environment endpoint (Story AC-C) is now the offline-first
source. This story makes libdoc the **primary** signature source everywhere and
**reduces** the static `RF_KEYWORD_SIGNATURES` map to a minimal bootstrap used
only before an environment has been introspected — without removing the safety
net entirely (Winston: only retire once libdoc reliably covers everything).

## Acceptance Criteria
- **AC1:** `useKeywordSignatures` precedence is documented + tested as:
  project > libdoc(env) > static-bootstrap. The static map NEVER overrides a
  libdoc entry for the same keyword.
- **AC2:** The static map is trimmed to a small, clearly-labelled BOOTSTRAP set
  (BuiltIn essentials only) — no third-party libraries (those come from libdoc).
  A comment + test pin its bootstrap-only role.
- **AC3:** When libdoc keywords are present for a keyword, its signature comes
  from libdoc even if the bootstrap also has it (regression test).
- **AC4:** No user-visible regression: with an introspected env, the palette and
  signatures are at least as complete as before (covered by existing tests +
  the libdoc path).

## Tasks
- `robotKeywordSignatures.ts`: split the map into `RF_BOOTSTRAP_SIGNATURES`
  (kept) and drop the third-party entries; keep `parseArgSignature` etc.
- `useKeywordSignatures.ts`: confirm/clarify precedence comment; ensure libdoc
  (explorer.keywords) overrides bootstrap.
- Adjust any references to removed entries.

## Tests
- Unit: bootstrap-only contents; libdoc overrides bootstrap; project overrides
  libdoc (already covered) still holds.
- e2e: with an environment introspected (libdoc), opening a Browser test shows
  Browser keyword signatures (already exercised by flow-editor-offline path).

## Risk
Removing entries other code imports. Grep for direct `RF_KEYWORD_SIGNATURES`
consumers first; keep the export name (re-export bootstrap) to avoid churn.
