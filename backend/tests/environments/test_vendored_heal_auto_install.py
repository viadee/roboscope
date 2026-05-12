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
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

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


def test_install_skips_silently_when_vendor_dir_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If the vendor dir vanished (build-artefact stripped, dev
    accidentally rm'd) we don't want venv creation to fail — log a
    warning and keep going."""
    fake_path = Path("/tmp/does/not/exist/robotframework-roboscopeheal")
    with patch(
        "src.environments.tasks._vendored_heal_path",
        return_value=fake_path,
    ), patch("src.environments.tasks.subprocess.run") as mock_run:
        with caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
            _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=99)
        # subprocess.run NEVER fires when the vendor dir is missing.
        mock_run.assert_not_called()
        assert any(
            "vendored heal lib missing" in r.message for r in caplog.records
        ), "missing-vendor warning not emitted"


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
    ) as mock_run:
        with caplog.at_level(logging.INFO, logger="roboscope.environments.tasks"):
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
    ):
        with caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
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
    ):
        with caplog.at_level(logging.WARNING, logger="roboscope.environments.tasks"):
            _install_vendored_heal_into_venv("/tmp/fake-venv", env_id=12)
    assert any(
        "vendored heal install raised" in r.message
        for r in caplog.records
    )
