"""Long-term guardrail for the Playwright version-pairing chain.

The 2026-04-24 incident chain had three distinct failures:

  1. Hardcoded Docker tag drifted behind installed playwright.
     Fixed by `playwright_docker_base_image()` deriving the tag.

  2. Transitive pip upgrade overrode the base image's Playwright
     inside the container. Fixed by a force-pin
     `playwright==<ver>` after the user-package install.

  3. (The one THIS file guards.) Robot packages — `robotframework-
     browser`, `robotframework-browser-batteries` — advertise their
     own `playwright` version constraint. If the backend's installed
     Playwright falls OUTSIDE that range, a rebuild either installs
     two Playwrights or fails at dependency resolution. The failure
     mode is structural: no amount of in-container pinning fixes an
     out-of-range constraint.

This file ships the continuous guardrail: unit tests for the
constraint-extraction logic (offline, stubbed) plus an integration
test that actually hits PyPI and asserts the current backend
Playwright satisfies the current robotframework-browser{,-batteries}
constraint. The integration test is what CI schedules regularly —
when it fails, the pin is about to drift and `uv lock --upgrade-package
playwright` is the fix.
"""

from __future__ import annotations

import json
from importlib.metadata import version as _installed_version

import pytest

from src.environments.service import (
    playwright_constraints_for_browser_package,
    playwright_pinned_version,
    validate_playwright_pin_against_packages,
)


# ---------------------------------------------------------------------------
# Unit tests — offline, stub the PyPI fetcher.
# ---------------------------------------------------------------------------


def _stub_pypi(name: str, requires: list[str]):
    """Return a `pypi_json_fetcher` callable that always returns a
    minimal JSON envelope mimicking PyPI's `/pypi/<pkg>/json`."""
    payload = json.dumps({"info": {"requires_dist": requires}}).encode()

    def _fetch(url: str) -> bytes:
        assert name in url, f"unexpected fetch URL: {url}"
        return payload

    return _fetch


class TestConstraintExtraction:
    def test_extracts_simple_upper_bound(self) -> None:
        spec = playwright_constraints_for_browser_package(
            "robotframework-browser",
            pypi_json_fetcher=_stub_pypi(
                "robotframework-browser",
                ["playwright>=1.55,<1.60", "other-dep>=0.1"],
            ),
        )
        assert spec == ">=1.55,<1.60"

    def test_extracts_paren_wrapped_spec(self) -> None:
        spec = playwright_constraints_for_browser_package(
            "robotframework-browser",
            pypi_json_fetcher=_stub_pypi(
                "robotframework-browser",
                ["playwright (>=1.55,<1.60)"],
            ),
        )
        assert spec == ">=1.55,<1.60"

    def test_strips_environment_markers(self) -> None:
        spec = playwright_constraints_for_browser_package(
            "robotframework-browser",
            pypi_json_fetcher=_stub_pypi(
                "robotframework-browser",
                ["playwright>=1.55 ; python_version >= '3.10'"],
            ),
        )
        assert spec == ">=1.55"

    def test_returns_none_on_no_playwright_constraint(self) -> None:
        assert (
            playwright_constraints_for_browser_package(
                "some-other-pkg",
                pypi_json_fetcher=_stub_pypi(
                    "some-other-pkg", ["requests>=2.0"],
                ),
            )
            is None
        )

    def test_handles_version_spec_in_package_arg(self) -> None:
        # Caller may pass "name==ver"; we only care about the name.
        spec = playwright_constraints_for_browser_package(
            "robotframework-browser==19.5.0",
            pypi_json_fetcher=_stub_pypi(
                "robotframework-browser",
                ["playwright>=1.58"],
            ),
        )
        assert spec == ">=1.58"

    def test_returns_none_on_network_failure(self) -> None:
        def _broken_fetcher(_url):
            raise TimeoutError("pretend offline")

        assert (
            playwright_constraints_for_browser_package(
                "robotframework-browser",
                pypi_json_fetcher=_broken_fetcher,
            )
            is None
        )


