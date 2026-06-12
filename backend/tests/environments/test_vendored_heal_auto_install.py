"""Story HEAL-VENDORED phase-2 — auto-install the vendored heal
library into every freshly-created project venv.

Pins:
  - `_vendored_heal_path()` resolves to the real on-disk vendor
    tree (catches accidental refactoring of the directory layout).
  - `_install_vendored_heal_into_venv()`:
      * passes the vendor path verbatim to `pip_install_cmd`,
      * silently returns when the vendor directory is missing
        (the warning is logged but the venv creation continues),
      * logs at WARNING (non-fatal) when pip exits non-zero,
      * logs at INFO when the install succeeds.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.environments.tasks import (
    _install_vendored_heal_into_venv,
    _vendored_heal_path,
)


def test_vendored_heal_path_points_at_real_vendor_tree() -> None:
    p = _vendored_heal_path()
    assert p.is_absolute()
    # Same shape the rest of the vendor tooling assumes.
    assert p.name == "robotframework-roboscopeheal"
    assert p.parent.name == "vendor"
    # And it actually exists on disk in this checkout.
    assert (p / "pyproject.toml").is_file(), (
        f"vendored heal pyproject missing at {p}/pyproject.toml — "
        f"either the vendor tree was deleted or the path-resolution "
        f"helper broke."
    )


def test_install_skips_silently_when_no_source_or_wheel(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If neither the vendor source tree NOR a bundled wheel can be
    found (build-artefact stripped both, dev accidentally rm'd) we don't
    want venv creation to fail — log a warning and keep going."""
    with patch(
        "src.environments.tasks._shipped_install_target",
        return_value=None,
    ), patch("src.environments.tasks.subprocess.run") as mock_run:
        with caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
            _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=99)
        # subprocess.run NEVER fires when there's nothing to install from.
        mock_run.assert_not_called()
        assert any(
            "no vendored heal source or bundled wheel" in r.message
            for r in caplog.records
        ), "missing-source-and-wheel warning not emitted"


def test_install_passes_vendor_path_to_pip(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Happy path — vendor exists, pip_install_cmd is built with the
    vendor path as a positional package arg, subprocess returns 0,
    INFO log fires."""
    real_vendor = _vendored_heal_path()
    assert real_vendor.is_dir()  # if this fails the test fixture is broken
    fake_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch(
        "src.environments.tasks.subprocess.run", return_value=fake_result,
    ) as mock_run, caplog.at_level(logging.INFO, logger="roboscope.environments.tasks"):
        _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=42)
    # The vendor path string ends up in argv somewhere — that's the
    # actual contract we care about (uv pip install accepts a path as
    # a positional package spec, same as a package name).
    invoked_argv = mock_run.call_args[0][0]
    assert str(real_vendor) in invoked_argv, (
        f"vendor path not in pip argv: {invoked_argv!r}"
    )
    assert any(
        "seeded robotframework-roboscopeheal" in r.getMessage()
        for r in caplog.records
    ), f"INFO log not emitted; records seen: {[r.getMessage() for r in caplog.records]!r}"


def test_install_failure_is_logged_warning_not_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pip exits non-zero (network blip, wheel-build error, missing
    build deps on the host …) — the helper logs and returns rather
    than tearing the venv-creation transaction down. The user can
    install heal manually later from the package-management UI."""
    fake_result = MagicMock(
        returncode=1, stdout="", stderr="ERROR: build wheel failed",
    )
    with patch(
        "src.environments.tasks.subprocess.run", return_value=fake_result,
    ), caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
        _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=7)
    assert any(
        "vendored heal install failed" in r.message
        and "rc=1" in r.message
        for r in caplog.records
    )


