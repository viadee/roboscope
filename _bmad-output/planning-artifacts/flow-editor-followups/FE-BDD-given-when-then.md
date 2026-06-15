# Story FE-BDD: Gherkin/BDD prefix awareness in the Flow Editor

- **Status:** Planned
- **Priority:** P2 (visual polish)
- **Parent:** Flow Editor — Verification & Hardening (deferred item N3)

## Context
Robot Framework BDD prefixes (`Given`, `When`, `Then`, `And`, `But`) are pure
syntactic sugar — `Given user logs in` calls the keyword `user logs in` (or a
keyword literally named `Given user logs in`). Today the Flow Editor shows them
as ordinary keyword nodes; round-trip already preserves them. This story adds
**recognition + dezente visual treatment** so BDD suites read as BDD, and makes
sure the keyword-signature lookup strips the prefix when resolving args.

NOT in scope: a dedicated BDD authoring mode / step-library picker. (John:
no gold-plating.)

## Acceptance Criteria
- **AC1:** A keyword step whose name starts with a BDD prefix (case-insensitive
  `Given|When|Then|And|But` followed by whitespace) is flagged as BDD in the
  node data, and the node renders a small prefix badge / accent.
- **AC2:** Signature lookup for such a step resolves against the keyword name
  **with the prefix stripped** when the full name isn't found (so `When Login`
  shows `Login`'s args). The full name still wins if it exists verbatim.
- **AC3:** Round-trip is unchanged — the prefix stays part of the keyword text
  in the serialized `.robot` (no normalisation).
- **AC4:** Pure, unit-tested helper `bddPrefix(name)` → `{ prefix, rest } | null`.

## Tasks
- `robotKeywordSignatures.ts` (or a small `bdd.ts`): `splitBddPrefix(name)`.
- `useKeywordSignatures.ts`: fallback lookup on the stripped name.
- `flowConverter.ts`: set `bdd` flag on keyword node data.
- Flow node component CSS: prefix badge.
- i18n: none needed (prefixes are literal RF tokens).

## Tests
- Unit `FlowEditorBdd.spec.ts`: splitBddPrefix matrix; signature falls back to
  stripped name; verbatim full name preferred.
- e2e `flow-editor-bdd.spec.ts`: load a BDD suite, assert prefix badge renders
  and code round-trip keeps `Given/When/Then`.