class TestValidation:
    def test_warns_when_pin_below_lower_bound(self, monkeypatch) -> None:
        """Pin 1.58.0 against a package demanding >=1.59 must warn."""
        monkeypatch.setattr(
            "src.environments.service.playwright_constraints_for_browser_package",
            lambda pkg, **kw: ">=1.59,<2.0",
        )
        warnings = validate_playwright_pin_against_packages(
            ["robotframework-browser-batteries"], "1.58.0",
        )
        assert len(warnings) == 1
        assert "1.58.0" in warnings[0]
        assert ">=1.59,<2.0" in warnings[0]

    def test_no_warn_when_pin_in_range(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "src.environments.service.playwright_constraints_for_browser_package",
            lambda pkg, **kw: ">=1.55,<1.60",
        )
        assert (
            validate_playwright_pin_against_packages(
                ["robotframework-browser"], "1.58.0",
            )
            == []
        )

    def test_skips_non_browser_packages(self, monkeypatch) -> None:
        called = {"count": 0}

        def _fake(pkg, **kw):
            called["count"] += 1
            return ">=999.0"

        monkeypatch.setattr(
            "src.environments.service.playwright_constraints_for_browser_package",
            _fake,
        )
        warnings = validate_playwright_pin_against_packages(
            ["requests", "some-random-lib"], "1.58.0",
        )
        assert warnings == []
        assert called["count"] == 0, "must not probe non-browser packages"

    def test_unknown_constraint_is_silent(self, monkeypatch) -> None:
        # Offline / unparseable constraint → no warning (can't block
        # the build on an unreachable PyPI).
        monkeypatch.setattr(
            "src.environments.service.playwright_constraints_for_browser_package",
            lambda pkg, **kw: None,
        )
        assert (
            validate_playwright_pin_against_packages(
                ["robotframework-browser"], "1.58.0",
            )
            == []
        )


# ---------------------------------------------------------------------------
# Integration test — actually hits PyPI to validate the current backend
# Playwright version against the *latest* published robotframework-
# browser / robotframework-browser-batteries constraints.
#
# Runs opt-in via `-m integration`. CI should schedule this nightly
# (or weekly) so drift is caught before users try to rebuild their
# Docker image.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "package_name",
    ["robotframework-browser", "robotframework-browser-batteries"],
)
def test_backend_playwright_satisfies_published_constraint(
    package_name: str,
) -> None:
    """Fetch the published `playwright` constraint of `package_name`
    and verify the backend's installed Playwright falls inside it.

    If this fails, the fix is NOT in RoboScope code — it's a
    `uv lock --upgrade-package playwright` on the backend followed
    by a relevant environment rebuild. The test message includes the
    exact command to run."""
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version

    spec_str = playwright_constraints_for_browser_package(package_name)
    if spec_str is None:
        pytest.skip(
            f"Could not fetch playwright constraint for {package_name} "
            f"from PyPI (offline?)"
        )
    spec = SpecifierSet(spec_str)
    backend_ver = Version(_installed_version("playwright"))
    assert spec.contains(backend_ver, prereleases=True), (
        f"Backend Playwright {backend_ver} is OUTSIDE the range "
        f"declared by {package_name} on PyPI: {spec_str}. "
        f"A user rebuilding their environment image will either get "
        f"a pip resolver error or two conflicting Playwright "
        f"versions. Fix: `cd backend && uv lock --upgrade-package "
        f"playwright && uv sync`. If that conflicts with other deps, "
        f"pin {package_name} to an older version that tolerates "
        f"playwright=={backend_ver}."
    )


def test_pinned_version_matches_currently_installed() -> None:
    """Sanity: the module-level helper keeps reading from
    `importlib.metadata`. A future refactor that hardcodes the
    version back as a string literal would reintroduce bug #1."""
    assert playwright_pinned_version() == _installed_version("playwright")
