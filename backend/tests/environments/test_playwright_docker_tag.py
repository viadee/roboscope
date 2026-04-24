"""Regression: the Playwright Docker base image must always match the
installed `playwright` Python package.

Background — production incident 2026-04-24
-------------------------------------------
A user ran a Browser-library test in a freshly-built Docker image and
got:

    Error: browserType.launch: Executable doesn't exist at
    /ms-playwright/chromium_headless_shell-1217/chrome-linux/headless_shell
    Looks like Playwright was just updated to 1.59.1.
    Please update docker image as well.
      - current: mcr.microsoft.com/playwright/python:v1.52.0-noble
      - required: mcr.microsoft.com/playwright/python:v1.59.1-noble

The bug: `generate_dockerfile` hardcoded the image tag as the literal
string `v1.52.0-noble` while `pyproject.toml` pinned the Python client
with a loose `playwright>=1.49.0` lower bound. `uv sync` pulled in a
much newer `playwright` (1.58+), the Docker image stayed at 1.52, and
the Playwright protocol handshake aborted on first launch.

The fix derived the image tag from `importlib.metadata.version("playwright")`.
This test pins that behaviour so a future cleanup can't re-introduce
the mismatch silently.
"""

from __future__ import annotations

import subprocess
from importlib.metadata import version

import pytest

from src.environments.service import (
    generate_dockerfile,
    playwright_docker_base_image,
    playwright_pinned_version,
)


class TestTagDerivation:
    """Unit tests — no Docker daemon required."""

    def test_tag_matches_installed_playwright(self) -> None:
        installed = version("playwright")
        tag = playwright_docker_base_image()
        assert tag == f"mcr.microsoft.com/playwright/python:v{installed}-noble", (
            f"Docker base image tag {tag!r} must mirror the installed "
            f"playwright version {installed!r}. Mismatch means a fresh "
            f"`docker build` will ship a browser binary that doesn't "
            f"speak the backend's Playwright protocol."
        )

    def test_dockerfile_embeds_derived_tag_for_browser_package(self) -> None:
        df = generate_dockerfile(
            python_version="3.12",
            packages=["robotframework", "robotframework-browser"],
        )
        expected_tag = playwright_docker_base_image()
        assert expected_tag in df, (
            "Generated Dockerfile must embed the derived Playwright tag "
            "when a Browser-library package is requested."
        )
        # Defensive: the old hardcoded v1.52.0 literal must never reappear.
        assert "v1.52.0-noble" not in df or "v1.52.0-noble" in expected_tag, (
            "Hardcoded v1.52.0 tag detected in generated Dockerfile"
        )

    def test_dockerfile_uses_python_slim_when_no_browser(self) -> None:
        df = generate_dockerfile(
            python_version="3.12",
            packages=["robotframework", "requests"],
        )
        assert "python:3.12-slim" in df
        assert "mcr.microsoft.com/playwright" not in df
        assert "playwright==" not in df  # no pin when no browser

    def test_explicit_base_image_wins(self) -> None:
        df = generate_dockerfile(
            python_version="3.12",
            packages=["robotframework-browser"],
            base_image="custom/internal:pinned-42",
        )
        assert "FROM custom/internal:pinned-42" in df
        assert "mcr.microsoft.com/playwright" not in df
        # Explicit base image means the caller owns the version pairing —
        # we don't double-install playwright.
        assert "playwright==" not in df

    def test_dockerfile_force_pins_playwright_matching_base_image(self) -> None:
        """Regression — the incident that made this fix necessary.

        Microsoft's playwright/python:v{X.Y.Z}-noble image carries
        browser binaries for exactly that Playwright version. When the
        user's packages (robotframework-browser) transitively upgrade
        Python Playwright past {X.Y.Z}, the client-binary handshake
        fails at chromium.launch() with 'Please update docker image
        as well'.

        The generated Dockerfile must therefore re-pin
        `playwright==<X.Y.Z>` AFTER the user packages install.
        """
        df = generate_dockerfile(
            python_version="3.12",
            packages=["robotframework-browser"],
        )
        pinned = playwright_pinned_version()
        # The pin line must exist.
        assert f"'playwright=={pinned}'" in df, (
            f"Dockerfile must force-pin playwright=={pinned} so "
            f"transitive upgrades don't drift past the base image's "
            f"browser binaries."
        )
        # And it must come AFTER the user package install so pip
        # respects the pin.
        install_block_end = df.find("robotframework-browser")
        pin_index = df.find(f"'playwright=={pinned}'")
        assert install_block_end < pin_index, (
            "Force-pin must come after user package install; otherwise "
            "the transitive upgrade overwrites it."
        )

    def test_dockerfile_force_pins_playwright_for_batteries_too(self) -> None:
        # Same safety applies to robotframework-browser-batteries.
        df = generate_dockerfile(
            python_version="3.12",
            packages=["robotframework-browser-batteries"],
        )
        assert f"'playwright=={playwright_pinned_version()}'" in df


