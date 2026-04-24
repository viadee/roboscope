"""Regression: every concrete runner must accept every parameter that
`AbstractRunner.execute` declares — including kwargs added after the
original interface was frozen.

Why this exists: Story FLAKY-2 extended `AbstractRunner.execute` with
a new `listeners` kwarg. `SubprocessRunner` was updated in the same
commit, `DockerRunner` was not. Because `AbstractRunner` is an ABC and
Python's ABC only enforces method *presence* (not signature shape),
the `DockerRunner` omission slipped through both lint and the test
suite — the first `execute_test_run` on a Docker-backed environment
crashed with `TypeError: DockerRunner.execute() got an unexpected
keyword argument 'listeners'`.

This test closes that hole at the introspection level: it walks every
concrete subclass of `AbstractRunner` it can find in the runners
package and asserts the `execute` signature covers the full abstract
parameter set. Adding a kwarg to the abstract without mirroring it on
every concrete fails CI now, not in production.
"""

from __future__ import annotations

import inspect

import pytest

from src.execution.runners import base, subprocess_runner
from src.execution.runners.base import AbstractRunner


# Concrete runner classes to vet. Keep explicit — an automatic walk of
# subclasses() is flaky because it depends on import order. A module
# that adds a new runner and forgets to register it here is itself a
# review-surface signal.
#
# `DockerRunner` is imported only if its optional `docker` dep is
# present; guarded so the parity test still runs in docker-less
# environments.
_CONCRETE_RUNNERS: list[type[AbstractRunner]] = [
    subprocess_runner.SubprocessRunner,
]
try:
    from src.execution.runners.docker_runner import DockerRunner
    _CONCRETE_RUNNERS.append(DockerRunner)
except Exception:  # pragma: no cover - docker dep missing
    pass


def _param_names(cls: type, method_name: str) -> set[str]:
    """All parameter names (positional + keyword-only) of the method,
    minus `self`."""
    sig = inspect.signature(getattr(cls, method_name))
    return {name for name in sig.parameters if name != "self"}


@pytest.mark.parametrize("runner_cls", _CONCRETE_RUNNERS,
                         ids=[c.__name__ for c in _CONCRETE_RUNNERS])
def test_execute_signature_matches_abstract(runner_cls: type[AbstractRunner]) -> None:
    abstract_params = _param_names(AbstractRunner, "execute")
    concrete_params = _param_names(runner_cls, "execute")

    missing = abstract_params - concrete_params
    assert not missing, (
        f"{runner_cls.__name__}.execute is missing parameters declared on "
        f"AbstractRunner.execute: {sorted(missing)}. "
        f"When extending the abstract interface, every concrete runner "
        f"must be updated at the same time."
    )


@pytest.mark.parametrize("runner_cls", _CONCRETE_RUNNERS,
                         ids=[c.__name__ for c in _CONCRETE_RUNNERS])
def test_prepare_signature_matches_abstract(runner_cls: type[AbstractRunner]) -> None:
    abstract_params = _param_names(AbstractRunner, "prepare")
    concrete_params = _param_names(runner_cls, "prepare")
    missing = abstract_params - concrete_params
    assert not missing, (
        f"{runner_cls.__name__}.prepare is missing parameters declared on "
        f"AbstractRunner.prepare: {sorted(missing)}."
    )


def test_abstract_runner_has_listeners_param() -> None:
    """Story FLAKY-2 specifically: make sure the `listeners` kwarg
    stays on the abstract contract. A future cleanup that drops it
    from AbstractRunner but leaves it on SubprocessRunner would let
    callers pass it to one runner and not another — silent divergence."""
    assert "listeners" in _param_names(AbstractRunner, "execute"), (
        "AbstractRunner.execute must advertise the listeners kwarg "
        "(Story FLAKY-2). Do not remove without a deprecation story."
    )


# Sanity — any future runner class forgotten by this list is still
# covered by runtime failure when someone dispatches through it, but
# it's useful for CI to surface the omission proactively.
def test_all_concrete_subclasses_are_checked() -> None:
    """Walk AbstractRunner.__subclasses__() transitively and assert
    each known concrete class is in the `_CONCRETE_RUNNERS` list."""
    # Import the runners package so all concrete runners are loaded.
    import importlib
    import pkgutil
    import src.execution.runners as runners_pkg

    for _, name, _ in pkgutil.iter_modules(runners_pkg.__path__):
        try:
            importlib.import_module(f"{runners_pkg.__name__}.{name}")
        except Exception:
            continue

    registered = {cls.__name__ for cls in _CONCRETE_RUNNERS}
    discovered: set[str] = set()

    def _walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            if inspect.isabstract(sub):
                _walk(sub)
                continue
            discovered.add(sub.__name__)
            _walk(sub)

    _walk(AbstractRunner)
    orphaned = discovered - registered
    # Docker may or may not be present depending on optional deps; we
    # don't count it as orphaned if it's simply not importable.
    orphaned -= {"DockerRunner"} - registered
    assert not orphaned, (
        f"New concrete runners found that aren't checked by this file: "
        f"{sorted(orphaned)}. Add them to `_CONCRETE_RUNNERS` in "
        f"test_runner_interface_parity.py."
    )