def test_install_subprocess_raise_is_caught(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Even an unexpected exception (e.g. uv binary missing on
    PATH) keeps venv creation viable — log + return."""
    with patch(
        "src.environments.tasks.subprocess.run",
        side_effect=FileNotFoundError("uv: not found"),
    ), caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
        _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=12)
    assert any(
        "vendored heal install raised" in r.message
        for r in caplog.records
    )


# --- Shipped-vendor registry (`_shipped_vendor_path`) ---
#
# Pins the contract used by `install_package` when a user clicks
# "install" on a `shipped_with_roboscope: True` entry in the UI:
#   - known shipped name + vendor dir present → returns the path
#   - unknown name → returns None (caller proceeds to PyPI)
#   - known name + vendor dir missing on disk → returns None + WARN
#   - case-insensitive lookup (PyPI distribution names are
#     case-insensitive; pip accepts any case)

from src.environments.tasks import _shipped_vendor_path  # noqa: E402


def test_shipped_vendor_path_resolves_known_package() -> None:
    p = _shipped_vendor_path("robotframework-roboscopeheal")
    assert p is not None
    assert p.is_absolute()
    assert p.name == "robotframework-roboscopeheal"
    assert (p / "pyproject.toml").is_file()


def test_shipped_vendor_path_is_case_insensitive() -> None:
    """pip normalises distribution names — the registry lookup
    must match regardless of how the UI sent the name."""
    mixed = _shipped_vendor_path("RobotFramework-RoboscopeHeal")
    upper = _shipped_vendor_path("ROBOTFRAMEWORK-ROBOSCOPEHEAL")
    assert mixed is not None
    assert upper is not None
    assert mixed == upper


def test_shipped_vendor_path_unknown_package_returns_none() -> None:
    """Non-shipped packages (the vast majority of PyPI) fall
    through to the normal `pip install <name>` PyPI path."""
    assert _shipped_vendor_path("robotframework-requests") is None
    assert _shipped_vendor_path("robotframework-browser") is None
    assert _shipped_vendor_path("definitely-not-a-real-package") is None


def test_shipped_vendor_path_logs_when_dir_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If a package IS registered as shipped but the vendor
    directory got stripped (build artefact, dev cleanup, …),
    return None + WARN — the caller falls back to PyPI cleanly
    instead of trying to install from a path that doesn't exist."""
    with patch.dict(
        "src.environments.tasks._SHIPPED_VENDOR_PACKAGES",
        {"some-broken-shipped-pkg": "does-not-exist-on-disk"},
    ), caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
        result = _shipped_vendor_path("some-broken-shipped-pkg")
    assert result is None
    assert any(
        "vendor dir missing" in r.message
        for r in caplog.records
    )


# --- Bundled-wheel fallback (`_shipped_install_target`) ---
#
# In a deployed distribution the vendored SOURCE tree is NOT copied, but
# the pre-built heal WHEEL ships in `wheels/`. The resolver must fall back
# to that wheel so the auto-seed (and the UI install) actually work off a
# release ZIP — otherwise they silently hit a PyPI 404 for the unpublished
# `robotframework-roboscopeheal`.

from src.environments.tasks import (  # noqa: E402
    _bundled_wheel_for,
    _shipped_install_target,
)


def test_shipped_install_target_prefers_source_in_dev() -> None:
    """Dev checkout: the vendor source tree exists, so that wins."""
    target = _shipped_install_target("robotframework-roboscopeheal")
    assert target is not None
    assert target.endswith("robotframework-roboscopeheal")
    assert Path(target).is_dir()


def test_shipped_install_target_falls_back_to_bundled_wheel(tmp_path) -> None:
    """No source tree (stripped dist) → resolve the bundled wheel."""
    wheel = tmp_path / "robotframework_roboscopeheal-0.2.2-py3-none-any.whl"
    wheel.write_text("fake wheel")
    with patch(
        "src.environments.tasks._shipped_vendor_path", return_value=None
    ), patch("src.environments.tasks._dist_wheels_dir", return_value=tmp_path):
        target = _shipped_install_target("robotframework-roboscopeheal")
    assert target == str(wheel)


def test_shipped_install_target_none_when_nothing_available(tmp_path) -> None:
    with patch(
        "src.environments.tasks._shipped_vendor_path", return_value=None
    ), patch("src.environments.tasks._dist_wheels_dir", return_value=None):
        assert _shipped_install_target("robotframework-roboscopeheal") is None


def test_bundled_wheel_for_matches_normalised_name(tmp_path) -> None:
    (tmp_path / "robotframework_roboscopeheal-0.2.2-py3-none-any.whl").write_text("w")
    (tmp_path / "robotframework_roboscopeheal-0.3.0-py3-none-any.whl").write_text("w")
    (tmp_path / "some_other_pkg-1.0-py3-none-any.whl").write_text("w")
    with patch("src.environments.tasks._dist_wheels_dir", return_value=tmp_path):
        found = _bundled_wheel_for("robotframework-roboscopeheal")
    assert found is not None
    # Highest version wins (lexicographic sort → 0.3.0 after 0.2.2).
    assert found.name == "robotframework_roboscopeheal-0.3.0-py3-none-any.whl"


def test_install_uses_bundled_wheel_with_find_links(tmp_path) -> None:
    """Deployed-dist path: install from the bundled wheel, and pass
    `--find-links wheels/` so heal's deps resolve from the bundle offline."""
    wheel = tmp_path / "robotframework_roboscopeheal-0.2.2-py3-none-any.whl"
    wheel.write_text("fake wheel")
    fake_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch(
        "src.environments.tasks._shipped_vendor_path", return_value=None
    ), patch(
        "src.environments.tasks._dist_wheels_dir", return_value=tmp_path
    ), patch(
        "src.environments.tasks.subprocess.run", return_value=fake_result
    ) as mock_run:
        _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=5)
    argv = mock_run.call_args[0][0]
    assert str(wheel) in argv
    assert "--find-links" in argv
    assert str(tmp_path) in argv