# ---------------------------------------------------------------------------
# Integration test — actually builds the image + runs Playwright inside
# it. Requires a Docker daemon and pulls the playwright image (~1 GB).
# Guarded with pytest.mark.integration.
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "version"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.integration
def test_derived_docker_tag_is_pullable() -> None:
    """The tag derived from the installed `playwright` version must
    actually exist in Microsoft's registry.

    Microsoft's contract: the image tag `v{X.Y.Z}-noble` ships the
    browser binaries matching the Python `playwright=={X.Y.Z}` client
    exactly. The tag *existing* is therefore proof of version
    alignment — we don't need to introspect image internals.

    The failure mode this test catches: someone bumps
    `playwright>=1.49.0` to a version Microsoft has not yet published
    a matching image for (rare — MS pushes images ~same day). The
    test surfaces that window before users hit it in production.

    Opt-in via `-m integration`. Uses `docker manifest inspect` — no
    full image pull needed (fast, cheap, Docker-daemon-only).
    """
    if not _docker_available():
        pytest.skip("docker daemon not reachable on this host")

    image = playwright_docker_base_image()

    # manifest inspect is a HEAD against the registry; does NOT pull
    # the image, runs in <1 s even on a cold cache.
    result = subprocess.run(
        ["docker", "manifest", "inspect", image],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"Derived Playwright Docker tag {image!r} is not pullable.\n"
        f"Installed playwright == {version('playwright')}. Either "
        f"Microsoft has not yet published this tag (wait 24 h) OR "
        f"the tag format changed (update playwright_docker_base_image()).\n"
        f"manifest-inspect stderr: {result.stderr.strip()[:400]}"
    )


@pytest.mark.integration
def test_freshly_built_image_chromium_launch(tmp_path) -> None:
    """Ultimate proof: generate a Dockerfile that installs Playwright
    explicitly, build the image, run a real `chromium.launch()` inside
    it. Heavier than the version-match test (needs build + chromium
    boot) but catches edge cases like a broken overlay install."""
    if not _docker_available():
        pytest.skip("docker daemon not reachable on this host")

    # Force playwright as an explicit dep so the layered install lands
    # it on the default Python path — robotframework-browser-batteries
    # bundles browsers but doesn't re-expose the `playwright` module.
    df_content = generate_dockerfile(
        python_version="3.12",
        packages=["robotframework-browser", f"playwright=={version('playwright')}"],
    )
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(df_content, encoding="utf-8")

    image_tag = f"roboscope-playwright-smoke:{tmp_path.name[-24:]}".lower()
    build = subprocess.run(
        [
            "docker", "build",
            "-f", str(dockerfile),
            "-t", image_tag,
            str(tmp_path),
        ],
        capture_output=True, text=True, timeout=900,
    )
    if build.returncode != 0:
        pytest.fail(
            "docker build failed:\n"
            f"STDOUT:\n{build.stdout[-2000:]}\n\nSTDERR:\n{build.stderr[-2000:]}"
        )

    try:
        run = subprocess.run(
            [
                "docker", "run", "--rm", image_tag,
                "python", "-c",
                "from playwright.sync_api import sync_playwright\n"
                "with sync_playwright() as pw:\n"
                "    b = pw.chromium.launch(headless=True)\n"
                "    page = b.new_context().new_page()\n"
                "    page.goto('about:blank')\n"
                "    b.close()\n"
                "print('LAUNCH_OK')\n",
            ],
            capture_output=True, text=True, timeout=180,
        )
        assert run.returncode == 0, (
            "Fresh image cannot launch Chromium — likely Playwright-vs-"
            "base-image version mismatch. "
            f"STDOUT:\n{run.stdout}\nSTDERR:\n{run.stderr}"
        )
        assert "LAUNCH_OK" in run.stdout
    finally:
        subprocess.run(
            ["docker", "rmi", "-f", image_tag],
            capture_output=True, timeout=30,
        )
