## Deferred from: code review of flow-editor-hardening (2026-06-14)

- FQN `Library.Keyword` disambiguation for genuine cross-library keyword-name ambiguity (AC-C4 second clause). Precedence project>library>BuiltIn is implemented; the fully-qualified tiebreak is not. Low impact — project/resource keywords already win and true library-vs-library collisions are rare.
- Multi-line `[Tags]` / `[Setup]` / `[Teardown]` `...` continuation lines are dropped by the parser (pre-existing behavior carried over from the original RobotEditor parser). Real round-trip gap for multi-line settings; not introduced by this epic.
- A `[Template]` data cell whose value literally equals a control marker (`IF`/`FOR`/`END`/`VAR`/`RETURN`/…) is classified as a control step rather than a data cell. RF itself is ambiguous here; kept the RF-aligned default and documented it.
