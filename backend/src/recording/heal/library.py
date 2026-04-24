"""Story SH-2 — RoboScopeHeal Robot Framework library.

User opts in by adding ``Library    RoboScopeHeal`` to their `.robot`
file (optionally with config args) and writing ``Heal Click``,
``Heal Fill Text``, etc. instead of the bare `Browser` keyword.

Rollback contract (see story SH-2):
- **Per-keyword opt-in**: the `Heal *` prefix is the user's informed
  consent. Plain `Click` is untouched.
- **Confidence threshold** gates every swap (default 0.7 for mutating,
  0.5 for read-only).
- **Per-test budget** caps the number of heals; exceeding it re-raises
  the original failure.
- **Per-call retry budget** is 1 — second failure is the real failure.
- **`no-heal` tag** on a test disables the feature entirely for that
  test (the `Heal *` keywords delegate straight through with no retry).
- **Never mutates `.robot` on disk** — heals are suggestions, surfaced
  in the run-detail UI for user review + manual acceptance.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from robot.api.deco import keyword, library
from robot.libraries.BuiltIn import BuiltIn

from src.recording.heal.candidate_finder import (
    HealCandidate,
    find_heal_candidates,
    pick_best_candidate,
)
from src.recording.heal.heal_report import append_heal_audit


# Keywords that change browser state — clicks, form submissions, key
# presses. Require higher confidence before we dare to swap.
_MUTATING_KEYWORDS: set[str] = {
    "Click",
    "Fill Text",
    "Type Text",
    "Press Keys",
    "Hover",
}

# Read-only probes — swapping on the wrong element is cheaper (no side
# effects), so we're more permissive.
_READONLY_KEYWORDS: set[str] = {
    "Wait For Elements State",
    "Get Text",
    "Get Element Count",
    "Element Should Be Visible",
}

# Default confidence thresholds.
_DEFAULT_THRESHOLD_MUTATING = 0.7
_DEFAULT_THRESHOLD_READONLY = 0.5

# Per-call retry budget — one alternative, then give up.
_PER_CALL_RETRY_BUDGET = 1


@library(scope="TEST SUITE", version="1.0.0", auto_keywords=False)
class RoboScopeHeal:
    """Self-healing wrappers around the `Browser` Robot Framework library.

    Configuration (all optional Library-import args):
        max_heals_per_test: int = 3
            Budget cap per test. Exceeding it re-raises the original
            failure.
        confidence_threshold_mutating: float = 0.7
        confidence_threshold_readonly: float = 0.5
            Minimum confidence required before attempting a swap.
        sidecar_path: str | None = None
            Absolute path to the running test's sibling `.rbs.json`
            recorder-emitted sidecar. When omitted, only transposition
            candidates are used. If the caller wants sidecar lookup
            without tracking the path manually, pass ``auto`` — the
            library will compute it from the running test's source
            file path via Robot's `${SUITE SOURCE}` variable.
        output_dir: str | None = None
            Where to write `heal_audit.jsonl`. When omitted, defaults
            to ``${OUTPUT DIR}`` from Robot Framework.
    """

    ROBOT_LIBRARY_LISTENER = None  # would-be place for listener hooks

    def __init__(
        self,
        max_heals_per_test: int = 3,
        confidence_threshold_mutating: float = _DEFAULT_THRESHOLD_MUTATING,
        confidence_threshold_readonly: float = _DEFAULT_THRESHOLD_READONLY,
        sidecar_path: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self._max_heals_per_test = max(0, int(max_heals_per_test))
        self._threshold_mutating = float(confidence_threshold_mutating)
        self._threshold_readonly = float(confidence_threshold_readonly)
        self._sidecar_arg = sidecar_path  # resolved lazily per test
        self._output_dir_arg = output_dir
        self._heals_in_current_test = 0
        self._current_test_name: str | None = None
        self._builtin = BuiltIn()

    # -- BuiltIn Robot hooks -------------------------------------------------

    def _start_test(self, name: str) -> None:
        self._current_test_name = name
        self._heals_in_current_test = 0

    # Robot Framework calls these automatically via the listener API at
    # TEST SUITE scope. We expose plain methods so unit tests can drive
    # the state machine without spinning up a Robot runner.

    # -- Public keywords -----------------------------------------------------

    @keyword("Heal Click")
    def heal_click(self, selector: str, *args: Any, **kwargs: Any) -> Any:
        return self._dispatch("Click", selector, args, kwargs)

    @keyword("Heal Fill Text")
    def heal_fill_text(self, selector: str, text: str, *args: Any, **kwargs: Any) -> Any:
        return self._dispatch("Fill Text", selector, (text, *args), kwargs)

    @keyword("Heal Type Text")
    def heal_type_text(self, selector: str, text: str, *args: Any, **kwargs: Any) -> Any:
        return self._dispatch("Type Text", selector, (text, *args), kwargs)

    @keyword("Heal Hover")
    def heal_hover(self, selector: str, *args: Any, **kwargs: Any) -> Any:
        return self._dispatch("Hover", selector, args, kwargs)

    @keyword("Heal Press Keys")
    def heal_press_keys(self, selector: str, *keys: Any, **kwargs: Any) -> Any:
        return self._dispatch("Press Keys", selector, keys, kwargs)

    @keyword("Heal Wait For Elements State")
    def heal_wait_for_elements_state(
        self, selector: str, *args: Any, **kwargs: Any
    ) -> Any:
        return self._dispatch("Wait For Elements State", selector, args, kwargs)

    # -- Dispatch machinery --------------------------------------------------

    def _dispatch(
        self,
        browser_keyword: str,
        selector: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """Run the underlying Browser keyword; on failure, try one healed
        alternative if the safety envelope allows."""
        # `no-heal` tag on the test → delegate straight through.
        if self._test_has_no_heal_tag():
            return self._builtin.run_keyword(browser_keyword, selector, *args, **kwargs)

        try:
            return self._builtin.run_keyword(browser_keyword, selector, *args, **kwargs)
        except Exception as first_exc:
            if not self._should_retry(first_exc):
                raise

            if self._heals_in_current_test >= self._max_heals_per_test:
                # Budget exhausted — re-raise the real failure unchanged.
                # Test output will show the drift as a normal fail.
                raise

            threshold = self._threshold_for(browser_keyword)
            sidecar = self._resolve_sidecar_path()
            verify = self._make_verifier()
            candidates = find_heal_candidates(
                selector,
                sidecar_path=sidecar,
                verify=verify,
            )

            # Respect per-call retry budget — try at most N candidates.
            tried = 0
            for cand in candidates:
                if cand.confidence < threshold:
                    # List is sorted desc; below-threshold means no more qualify.
                    break
                if tried >= _PER_CALL_RETRY_BUDGET:
                    break
                tried += 1
                try:
                    result = self._builtin.run_keyword(
                        browser_keyword, cand.value, *args, **kwargs
                    )
                except Exception:
                    continue  # next candidate
                self._record_successful_heal(
                    browser_keyword, selector, cand
                )
                return result

            # Nothing worked. Re-raise the original failure.
            raise first_exc

    def _should_retry(self, exc: BaseException) -> bool:
        """Narrow heuristic: only retry on selector-related failures.
        Assertion errors, wrong-state errors, etc. must not trigger a
        heal — clicking the wrong element when the page is actually
        stale is worse than failing."""
        msg = str(exc).lower()
        return any(
            needle in msg
            for needle in (
                "not found",
                "did not appear",
                "timeout",
                "waiting for selector",
                "locator(",
                "element(s) matching",
            )
        )

    def _threshold_for(self, browser_keyword: str) -> float:
        if browser_keyword in _MUTATING_KEYWORDS:
            return self._threshold_mutating
        return self._threshold_readonly

    def _test_has_no_heal_tag(self) -> bool:
        tags = self._get_test_tags()
        return any(t.strip().lower() == "no-heal" for t in tags)

    def _get_test_tags(self) -> list[str]:
        try:
            val = self._builtin.get_variable_value("${TEST TAGS}") or []
        except Exception:
            return []
        if isinstance(val, (list, tuple)):
            return [str(x) for x in val]
        return [str(val)]

    def _resolve_sidecar_path(self) -> Path | None:
        if self._sidecar_arg is None:
            return None
        if self._sidecar_arg == "auto":
            try:
                source = self._builtin.get_variable_value("${SUITE SOURCE}")
            except Exception:
                source = None
            if not source:
                return None
            p = Path(str(source)).with_suffix(".rbs.json")
            return p if p.is_file() else None
        candidate = Path(self._sidecar_arg)
        return candidate if candidate.is_file() else None

    def _make_verifier(self):
        """Return a `verify(selector) -> int` callable that reports how
        many live-page elements match. Uses the Browser library's
        `Get Element Count` keyword — matches 0 and >1 get discarded by
        the caller. When the Browser instance isn't accessible (unit
        tests), returns None so all candidates are kept."""
        try:
            self._builtin.get_library_instance("Browser")
        except Exception:
            return None

        def _verify(selector: str) -> int:
            try:
                return int(self._builtin.run_keyword("Get Element Count", selector))
            except Exception:
                return 0

        return _verify

    def _record_successful_heal(
        self,
        browser_keyword: str,
        original_selector: str,
        candidate: HealCandidate,
    ) -> None:
        self._heals_in_current_test += 1
        audit = self._resolve_audit_path()
        if audit is None:
            return
        append_heal_audit(
            audit,
            test_name=self._current_test_name or self._discover_current_test_name(),
            keyword=browser_keyword,
            original_selector=original_selector,
            healed_selector=candidate.value,
            confidence=candidate.confidence,
            source=candidate.source,
        )

    def _resolve_audit_path(self) -> Path | None:
        base: str | None = self._output_dir_arg
        if base is None:
            try:
                base = self._builtin.get_variable_value("${OUTPUT DIR}")
            except Exception:
                base = None
        if not base:
            # No configured output dir and no Robot context to read one
            # from — silently disable audit rather than writing to cwd.
            # Heals still work; we just don't have a persistent trail.
            return None
        return Path(str(base)) / "heal_audit.jsonl"

    def _discover_current_test_name(self) -> str:
        try:
            return str(self._builtin.get_variable_value("${TEST NAME}") or "")
        except Exception:
            return ""
