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

    @pytest.mark.parametrize("keyword_method,positional_only_params", [
        ("heal_click", ("selector",)),
        ("heal_fill_text", ("selector",)),
        ("heal_type_text", ("selector",)),
        ("heal_hover", ("selector",)),
        ("heal_press_keys", ("selector",)),
        ("heal_wait_for_elements_state", ("selector",)),
        ("heal_upload_file", ("selector",)),
        ("heal_check_checkbox", ("selector",)),
        ("heal_uncheck_checkbox", ("selector",)),
        ("heal_select_options_by", ("selector",)),
        ("heal_get_text", ("selector",)),
        ("heal_get_element_count", ("selector",)),
        ("heal_drag_and_drop", ("source_selector", "target_selector")),
    ])
    def test_selector_params_are_positional_only(
        self, keyword_method: str, positional_only_params: tuple[str, ...]
    ) -> None:
        """Regression — selector parameters MUST be Python positional-only
        (declared with `/` after them in the signature).

        Robot Framework's ``NamedArgumentResolver`` peels off
        ``arguments[:len(positional_only)]`` BEFORE running its named-arg
        detection. Without the marker, a recorded selector like
        ``xpath=//a[normalize-space()="Bio"]`` matches the
        ``name=value`` shape; the resolver sees the keyword's
        ``**kwargs`` and routes ``xpath=…`` into kwargs because
        ``xpath`` is not a known param name. The positional ``selector``
        arrives unbound and RF aborts with:

            Keyword 'RoboScopeHeal.Heal Click' expected at least 1
            non-named argument, got 0.

        Removing ``/`` from any Heal keyword reopens that silent-failure
        path; pin it parametrically across all 13 keywords so a future
        refactor that "tidies up" the slash gets caught at test time."""
        import inspect

        import RoboScopeHeal.library as heal_lib

        method = getattr(heal_lib.RoboScopeHeal, keyword_method)
        sig = inspect.signature(method)
        for name in positional_only_params:
            param = sig.parameters[name]
            assert param.kind is inspect.Parameter.POSITIONAL_ONLY, (
                f"{keyword_method}.{name} must be POSITIONAL_ONLY "
                f"(declared `/` after it), found {param.kind}. Without "
                f"this Robot Framework's argument resolver swallows "
                f"locator-strategy prefixes like `xpath=` / `css=` / "
                f"`text=` into **kwargs and the keyword fails at run-time."
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
