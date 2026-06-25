"""Single source of truth for building the ``robot`` command line.

Story EXEC.1 (Epic EXEC). Both the subprocess and Docker runners build their
``robot`` invocation through :func:`build_robot_argv` here, so the argument
sequence can never drift between runners and validation happens in exactly one
place. Runners differ ONLY in the Python executable and the output directory
(host path vs. the container's ``/output``) — i.e. path mapping.

Three-zone flag taxonomy (per exec-architecture.md), scaffolded here for EXEC.3:

* **Z1 — RoboScope-owned**: output/log paths and console settings. Hard-coded in
  :func:`build_robot_argv`, NEVER taken from user input.
* **Z2 — safe-curated**: exposed later as discrete UI controls (EXEC.3).
* **Z3 — freeform**: a future advanced-args field; :func:`validate_advanced_args`
  rejects Z1-owned and code-loading flags so they can never be smuggled in.

Args are always emitted as a ``list[str]`` — never a shell string — so no value
can be interpreted by a shell (NFR2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

# Z1: RoboScope owns these — the server controls all output paths and console
# behaviour. They are emitted by build_robot_argv itself and must never be
# accepted from user-supplied advanced args.
OWNED_FLAGS: frozenset[str] = frozenset(
    {
        "--outputdir",
        "--output",
        "--log",
        "--report",
        "--xunit",
        "--debugfile",
        "--loglevel",
        "--consolecolors",
    }
)

# Code-loading / path-escaping flags. Allowing these via a freeform field would
# mean arbitrary code execution in the run environment, so they are denied even
# inside Z3. (PreRunModifiers/listeners get their own gated, curated paths in
# EXEC.2/EXEC.7 — never through generic advanced args.)
#
# --variablefile imports and RUNS a Python file; --argumentfile reads further
# CLI args (incl. --listener/--pythonpath) from a file — both are code/arg
# injection vectors and MUST be denied alongside the obvious loaders.
DENIED_FLAGS: frozenset[str] = frozenset(
    {
        "--pythonpath",
        "--listener",
        "--prerunmodifier",
        "--prerebotmodifier",
        "--parser",
        "--variablefile",
        "--argumentfile",
    }
)

# RF accepts short aliases for the controlled long flags. These are
# CASE-SENSITIVE: -v (--variable) is the safe variable setter we emit ourselves,
# while -V (--variablefile) loads code. An exact-long-flag check alone would let
# every short form straight through, so they are enumerated here.
OWNED_SHORT: frozenset[str] = frozenset(
    {"-d", "-o", "-l", "-r", "-x", "-b", "-L", "-C"}
)
DENIED_SHORT: frozenset[str] = frozenset({"-P", "-V", "-A"})

# Union of the controlled long flags, used for RF's unambiguous-prefix
# abbreviation expansion (e.g. `--listen` → `--listener`).
_CONTROLLED_LONG: frozenset[str] = OWNED_FLAGS | DENIED_FLAGS

# Safe full flags that happen to be a strict prefix of a controlled flag
# (`--variable` vs `--variablefile`). RF resolves the exact match first, so
# these must NOT be rejected by the abbreviation check below.
_SAFE_PREFIX_FLAGS: frozenset[str] = frozenset({"--variable"})


def _abbreviates_controlled(flag: str) -> bool:
    """True if ``flag`` is an unambiguous long-option abbreviation of a
    controlled flag (RF expands a unique prefix). Over-rejects ambiguous
    prefixes too — those wouldn't run anyway, so denying them is strictly safe.
    """
    if not (flag.startswith("--") and len(flag) > 2):
        return False
    if flag in _SAFE_PREFIX_FLAGS:
        return False
    return any(full.startswith(flag) for full in _CONTROLLED_LONG)


class AdvancedArgError(ValueError):
    """A requested ``robot`` arg violates the three-zone policy.

    Resolved BEFORE either runner is reached, so a denied spec is rejected
    identically regardless of runner (subprocess or Docker).
    """


@dataclass(frozen=True)
class ResolvedRunSpec:
    """Immutable, validated description of a ``robot`` invocation.

    Produced by :func:`resolve_run_spec` at the service layer; runners consume
    this (via :func:`build_robot_argv`) rather than raw request fields, which is
    what prevents argument-construction drift between runners.
    """

    target_path: str
    runner_type: str = "subprocess"
    tags_include: tuple[str, ...] = ()
    tags_exclude: tuple[str, ...] = ()
    variables: tuple[tuple[str, str], ...] = ()
    listeners: tuple[str, ...] = ()
    # EXEC.3/EXEC.7: validated freeform args (Z3) + curated PreRunModifier specs
    # ("name" or "name:arg1:arg2"). Modifiers are a separate, gated channel —
    # never reachable through advanced_args (which denies --prerunmodifier).
    advanced_args: tuple[str, ...] = ()
    prerun_modifiers: tuple[str, ...] = ()
    # EXEC.10: further typed channels that bypass the Z3 deny-list (which denies
    # all of these raw flags) but are NEVER read from the freeform field.
    # prerebot_modifiers run against the RESULT model after execution (the
    # "update reports / TMS" hook). python_paths / variable_files are
    # repo-confined at resolve time.
    prerebot_modifiers: tuple[str, ...] = ()
    python_paths: tuple[str, ...] = ()
    variable_files: tuple[str, ...] = ()
    audit_payload: dict = field(default_factory=dict)


def _split_tags(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalise a comma-separated tag string (or iterable) to a clean tuple."""
    if not value:
        return ()
    parts = value.split(",") if isinstance(value, str) else list(value)
    return tuple(t.strip() for t in parts if t and t.strip())


