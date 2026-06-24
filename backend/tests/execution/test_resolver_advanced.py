"""EXEC.3/EXEC.7: resolver emits validated advanced args + curated PreRunModifiers."""

import pytest

from src.execution.resolver import (
    AdvancedArgError,
    build_robot_argv,
    resolve_run_spec,
    robot_flag_args,
)


def test_advanced_args_emitted_before_target():
    spec = resolve_run_spec(target_path="suite.robot", advanced_args=["--randomize", "all"])
    flags = robot_flag_args(spec)
    assert flags[-3:] == ["--randomize", "all", "suite.robot"]


def test_prerun_modifier_emitted_as_flag():
    spec = resolve_run_spec(
        target_path="s.robot",
        prerun_modifiers=["pkg.Mod:arg1", "Other"],
    )
    argv = build_robot_argv(spec, python="python", output_dir="/output")
    assert "--prerunmodifier" in argv
    assert argv.count("--prerunmodifier") == 2
    i = argv.index("--prerunmodifier")
    assert argv[i + 1] == "pkg.Mod:arg1"


def test_prerun_modifier_is_separate_from_denied_advanced_args():
    # --prerunmodifier is denied in freeform args but allowed via the curated channel.
    with pytest.raises(AdvancedArgError):
        resolve_run_spec(target_path="s.robot", advanced_args=["--prerunmodifier", "x"])
    # ...while the dedicated channel is fine.
    spec = resolve_run_spec(target_path="s.robot", prerun_modifiers=["x"])
    assert spec.prerun_modifiers == ("x",)


@pytest.mark.parametrize(
    "token",
    [
        # Code-loading flags absent from the original long-only deny-list.
        "--variablefile",  # imports + RUNS a Python file
        "--argumentfile",  # reads further CLI args (incl --listener) from a file
        # RF short aliases for owned/denied long flags (case-sensitive).
        "-V",  # --variablefile
        "-A",  # --argumentfile
        "-P",  # --pythonpath
        "-d",  # --outputdir (owned)
        "-o",  # --output (owned)
        "-l",  # --log (owned)
        # Unambiguous long-option abbreviations RF would expand.
        "--listen",  # --listener
        "--prerunmod",  # --prerunmodifier
        "--variablef",  # --variablefile (past the --variable collision point)
        "--outp",  # --output / --outputdir (owned)
        # The =-joined form must be caught too.
        "--variablefile=/tmp/evil.py",
    ],
)
def test_advanced_args_reject_code_loading_vectors(token):
    # code-review 2026-06-24: the deny-list must cover short aliases,
    # --variablefile/--argumentfile, and abbreviations, not just exact longs.
    with pytest.raises(AdvancedArgError):
        resolve_run_spec(target_path="s.robot", advanced_args=[token])


@pytest.mark.parametrize(
    "token",
    [
        "--randomize",  # benign Z3 flag
        "--name",  # benign
        "--variable",  # the safe variable setter — must NOT be caught by the
        # --variablefile abbreviation check (RF resolves the exact match first)
        "-v",  # lowercase short --variable (safe), distinct from -V
    ],
)
def test_advanced_args_allow_safe_flags(token):
    # No exception — these are not owned/denied/abbreviations of controlled flags.
    spec = resolve_run_spec(target_path="s.robot", advanced_args=[token])
    assert token in spec.advanced_args


def test_parity_holds_with_advanced_config():
    spec = resolve_run_spec(
        target_path="s.robot",
        advanced_args=["--randomize", "all"],
        prerun_modifiers=["pkg.Mod"],
    )
    sub = build_robot_argv(spec, python="/venv/bin/python", output_dir="/host/out")
    dock = build_robot_argv(spec, python="python", output_dir="/output")

    def flags_only(argv):
        rest = argv[1:]
        j = rest.index("--outputdir")
        del rest[j : j + 2]
        return rest

    assert flags_only(sub) == flags_only(dock)
