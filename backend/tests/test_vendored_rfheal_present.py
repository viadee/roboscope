"""Story HEAL-VENDORED — guard against accidental deletion / drift
of the vendored `robotframework-roboscopeheal` source tree.

The vendored copy travels in this repo so that `make dev` works on
a fresh clone without a sibling rfheal repo and the offline release
ZIPs can ship the heal library as a pre-built wheel. Without this
test, a refactor or `rm -rf` could quietly remove the vendor
directory; everything in this repo would still import correctly
(the installed wheel is in the venv), but the next fresh setup
would fail with `No matching distribution found`.

What this test pins:

  1. The four canonical source files exist under
     `vendor/robotframework-roboscopeheal/src/RoboScopeHeal/`.
  2. The vendored `pyproject.toml` declares the canonical
     distribution name (catches an upstream rename without a
     matching vendor sync).
  3. The installed `RoboScopeHeal.__version__` matches the
     vendored `pyproject.toml` version (catches the "stale
     installed wheel, fresh source on disk" scenario where someone
     edited the vendor pyproject but didn't `uv sync`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


VENDOR_ROOT = (
    Path(__file__).resolve().parent.parent
    / "vendor"
    / "robotframework-roboscopeheal"
)


class TestVendoredHealLibPresent:
    def test_vendor_directory_exists(self) -> None:
        assert VENDOR_ROOT.is_dir(), (
            f"vendored heal lib missing at {VENDOR_ROOT}. The pyproject's "
            f"[tool.uv.sources] block points here; without the source tree, "
            f"`uv sync` fails on fresh clones and the offline build script "
            f"can't produce the wheel."
        )

    @pytest.mark.parametrize("filename", [
        "pyproject.toml",
        "LICENSE",
        "NOTICE",
        "src/RoboScopeHeal/__init__.py",
        "src/RoboScopeHeal/candidate_finder.py",
        "src/RoboScopeHeal/fingerprint.py",
        "src/RoboScopeHeal/heal_report.py",
        "src/RoboScopeHeal/library.py",
    ])
    def test_canonical_file_exists(self, filename: str) -> None:
        path = VENDOR_ROOT / filename
        assert path.is_file(), (
            f"vendored heal file missing: {filename}. The sync script "
            f"(`scripts/sync-roboscopeheal.sh`) ships every file in this "
            f"set; if one is missing, run the script or restore from "
            f"the upstream `roboscope-rfheal` repo."
        )

    def test_vendor_pyproject_declares_canonical_distribution_name(self) -> None:
        """If someone renames the upstream package on PyPI but
        forgets to mirror the rename into the vendored copy,
        `[tool.uv.sources]` keeps resolving the old name from the
        vendored path while the rest of the world expects the new
        name. Pin the contract here so the divergence surfaces in
        CI, not in a user-reported install break."""
        text = (VENDOR_ROOT / "pyproject.toml").read_text()
        m = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        assert m is not None, "vendored pyproject has no `name = …` line"
        assert m.group(1) == "robotframework-roboscopeheal", (
            f"vendored distribution name drifted: pyproject says "
            f"`{m.group(1)}`, backend pyproject depends on "
            f"`robotframework-roboscopeheal`. Re-sync from the upstream "
            f"repo OR update backend/pyproject.toml in lockstep."
        )

    def test_installed_version_matches_vendor_pyproject(self) -> None:
        """Catches the "vendored source bumped, venv not refreshed"
        scenario: `pyproject.toml` says 0.2.1 but the installed wheel
        is the 0.2.0 build sitting in site-packages from before the
        bump. `uv sync` after the bump fixes it, but without this
        test the divergence silently lives in the venv until someone
        runs into a missing API."""
        import RoboScopeHeal

        text = (VENDOR_ROOT / "pyproject.toml").read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        assert m is not None
        vendor_version = m.group(1)

        installed = RoboScopeHeal.__version__
        assert installed == vendor_version, (
            f"installed RoboScopeHeal {installed!r} doesn't match vendored "
            f"source {vendor_version!r}. Run `uv sync` (or "
            f"`uv pip install -e backend/vendor/robotframework-roboscopeheal`) "
            f"in the backend venv to refresh."
        )