def _confine_to_repo(raw: str, repo_root: str | None) -> str:
    """Resolve a user-supplied file/dir path against the repo root and ensure it
    stays inside it (EXEC.10 ``--pythonpath`` / ``--variablefile`` levers).

    Returns the resolved absolute path. Raises :class:`AdvancedArgError` when the
    path escapes the repo tree OR no repo context is available (fail closed). An
    absolute ``raw`` inside the repo is accepted; one outside is rejected.
    """
    if not repo_root:
        raise AdvancedArgError(
            "a repository context is required to use file-based execution levers"
        )
    from pathlib import Path

    root = Path(repo_root).resolve()
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise AdvancedArgError(
            f"path '{raw}' escapes the repository tree and is not allowed"
        ) from None
    return str(target)


def validate_advanced_args(args: Iterable[str] | None) -> tuple[str, ...]:
    """Validate freeform (Z3) ``robot`` args against the three-zone policy.

    Raises :class:`AdvancedArgError` if any token is a Z1-owned flag or a
    code-loading/path flag — including RF short aliases (``-V`` etc.) and
    unambiguous long-option abbreviations (``--listen`` → ``--listener``).
    Returns the validated tuple unchanged otherwise. EXEC.1 wires no UI for this
    yet (callers pass nothing); it exists so the rejection contract is testable
    and ready for EXEC.3.
    """
    if not args:
        return ()
    validated = tuple(args)
    for token in validated:
        flag = token.split("=", 1)[0].strip()
        if flag in OWNED_FLAGS or flag in OWNED_SHORT:
            raise AdvancedArgError(
                f"{flag} is controlled by RoboScope and cannot be set via advanced args"
            )
        if flag in DENIED_FLAGS or flag in DENIED_SHORT:
            raise AdvancedArgError(
                f"{flag} loads code or escapes paths and is not allowed in advanced args"
            )
        if _abbreviates_controlled(flag):
            raise AdvancedArgError(
                f"{flag} abbreviates a flag controlled by RoboScope and is not allowed "
                "in advanced args"
            )
    return validated


