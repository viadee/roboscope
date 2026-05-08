"""Story FLAKY-2 — QuarantineSkipListener + runner command wiring tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.execution.runners.quarantine_listener import (
    QuarantineSkipListener,
    write_quarantine_snapshot,
)
from src.execution.runners.subprocess_runner import SubprocessRunner


# ---------------------------------------------------------------------------
# Snapshot writer
# ---------------------------------------------------------------------------


class TestWriteSnapshot:
    def test_round_trip(self, tmp_path: Path) -> None:
        p = write_quarantine_snapshot(
            tmp_path,
            [{"suite_name": "Login", "test_name": "flaky", "reason": "timing"}],
        )
        assert p.is_file()
        payload = json.loads(p.read_text(encoding="utf-8"))
        assert payload == [
            {"suite_name": "Login", "test_name": "flaky", "reason": "timing"},
        ]

    def test_empty_list_still_writes_file(self, tmp_path: Path) -> None:
        p = write_quarantine_snapshot(tmp_path, [])
        assert json.loads(p.read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------------------
# Listener
# ---------------------------------------------------------------------------


class TestListener:
    def test_matching_test_name_calls_skip(self, tmp_path: Path) -> None:
        p = write_quarantine_snapshot(
            tmp_path,
            [{"suite_name": "Login", "test_name": "flaky_login", "reason": "flaky"}],
        )
        listener = QuarantineSkipListener(str(p))

        data = MagicMock(name="flaky_login")
        data.name = "flaky_login"
        result = MagicMock()

        with patch("robot.libraries.BuiltIn.BuiltIn") as BuiltIn_cls:
            instance = BuiltIn_cls.return_value
            listener.start_test(data, result)
            instance.skip.assert_called_once()
            msg = instance.skip.call_args.args[0]
            assert "[roboscope-quarantine]" in msg
            assert "flaky" in msg.lower()

    def test_non_matching_test_name_is_passthrough(self, tmp_path: Path) -> None:
        p = write_quarantine_snapshot(
            tmp_path,
            [{"suite_name": "Login", "test_name": "other_test"}],
        )
        listener = QuarantineSkipListener(str(p))

        data = MagicMock()
        data.name = "unrelated"
        result = MagicMock()

        with patch("robot.libraries.BuiltIn.BuiltIn") as BuiltIn_cls:
            instance = BuiltIn_cls.return_value
            listener.start_test(data, result)
            instance.skip.assert_not_called()

    def test_missing_quarantine_file_yields_inert_listener(self, tmp_path: Path) -> None:
        listener = QuarantineSkipListener(str(tmp_path / "does-not-exist.json"))
        data = MagicMock()
        data.name = "anything"
        result = MagicMock()
        # No crash, no skip.
        with patch("robot.libraries.BuiltIn.BuiltIn") as BuiltIn_cls:
            instance = BuiltIn_cls.return_value
            listener.start_test(data, result)
            instance.skip.assert_not_called()

    def test_malformed_json_yields_inert_listener(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        listener = QuarantineSkipListener(str(p))
        data = MagicMock()
        data.name = "x"
        with patch("robot.libraries.BuiltIn.BuiltIn") as BuiltIn_cls:
            listener.start_test(data, MagicMock())
            BuiltIn_cls.return_value.skip.assert_not_called()

    def test_builtin_unavailable_falls_back_to_result_mutation(
        self, tmp_path: Path
    ) -> None:
        p = write_quarantine_snapshot(
            tmp_path, [{"suite_name": "S", "test_name": "flaky"}],
        )
        listener = QuarantineSkipListener(str(p))
        data = MagicMock()
        data.name = "flaky"
        result = MagicMock()

        with patch(
            "robot.libraries.BuiltIn.BuiltIn",
            side_effect=RuntimeError("no RF context"),
        ):
            listener.start_test(data, result)
            assert result.status == "SKIP"
            assert "[roboscope-quarantine]" in result.message


# ---------------------------------------------------------------------------
# Command builder — no listeners → no flag, listeners → `--listener` pairs
# ---------------------------------------------------------------------------


class TestCommandBuilder:
    def test_no_listeners_arg_omits_flag(self) -> None:
        runner = SubprocessRunner()
        cmd = runner._build_command(
            repo_path="/x", target_path="tests/", output_dir="/tmp/o",
        )
        assert "--listener" not in cmd

    def test_single_listener_adds_flag(self) -> None:
        runner = SubprocessRunner()
        cmd = runner._build_command(
            repo_path="/x", target_path="tests/", output_dir="/tmp/o",
            listeners=["src.execution.runners.quarantine_listener.QuarantineSkipListener:/tmp/q.json"],
        )
        assert cmd.count("--listener") == 1
        idx = cmd.index("--listener")
        assert cmd[idx + 1].endswith("QuarantineSkipListener:/tmp/q.json")

    def test_blank_entries_filtered(self) -> None:
        runner = SubprocessRunner()
        cmd = runner._build_command(
            repo_path="/x", target_path="t/", output_dir="/tmp/o",
            listeners=["", "   ", "valid.Listener"],
        )
        # Only the valid one contributes a --listener pair.
        assert cmd.count("--listener") == 1
