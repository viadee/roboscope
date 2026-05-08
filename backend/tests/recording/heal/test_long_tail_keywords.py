"""Story SH-5 — long-tail heal keyword tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.recording.heal.library import RoboScopeHeal


def _make_lib(**overrides) -> RoboScopeHeal:
    lib = RoboScopeHeal(**overrides)
    lib._builtin = MagicMock()
    lib._builtin.get_variable_value.return_value = []
    lib._builtin.get_library_instance.side_effect = Exception("no Browser")
    return lib


class TestReadOnlyKeywords:
    def test_heal_get_text_passes_args_through(self) -> None:
        lib = _make_lib()
        lib._builtin.run_keyword.return_value = "value"
        assert lib.heal_get_text("id=field") == "value"
        lib._builtin.run_keyword.assert_called_once_with("Get Text", "id=field")

    def test_heal_get_element_count_uses_readonly_threshold(
        self, tmp_path: Path
    ) -> None:
        # Prove the readonly threshold applies to Get Element Count.
        # Any id→testid transposition scores ~0.95, well above 0.5 (the
        # readonly default) but we set a strict 0.99 mutating threshold
        # to show the readonly path is the one that qualifies. If the
        # library mistakenly used the mutating threshold, the heal
        # wouldn't run.
        lib = _make_lib(
            output_dir=str(tmp_path),
            confidence_threshold_readonly=0.5,
            confidence_threshold_mutating=0.99,
        )
        lib._builtin.run_keyword.side_effect = [
            Exception("Element 'id=submit' not found"),
            3,
        ]
        result = lib.heal_get_element_count("id=submit")
        assert result == 3
        assert lib._builtin.run_keyword.call_count == 2


class TestMutatingKeywords:
    def test_heal_upload_file_path_passes_through(self) -> None:
        lib = _make_lib()
        lib._builtin.run_keyword.return_value = None
        lib.heal_upload_file("css=input[type=file]", "/tmp/x.txt")
        lib._builtin.run_keyword.assert_called_once_with(
            "Upload File", "css=input[type=file]", "/tmp/x.txt",
        )

    def test_heal_check_checkbox_calls_underlying(self) -> None:
        lib = _make_lib()
        lib.heal_check_checkbox("id=accept")
        lib._builtin.run_keyword.assert_called_once_with("Check Checkbox", "id=accept")

    def test_heal_uncheck_checkbox_calls_underlying(self) -> None:
        lib = _make_lib()
        lib.heal_uncheck_checkbox("id=accept")
        lib._builtin.run_keyword.assert_called_once_with("Uncheck Checkbox", "id=accept")

    def test_heal_select_options_by_forwards_attribute_and_values(self) -> None:
        lib = _make_lib()
        lib.heal_select_options_by("id=country", "value", "DE", "FR")
        lib._builtin.run_keyword.assert_called_once_with(
            "Select Options By", "id=country", "value", "DE", "FR",
        )


class TestDragAndDropHealing:
    def test_no_failure_passes_through_with_both_selectors(self) -> None:
        lib = _make_lib()
        lib._builtin.run_keyword.return_value = None
        lib.heal_drag_and_drop("id=src", "id=dst")
        lib._builtin.run_keyword.assert_called_once_with(
            "Drag And Drop", "id=src", "id=dst",
        )

    def test_source_missing_gets_healed_target_unchanged(
        self, tmp_path: Path
    ) -> None:
        lib = _make_lib(
            output_dir=str(tmp_path),
            confidence_threshold_mutating=0.5,
        )

        # Browser probe mock: "id=src" → 0 elements (missing),
        # "id=dst" → 1 (fine), all healed candidates → 1.
        browser_lib = MagicMock()
        lib._builtin.get_library_instance.side_effect = None
        lib._builtin.get_library_instance.return_value = browser_lib

        probe_counts = {"id=src": 0, "id=dst": 1}
        dispatch_seq = iter([
            Exception("Element 'id=src' not found"),  # original DnD call
            None,                                     # retry succeeds
        ])

        def _run_keyword(name, *args, **kwargs):
            if name == "Get Element Count":
                sel = args[0]
                return probe_counts.get(sel, 1)
            # Drag And Drop call (twice — first fails, second succeeds)
            res = next(dispatch_seq)
            if isinstance(res, Exception):
                raise res
            return res

        lib._builtin.run_keyword.side_effect = _run_keyword

        lib.heal_drag_and_drop("id=src", "id=dst")
        # The second DnD call used a healed source but the original target.
        second_call = lib._builtin.run_keyword.call_args_list[-1]
        assert second_call.args[0] == "Drag And Drop"
        assert second_call.args[1] != "id=src"      # healed
        assert second_call.args[2] == "id=dst"      # unchanged
        # Budget burned once for the one healed selector.
        assert lib._heals_in_current_test == 1

    def test_neither_missing_reraises_original_exception(
        self, tmp_path: Path
    ) -> None:
        lib = _make_lib(
            output_dir=str(tmp_path),
            confidence_threshold_mutating=0.5,
        )
        browser_lib = MagicMock()
        lib._builtin.get_library_instance.side_effect = None
        lib._builtin.get_library_instance.return_value = browser_lib

        def _run_keyword(name, *args, **kwargs):
            if name == "Get Element Count":
                return 1  # both selectors resolve fine
            # DnD call fails anyway — something non-selector is wrong.
            raise Exception("element blocked by overlay")

        lib._builtin.run_keyword.side_effect = _run_keyword

        with pytest.raises(Exception, match="overlay"):
            lib.heal_drag_and_drop("id=src", "id=dst")

    def test_no_heal_tag_bypasses_drag_and_drop(self) -> None:
        lib = _make_lib()
        lib._builtin.get_variable_value.return_value = ["no-heal"]
        lib._builtin.run_keyword.side_effect = Exception(
            "Element 'id=src' not found"
        )
        with pytest.raises(Exception, match="not found"):
            lib.heal_drag_and_drop("id=src", "id=dst")
        # Only the original call — no probing, no healing.
        assert lib._builtin.run_keyword.call_count == 1


class TestKeywordClassification:
    def test_upload_file_is_mutating(self) -> None:
        lib = _make_lib()
        assert lib._threshold_for("Upload File") == lib._threshold_mutating

    def test_get_text_is_readonly(self) -> None:
        lib = _make_lib()
        assert lib._threshold_for("Get Text") == lib._threshold_readonly

    def test_drag_and_drop_is_mutating(self) -> None:
        lib = _make_lib()
        assert lib._threshold_for("Drag And Drop") == lib._threshold_mutating
