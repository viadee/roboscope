"""Runner-parity contract (Story EXEC.1, mandated by exec-architecture.md).

For a given ResolvedRunSpec, the subprocess and Docker runners must build an
identical ``robot`` argument sequence modulo path mapping (the Python
executable and the output directory), and a denied spec must be rejected
identically regardless of runner.
"""

import pytest

from src.execution.resolver import (
    AdvancedArgError,
    build_robot_argv,
    resolve_run_spec,
    robot_flag_args,
)


def _spec():
    return resolve_run_spec(
        target_path="suite.robot",
        runner_type="subprocess",
        tags_include="smoke, wip",
        tags_exclude="slow",
        variables={"BROWSER": "chromium", "URL": "http://app"},
        listeners=["pkg.mod.Listener:arg1"],
    )


def _flags_only(argv: list[str]) -> list[str]:
    """Strip the runner/path-specific bits: argv[0] (python) and --outputdir <val>."""
    rest = argv[1:]  # drop python executable
    i = rest.index("--outputdir")
    del rest[i : i + 2]  # drop --outputdir and its value
    return rest


def test_runners_build_identical_argv_modulo_path_mapping():
    spec = _spec()
    subprocess_argv = build_robot_argv(spec, python="/venv/bin/python", output_dir="/host/out")
    docker_argv = build_robot_argv(spec, python="python", output_dir="/output")

    # Identical everything except the python exe and the outputdir value.
    assert _flags_only(subprocess_argv) == _flags_only(docker_argv)
    # And that shared remainder ends with the runner-independent flag portion.
    flags = _flags_only(subprocess_argv)
    assert flags[-len(robot_flag_args(spec)) :] == robot_flag_args(spec)


def test_listener_parity_both_runners_emit_listener():
    spec = _spec()
    subprocess_argv = build_robot_argv(spec, python="/venv/bin/python", output_dir="/host/out")
    docker_argv = build_robot_argv(spec, python="python", output_dir="/output")
    assert "--listener" in subprocess_argv
    assert "--listener" in docker_argv
    assert subprocess_argv.count("--listener") == docker_argv.count("--listener") == 1


def test_owned_output_flags_are_server_controlled():
    spec = _spec()
    argv = build_robot_argv(spec, python="python", output_dir="/output")
    # RoboScope owns the output dir; it is present and set by the builder.
    assert argv[argv.index("--outputdir") + 1] == "/output"
    # The target path is always last.
    assert argv[-1] == "suite.robot"


@pytest.mark.parametrize("runner_type", ["subprocess", "docker"])
def test_denied_advanced_arg_rejected_identically(runner_type):
    # A code-loading flag is rejected at resolve time, before any runner runs —
    # identical behaviour regardless of runner_type.
    with pytest.raises(AdvancedArgError):
        resolve_run_spec(
            target_path="s.robot",
            runner_type=runner_type,
            advanced_args=["--listener", "evil.Mod"],
        )


@pytest.mark.parametrize("runner_type", ["subprocess", "docker"])
def test_owned_flag_rejected_in_advanced_args(runner_type):
    with pytest.raises(AdvancedArgError):
        resolve_run_spec(
            target_path="s.robot",
            runner_type=runner_type,
            advanced_args=["--outputdir", "/tmp/escape"],
        )


def test_no_regression_tags_and_variables_order():
    spec = _spec()
    flags = robot_flag_args(spec)
    # Tags split + stripped; variables rendered KEY:VALUE; target last.
    assert "--include" in flags and "smoke" in flags and "wip" in flags
    assert flags[flags.index("--exclude") + 1] == "slow"
    assert "--variable" in flags and "BROWSER:chromium" in flags and "URL:http://app" in flags
    assert flags[-1] == "suite.robot"
