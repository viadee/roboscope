"""Offline browser-pack lay-down — make Robot Framework Browser tests
work on an air-gapped install without the network-only `rfbrowser init`.

Covers:
  - venv_utils browser-wrapper path resolution + the variant-safe copy
    (`browser_wrapper_node_modules`, `browser_local_browsers_dir`,
    `bundled_browsers_present`, `lay_down_bundled_browsers`),
  - tasks resolvers (`resolve_browser_pack_dir`),
  - the offline-first branch in `_run_rfbrowser_init` (lay down bundled
    browsers and skip the network init when a pack is present).

These exercise the Unix wrapper layout (`lib/python*/…`); pytest only
runs on the Linux/macOS CI legs, so the `win32` branch isn't covered here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.environments.venv_utils import (
    browser_local_browsers_dir,
    browser_wrapper_node_modules,
    bundled_browsers_present,
    lay_down_bundled_browsers,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fixtures build the Unix wrapper layout (lib/python*/…)",
)


def _make_venv_with_browser(tmp_path: Path, *, with_playwright_core: bool) -> Path:
    """Create a fake venv whose Browser wrapper mirrors what a real
    `-batteries` install lays down (node_modules + playwright-core, no
    browsers) or a bare standard install (node_modules without
    playwright-core)."""
    venv = tmp_path / "venv"
    wrapper = (
        venv / "lib" / "python3.12" / "site-packages"
        / "Browser" / "wrapper" / "node_modules"
    )
    wrapper.mkdir(parents=True)
    if with_playwright_core:
        (wrapper / "playwright-core").mkdir()
    return venv


def _make_pack(tmp_path: Path) -> Path:
    """A bundled browser-pack: a `.local-browsers/` subtree with one
    browser build dir holding a fake executable."""
    pack = tmp_path / "browser-pack"
    build = pack / ".local-browsers" / "chromium_headless_shell-1223"
    build.mkdir(parents=True)
    (build / "chrome-headless-shell").write_text("#!/fake/binary\n")
    # A dotfile sibling (playwright writes `.links`) that must be copied too.
    (pack / ".local-browsers" / ".links").write_text("{}\n")
    return pack


def test_wrapper_and_local_browsers_resolution(tmp_path: Path) -> None:
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    node_modules = browser_wrapper_node_modules(str(venv))
    assert node_modules is not None and node_modules.name == "node_modules"
    target = browser_local_browsers_dir(str(venv))
    assert target is not None
    assert target.parent.name == "playwright-core"
    assert target.name == ".local-browsers"


def test_local_browsers_dir_none_without_playwright_core(tmp_path: Path) -> None:
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=False)
    assert browser_local_browsers_dir(str(venv)) is None


def test_bundled_browsers_present_detects_build_dir(tmp_path: Path) -> None:
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    assert bundled_browsers_present(str(venv)) is False
    target = browser_local_browsers_dir(str(venv))
    assert target is not None
    (target / "chromium_headless_shell-1223").mkdir(parents=True)
    assert bundled_browsers_present(str(venv)) is True


def test_lay_down_links_browsers_into_playwright_core(tmp_path: Path) -> None:
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    pack = _make_pack(tmp_path)

    assert lay_down_bundled_browsers(str(venv), str(pack)) is True

    target = browser_local_browsers_dir(str(venv))
    assert target is not None
    # On a normal filesystem the target is a LINK to the shared pack (no
    # per-venv duplication); the browser binary is reachable through it.
    assert target.is_symlink()
    assert target.resolve() == (pack / ".local-browsers").resolve()
    laid = target / "chromium_headless_shell-1223" / "chrome-headless-shell"
    assert laid.is_file()
    assert (target / ".links").is_file()  # dotfile sibling reachable too
    assert bundled_browsers_present(str(venv)) is True


def test_lay_down_shares_one_pack_across_two_venvs(tmp_path: Path) -> None:
    """Two environments must point at the SAME shared pack — the whole
    reason for linking instead of copying."""
    pack = _make_pack(tmp_path)
    venv_a = _make_venv_with_browser(tmp_path / "a", with_playwright_core=True)
    venv_b = _make_venv_with_browser(tmp_path / "b", with_playwright_core=True)

    assert lay_down_bundled_browsers(str(venv_a), str(pack)) is True
    assert lay_down_bundled_browsers(str(venv_b), str(pack)) is True

    shared = (pack / ".local-browsers").resolve()
    assert browser_local_browsers_dir(str(venv_a)).resolve() == shared
    assert browser_local_browsers_dir(str(venv_b)).resolve() == shared


def test_lay_down_copy_fallback_when_link_unsupported(tmp_path: Path) -> None:
    """When the filesystem refuses a link, fall back to a real copy so
    offline Browser tests still work (e.g. restricted Windows)."""
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    pack = _make_pack(tmp_path)

    with patch(
        "src.environments.venv_utils._link_browser_dir", return_value=False
    ):
        assert lay_down_bundled_browsers(str(venv), str(pack)) is True

    target = browser_local_browsers_dir(str(venv))
    assert target is not None
    assert not target.is_symlink()  # real copied dir, not a link
    assert (target / "chromium_headless_shell-1223" / "chrome-headless-shell").is_file()
    assert bundled_browsers_present(str(venv)) is True


def test_lay_down_returns_false_without_playwright_core(tmp_path: Path) -> None:
    """Standard variant with no node_modules/playwright-core: nothing to
    copy into → caller must fall back to network rfbrowser init."""
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=False)
    pack = _make_pack(tmp_path)
    assert lay_down_bundled_browsers(str(venv), str(pack)) is False


def test_lay_down_returns_false_when_pack_has_no_browsers(tmp_path: Path) -> None:
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    empty_pack = tmp_path / "empty-pack"
    empty_pack.mkdir()
    assert lay_down_bundled_browsers(str(venv), str(empty_pack)) is False


def test_lay_down_is_idempotent(tmp_path: Path) -> None:
    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    pack = _make_pack(tmp_path)
    assert lay_down_bundled_browsers(str(venv), str(pack)) is True
    # Second call: already present → returns True, doesn't raise on existing dirs.
    assert lay_down_bundled_browsers(str(venv), str(pack)) is True


# ----- tasks.resolve_browser_pack_dir -----


def test_resolve_browser_pack_dir_from_setting(tmp_path: Path) -> None:
    from src.environments.tasks import resolve_browser_pack_dir

    pack = _make_pack(tmp_path)
    with patch("src.config.settings.BROWSER_PACK_DIR", str(pack)):
        assert resolve_browser_pack_dir() == pack


def test_resolve_browser_pack_dir_none_when_absent(tmp_path: Path) -> None:
    from src.environments.tasks import resolve_browser_pack_dir

    # Setting points at a dir without `.local-browsers` → not a valid pack.
    bogus = tmp_path / "nope"
    bogus.mkdir()
    with patch("src.config.settings.BROWSER_PACK_DIR", str(bogus)), patch(
        "src.environments.tasks._dist_root", return_value=tmp_path
    ):
        assert resolve_browser_pack_dir() is None


# ----- _run_rfbrowser_init offline branch -----


def test_rfbrowser_init_lays_down_pack_and_skips_network(tmp_path: Path) -> None:
    """When a pack is present and the wrapper is ready, the offline
    lay-down runs and the network `rfbrowser init` (subprocess) is skipped."""
    from src.environments import tasks

    venv = _make_venv_with_browser(tmp_path, with_playwright_core=True)
    pack = _make_pack(tmp_path)

    with patch.object(
        tasks, "resolve_browser_pack_dir", return_value=pack
    ), patch.object(tasks, "_broadcast_package_status") as mock_broadcast, patch(
        "src.environments.tasks.subprocess.run"
    ) as mock_run:
        tasks._run_rfbrowser_init(
            str(venv), env_id=1, package_name="robotframework-browser-batteries",
            pkg=None, session=MagicMock(),
        )

    mock_run.assert_not_called()  # network rfbrowser init never ran
    assert bundled_browsers_present(str(venv)) is True
    statuses = [c.args[2] for c in mock_broadcast.call_args_list]
    assert "initialized" in statuses


def test_rfbrowser_init_falls_back_to_network_without_playwright_core(
    tmp_path: Path,
) -> None:
    """Pack present but wrapper not ready (no playwright-core) → the
    lay-down returns False and the network init runs as before."""
    from src.environments import tasks

    venv = _make_venv_with_browser(tmp_path, with_playwright_core=False)
    pack = _make_pack(tmp_path)
    ok_result = MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(
        tasks, "resolve_browser_pack_dir", return_value=pack
    ), patch.object(tasks, "_broadcast_package_status"), patch(
        "src.environments.tasks.subprocess.run", return_value=ok_result
    ) as mock_run, patch.object(
        tasks, "check_rfbrowser_initialized", return_value=True
    ):
        tasks._run_rfbrowser_init(
            str(venv), env_id=2, package_name="robotframework-browser",
            pkg=None, session=MagicMock(),
        )

    mock_run.assert_called_once()  # fell through to the network init