def resolve_run_spec(
    *,
    target_path: str,
    runner_type: str = "subprocess",
    tags_include: str | Iterable[str] | None = None,
    tags_exclude: str | Iterable[str] | None = None,
    variables: Mapping[str, object] | None = None,
    listeners: Iterable[str] | None = None,
    advanced_args: Iterable[str] | None = None,
    prerun_modifiers: Iterable[str] | None = None,
    prerebot_modifiers: Iterable[str] | None = None,
    python_paths: Iterable[str] | None = None,
    variable_files: Iterable[str] | None = None,
    repo_root: str | None = None,
) -> ResolvedRunSpec:
    """Validate and normalise run inputs into an immutable :class:`ResolvedRunSpec`.

    This is the single place validation happens; both runners build their argv
    from the returned spec. ``advanced_args`` is validated against the three-zone
    policy (rejection is runner-independent). ``prerun_modifiers`` /
    ``prerebot_modifiers`` are the curated, separately-gated modifier channels
    (EXEC.7/EXEC.10), emitted as ``--prerunmodifier`` / ``--prerebotmodifier``.
    ``python_paths`` / ``variable_files`` are repo-confined here against
    ``repo_root`` (EXEC.10) — a path escaping the tree raises ``AdvancedArgError``.
    """
    validated_args = validate_advanced_args(advanced_args)

    inc = _split_tags(tags_include)
    exc = _split_tags(tags_exclude)
    vars_t: tuple[tuple[str, str], ...] = (
        tuple((str(k), str(v)) for k, v in variables.items()) if variables else ()
    )
    listeners_t = tuple(s.strip() for s in (listeners or []) if s and s.strip())
    modifiers_t = tuple(s.strip() for s in (prerun_modifiers or []) if s and s.strip())
    prerebot_t = tuple(s.strip() for s in (prerebot_modifiers or []) if s and s.strip())
    pythonpaths_t = tuple(
        _confine_to_repo(str(p).strip(), repo_root)
        for p in (python_paths or [])
        if p and str(p).strip()
    )
    varfiles_t = tuple(
        _confine_to_repo(str(p).strip(), repo_root)
        for p in (variable_files or [])
        if p and str(p).strip()
    )

    spec = ResolvedRunSpec(
        target_path=target_path,
        runner_type=runner_type,
        tags_include=inc,
        tags_exclude=exc,
        variables=vars_t,
        listeners=listeners_t,
        advanced_args=validated_args,
        prerun_modifiers=modifiers_t,
        prerebot_modifiers=prerebot_t,
        python_paths=pythonpaths_t,
        variable_files=varfiles_t,
    )
    # Runner-independent flag portion — used for parity assertions and for the
    # audit trail (EXEC.3 will persist this on the AuditLog).
    object.__setattr__(spec, "audit_payload", {"robot_flags": list(robot_flag_args(spec))})
    return spec


def robot_flag_args(spec: ResolvedRunSpec) -> list[str]:
    """The runner-INDEPENDENT portion of the robot command line.

    Identical across runners for a given spec — this is what the parity test
    asserts. Excludes the Python executable and the Z1 output/console prefix
    (those are runner/path specific).
    """
    flags: list[str] = []
    for tag in spec.tags_include:
        flags += ["--include", tag]
    for tag in spec.tags_exclude:
        flags += ["--exclude", tag]
    for path in spec.python_paths:
        flags += ["--pythonpath", path]
    for spec_str in spec.listeners:
        flags += ["--listener", spec_str]
    for modifier in spec.prerun_modifiers:
        flags += ["--prerunmodifier", modifier]
    for modifier in spec.prerebot_modifiers:
        flags += ["--prerebotmodifier", modifier]
    for var_file in spec.variable_files:
        flags += ["--variablefile", var_file]
    for key, value in spec.variables:
        flags += ["--variable", f"{key}:{value}"]
    # Validated freeform args (Z3) — emitted verbatim before the target path.
    flags += list(spec.advanced_args)
    flags.append(spec.target_path)
    return flags


def build_robot_argv(spec: ResolvedRunSpec, *, python: str, output_dir: str) -> list[str]:
    """Build the full ``robot`` argv for a spec — the single shared arg-builder.

    Z1-owned flags (``--outputdir``/``--loglevel``/``--consolecolors``) are
    emitted here and never sourced from user input. ``python`` and
    ``output_dir`` are the only runner-specific inputs (path mapping).
    """
    return [
        python,
        "-m",
        "robot",
        "--outputdir",
        output_dir,
        "--loglevel",
        "INFO",
        "--consolecolors",
        "off",
        *robot_flag_args(spec),
    ]
