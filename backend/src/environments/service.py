"""Environment management service."""

import json
import logging
import shutil
import subprocess
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.environments.models import (
    Environment,
    EnvironmentKeywordCache,
    EnvironmentPackage,
    EnvironmentVariable,
)
from src.environments.schemas import EnvCreate, EnvUpdate, EnvVarCreate, PackageCreate

logger = logging.getLogger("roboscope.environments")


def list_environments(db: Session) -> list[Environment]:
    """List all environments."""
    result = db.execute(select(Environment).order_by(Environment.name))
    return list(result.scalars().all())


def get_environment(db: Session, env_id: int) -> Environment | None:
    """Get an environment by ID."""
    result = db.execute(select(Environment).where(Environment.id == env_id))
    return result.scalar_one_or_none()


def create_environment(db: Session, data: EnvCreate, user_id: int) -> Environment:
    """Create a new environment."""
    venv_dir = Path(settings.VENVS_DIR)
    venv_dir.mkdir(parents=True, exist_ok=True)
    venv_path = str(venv_dir / data.name)

    env = Environment(
        name=data.name,
        python_version=data.python_version,
        venv_path=venv_path,
        docker_image=data.docker_image,
        is_default=data.is_default,
        description=data.description,
        index_url=data.index_url,
        extra_index_url=data.extra_index_url,
        created_by=user_id,
    )

    # If this is the new default, unset other defaults
    if data.is_default:
        _unset_defaults(db)

    db.add(env)
    db.flush()
    db.refresh(env)
    return env


def update_environment(db: Session, env: Environment, data: EnvUpdate) -> Environment:
    """Update an environment."""
    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("is_default"):
        _unset_defaults(db)

    for key, value in update_data.items():
        setattr(env, key, value)

    db.flush()
    db.refresh(env)
    return env


def delete_environment(db: Session, env: Environment) -> None:
    """Delete an environment and its venv."""
    if env.venv_path:
        venv_path = Path(env.venv_path)
        if venv_path.exists():
            shutil.rmtree(venv_path, ignore_errors=True)

    # Delete related packages and variables
    packages = db.execute(
        select(EnvironmentPackage).where(EnvironmentPackage.environment_id == env.id)
    )
    for pkg in packages.scalars().all():
        db.delete(pkg)

    variables = db.execute(
        select(EnvironmentVariable).where(EnvironmentVariable.environment_id == env.id)
    )
    for var in variables.scalars().all():
        db.delete(var)

    db.delete(env)
    db.flush()


def clone_environment(db: Session, env: Environment, new_name: str, user_id: int) -> Environment:
    """Clone an environment with a new name."""
    new_env = create_environment(
        db,
        EnvCreate(
            name=new_name,
            python_version=env.python_version,
            docker_image=env.docker_image,
            is_default=False,
            description=f"Clone of {env.name}",
            index_url=env.index_url,
            extra_index_url=env.extra_index_url,
        ),
        user_id,
    )

    # Copy packages
    packages = list_packages(db, env.id)
    for pkg in packages:
        new_pkg = EnvironmentPackage(
            environment_id=new_env.id,
            package_name=pkg.package_name,
            version=pkg.version,
        )
        db.add(new_pkg)

    # Copy variables
    variables = list_variables(db, env.id)
    for var in variables:
        new_var = EnvironmentVariable(
            environment_id=new_env.id,
            key=var.key,
            value=var.value,
            is_secret=var.is_secret,
        )
        db.add(new_var)

    db.flush()
    db.refresh(new_env)
    return new_env


# --- Packages ---


def list_packages(db: Session, env_id: int) -> list[EnvironmentPackage]:
    """List packages in an environment.

    Automatically resets stuck packages (pending/installing with no active task)
    to 'failed' so the UI doesn't show a perpetual spinner.
    """
    from src.environments.tasks import is_package_task_active

    result = db.execute(
        select(EnvironmentPackage)
        .where(EnvironmentPackage.environment_id == env_id)
        .order_by(EnvironmentPackage.package_name)
    )
    packages = list(result.scalars().all())

    dirty = False
    for pkg in packages:
        if pkg.install_status in ("pending", "installing"):
            if not is_package_task_active(env_id, pkg.package_name):
                pkg.install_status = "failed"
                pkg.install_error = "Installation interrupted or never started."
                dirty = True
                logger.warning(
                    "Reset stuck package '%s' in env %d (was '%s')",
                    pkg.package_name, env_id, pkg.install_status,
                )
    if dirty:
        db.commit()

    return packages


def add_package(db: Session, env_id: int, data: PackageCreate) -> EnvironmentPackage:
    """Add a package to an environment."""
    pkg = EnvironmentPackage(
        environment_id=env_id,
        package_name=data.package_name,
        version=data.version,
    )
    db.add(pkg)
    db.flush()
    db.refresh(pkg)
    return pkg


def remove_package(db: Session, env_id: int, package_name: str) -> None:
    """Remove a package from an environment."""
    result = db.execute(
        select(EnvironmentPackage).where(
            EnvironmentPackage.environment_id == env_id,
            EnvironmentPackage.package_name == package_name,
        )
    )
    pkg = result.scalar_one_or_none()
    if pkg:
        db.delete(pkg)
        db.flush()


# --- Variables ---


def list_variables(db: Session, env_id: int) -> list[EnvironmentVariable]:
    """List variables in an environment."""
    result = db.execute(
        select(EnvironmentVariable)
        .where(EnvironmentVariable.environment_id == env_id)
        .order_by(EnvironmentVariable.key)
    )
    return list(result.scalars().all())


def add_variable(db: Session, env_id: int, data: EnvVarCreate) -> EnvironmentVariable:
    """Add a variable to an environment. Secret values are encrypted at rest."""
    value = data.value
    if data.is_secret and value:
        from src.encryption import encrypt_value
        value = encrypt_value(value)

    var = EnvironmentVariable(
        environment_id=env_id,
        key=data.key,
        value=value,
        is_secret=data.is_secret,
    )
    db.add(var)
    db.flush()
    db.refresh(var)
    return var


def decrypt_variable_value(var: EnvironmentVariable) -> str:
    """Decrypt a secret variable's value. Returns plaintext for non-secrets."""
    if not var.is_secret or not var.value:
        return var.value or ""
    from src.encryption import decrypt_value, is_encrypted
    if is_encrypted(var.value):
        return decrypt_value(var.value)
    # Legacy plaintext secret — return as-is
    return var.value


def _unset_defaults(db: Session) -> None:
    """Unset all default environments."""
    result = db.execute(
        select(Environment).where(Environment.is_default == True)
    )
    for env in result.scalars().all():
        env.is_default = False


# --- PyPI ---


def search_pypi(query: str) -> list[dict]:
    """Search PyPI for packages using the JSON API."""
    results = []
    try:
        with httpx.Client(timeout=10.0) as client:
            # PyPI doesn't have a search API anymore, use the simple JSON endpoint
            # Search by trying exact match first, then fall back to warehouse search
            response = client.get(
                f"https://pypi.org/pypi/{query}/json",
            )
            if response.status_code == 200:
                data = response.json()
                info = data.get("info", {})
                results.append({
                    "name": info.get("name", query),
                    "version": info.get("version", ""),
                    "summary": info.get("summary", ""),
                    "author": info.get("author", ""),
                })

            # Also search for robotframework-related packages if query is short
            if len(query) >= 2:
                search_response = client.get(
                    "https://pypi.org/simple/",
                    headers={"Accept": "application/vnd.pypi.simple.v1+json"},
                )
                if search_response.status_code == 200:
                    data = search_response.json()
                    projects = data.get("projects", [])
                    query_lower = query.lower()
                    matched = [
                        p for p in projects
                        if query_lower in p.get("name", "").lower()
                    ][:20]

                    for proj in matched:
                        name = proj.get("name", "")
                        if not any(r["name"] == name for r in results):
                            results.append({
                                "name": name,
                                "version": "",
                                "summary": "",
                                "author": "",
                            })
    except Exception as e:
        logger.warning("PyPI search failed: %s", e)

    return results[:20]


def _strip_version(pkg_spec: str) -> str:
    """Strip version specifier from a package spec."""
    return pkg_spec.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("!=")[0].strip().lower().replace("_", "-")


def _has_browser_package(packages: list[str]) -> bool:
    """Check if any package spec refers to robotframework-browser (standard, needs rfbrowser init)."""
    return any(_strip_version(p) == "robotframework-browser" for p in packages)


def _has_batteries_package(packages: list[str]) -> bool:
    """Check if any package spec refers to robotframework-browser-batteries (self-contained)."""
    return any(_strip_version(p) == "robotframework-browser-batteries" for p in packages)


def playwright_constraints_for_browser_package(
    package_spec: str,
    *,
    pypi_json_fetcher=None,
) -> str | None:
    """Return the `playwright` version-specifier that a `robotframework-
    browser*` package declares as its transitive requirement.

    Used by `validate_playwright_pin_against_packages` to double-check
    at Dockerfile-generation time that our backend-derived Playwright
    pin satisfies whatever the user's package expects — catching the
    class of drift "backend playwright is 1.58.0, but new
    robotframework-browser-batteries requires >=1.59.0" BEFORE the
    docker build burns minutes and fails at chromium.launch().

    Args:
        package_spec: plain package name OR "name==ver" OR "name>=ver".
            Only the name is used — version is ignored here.
        pypi_json_fetcher: optional `(url) -> bytes` override. Used by
            tests to stub out network calls.

    Returns the `playwright` constraint string (e.g. "<1.60,>=1.55")
    or None if no constraint is declared / PyPI is unreachable /
    parsing fails. `None` means "unknown, skip the check" — never
    blocks the build.
    """
    import json
    import re
    import urllib.error
    import urllib.request

    name = re.split(r"[<>=!~\s]", package_spec, maxsplit=1)[0].strip()
    if not name:
        return None

    url = f"https://pypi.org/pypi/{name}/json"
    try:
        if pypi_json_fetcher is None:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                raw = resp.read()
        else:
            raw = pypi_json_fetcher(url)
        data = json.loads(raw)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None
    except Exception:
        return None

    requires = (data.get("info") or {}).get("requires_dist") or []
    for req in requires:
        # Lines look like "playwright>=1.55,<1.60" or
        # "playwright (>=1.55,<1.60)" or "playwright ; python_version >= '3.10'".
        # We only need the playwright ones.
        m = re.match(r"^\s*playwright\b(.*)$", req)
        if not m:
            continue
        tail = m.group(1)
        # Strip environment markers (anything after ';').
        tail = tail.split(";", 1)[0].strip()
        # Strip parens around the spec.
        tail = tail.strip("()").strip()
        return tail or None
    return None


def validate_playwright_pin_against_packages(
    packages: list[str],
    pinned_version: str,
) -> list[str]:
    """Cross-check our force-pinned Playwright version against the
    constraints declared by every `robotframework-browser*` package in
    the user's list.

    Returns a list of human-readable warnings — empty list if all good
    or if constraints couldn't be checked (offline, stale PyPI).
    Callers decide whether to surface warnings as build-time errors,
    log them, or ignore — this function itself never raises.
    """
    warnings: list[str] = []
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
    except Exception:
        return warnings

    try:
        pin_ver = Version(pinned_version)
    except Exception:
        return warnings

    for pkg in packages:
        pkg_lower = pkg.lower()
        if not (
            pkg_lower.startswith("robotframework-browser")
            or pkg_lower == "playwright"
        ):
            continue
        spec_str = playwright_constraints_for_browser_package(pkg)
        if not spec_str:
            continue
        try:
            spec = SpecifierSet(spec_str)
        except Exception:
            continue
        if not spec.contains(pin_ver, prereleases=True):
            warnings.append(
                f"Package {pkg!r} declares playwright{spec_str!r}, but "
                f"the backend-derived Playwright pin is "
                f"{pinned_version!r}. A rebuild will either install "
                f"two Playwright versions or fail at dependency "
                f"resolution. Upgrade the backend's playwright to a "
                f"version in the required range."
            )
    return warnings


def rfbrowser_node_playwright_version(
    package_spec: str = "robotframework-browser",
    *,
    pypi_json_fetcher=None,
    wheel_fetcher=None,
) -> str | None:
    """Fetch the Node-side `playwright` version that
    `robotframework-browser`'s shipped `Browser/wrapper/package.json`
    declares as its dependency.

    This — NOT the backend's installed Python `playwright` package —
    is the actual source of truth for which MS-Playwright Docker image
    tag matches. The Node-side gRPC wrapper (also used by batteries
    via `BrowserBatteries/bin/grpc_server`) is what does
    `chromium.launch()`, and it expects browser binaries matching the
    Node-Playwright version baked into the rfbrowser wheel.

    Returns a pinned version string like ``"1.59.1"`` or None on any
    failure (offline / wheel layout changed / parse error). Callers
    fall back to `playwright_pinned_version()`.
    """
    import io
    import json
    import re
    import urllib.error
    import urllib.request
    import zipfile

    name = re.split(r"[<>=!~\s]", package_spec, maxsplit=1)[0].strip()
    if not name:
        return None

    pypi_url = f"https://pypi.org/pypi/{name}/json"
    try:
        if pypi_json_fetcher is None:
            with urllib.request.urlopen(pypi_url, timeout=10) as resp:  # noqa: S310
                meta = json.loads(resp.read())
        else:
            meta = json.loads(pypi_json_fetcher(pypi_url))
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return None

    # Pick a wheel — prefer manylinux x86_64 since that's what we Dockerfile-target,
    # fall back to any wheel.
    files = meta.get("urls") or []
    wheel = next(
        (f for f in files if "manylinux_2_17_x86_64" in f.get("filename", "")),
        None,
    )
    if wheel is None:
        wheel = next(
            (f for f in files if f.get("filename", "").endswith(".whl")),
            None,
        )
    if wheel is None:
        return None

    try:
        if wheel_fetcher is None:
            buf = urllib.request.urlopen(wheel["url"], timeout=120).read()  # noqa: S310
        else:
            buf = wheel_fetcher(wheel["url"])
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    try:
        zf = zipfile.ZipFile(io.BytesIO(buf))
        # Look for the wrapper package.json. Robotframework-browser places it at
        # Browser/wrapper/package.json; tolerate layout drift defensively.
        candidates = [
            n for n in zf.namelist()
            if n.endswith("/package.json") and "wrapper" in n.lower()
        ]
        for entry in candidates:
            try:
                payload = json.loads(zf.read(entry).decode("utf-8", errors="replace"))
            except Exception:
                continue
            deps = {**(payload.get("dependencies") or {}),
                    **(payload.get("devDependencies") or {})}
            spec = deps.get("playwright") or deps.get("playwright-core")
            if not spec:
                continue
            # Strip caret/tilde/range prefixes — pin to the exact version
            # rfbrowser was built against. Anything beyond that is
            # speculation about what browsers Microsoft published.
            # `re.search` (not `match`) because the spec often starts
            # with `^` or `~`.
            cleaned = re.search(r"\d+\.\d+\.\d+", spec)
            if cleaned:
                return cleaned.group(0)
        return None
    except (zipfile.BadZipFile, KeyError):
        return None


def playwright_pinned_version() -> str:
    """Return the Playwright Python version the Docker container must
    be pinned to — derived from the currently installed backend package.

    Single source of truth used by both:
      * `playwright_docker_base_image()` (chooses the matching browser binaries)
      * the `uv pip install --system playwright==<ver>` pin that the
        generated Dockerfile emits AFTER user packages, so transitive
        upgrades (e.g. `robotframework-browser` pulling in a newer
        playwright) can't push the Python client ahead of the base
        image's browser binaries.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("playwright").strip()
    except PackageNotFoundError:
        return "1.58.0"


def playwright_docker_base_image() -> str:
    """Return the Microsoft Playwright Python Docker tag that matches
    the backend's installed `playwright` Python package.

    Background — production incident 2026-04-24: the backend's
    Playwright client does a protocol handshake with the
    `headless_shell` binary bundled in the base image; a drift of
    even one minor version aborts `chromium.launch()` with
    "Please update docker image as well". Deriving the tag from the
    installed package keeps `uv sync` and the next docker build in
    lockstep.

    Paired with `playwright_pinned_version()` — same version — which
    gets re-installed inside the container so transitive upgrades via
    robotframework-browser can't push the Python client ahead of the
    browser binaries.

    Falls back to v1.58.0 on introspection failure (unusual packaging
    setups). Live runs against a mismatched image still fail loudly
    — that is what the regression tests catch.
    """
    # Microsoft tags releases as `v{X.Y.Z}-noble`. Scheme stable since
    # v1.40 — safe to compose by string.
    return f"mcr.microsoft.com/playwright/python:v{playwright_pinned_version()}-noble"


def generate_dockerfile(
    python_version: str,
    packages: list[str],
    base_image: str | None = None,
) -> str:
    """Generate a Dockerfile that installs the given packages.

    Pure function, no DB access.
    When robotframework-browser is among the packages, the official
    Microsoft Playwright Python image is used as base (includes Python
    and all browser system dependencies). Node.js is installed separately
    because rfbrowser init requires npm. Otherwise, python-slim.
    """
    needs_browser_standard = _has_browser_package(packages)
    needs_batteries = _has_batteries_package(packages)
    needs_browser_any = needs_browser_standard or needs_batteries

    if base_image:
        base = base_image
    else:
        # Story Playwright-fix-E (2026-04-27): always start from
        # `python:<ver>-slim` and install Playwright browsers
        # explicitly. rfbrowser ships ahead of Microsoft's published
        # image tags (e.g. rfbrowser 19.14.2 ships Node-Playwright
        # 1.59.1, but Microsoft only has up to v1.58.0-noble). The MS
        # base image is therefore unreliable as a long-term anchor.
        # python-slim has nothing pre-installed → no version drift to
        # accommodate.
        base = f"python:{python_version}-slim"

    lines = [
        f"FROM {base}",
        "",
        "COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv",
        "",
    ]

    # Node.js 20 LTS. Story Playwright-fix-E (2026-04-27): both
    # `robotframework-browser` AND `-batteries` need Node — rfbrowser init
    # is the cleanest way to lay down browsers compatible with rfbrowser's
    # Node-side wrapper, regardless of whether the user picked the
    # standard or the batteries variant. The earlier "batteries is
    # self-contained" assumption was wrong: batteries replaces the gRPC
    # server binary but does NOT bundle browser binaries.
    if needs_browser_any:
        lines += [
            "# Node.js required for rfbrowser init (downloads matching browsers)",
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "    curl gnupg \\",
            "    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \\",
            "    && apt-get install -y --no-install-recommends nodejs \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
        ]

    lines.append("RUN uv pip install --system --no-cache-dir \\")
    for i, pkg in enumerate(packages):
        suffix = "" if i == len(packages) - 1 else " \\"
        lines.append(f"    {pkg}{suffix}")
    lines.append("")

    # Story Playwright-fix-E (2026-04-27, verified by real-build smoke):
    # rfbrowser init is the canonical path to populate
    # `Browser/wrapper/node_modules/playwright-core/.local-browsers/`
    # with browsers matching rfbrowser's Node-side Playwright. After
    # that, `npx playwright install-deps chromium` adds the Linux apt
    # libs Chromium needs at runtime (libnss3, libnspr4, ...). One pass
    # for both rfbrowser variants — batteries had the same browser-
    # missing problem; only its grpc_server differs.
    if needs_browser_any:
        lines.append(
            "# Story Playwright-fix-E: rfbrowser init lays down browsers"
        )
        lines.append(
            "# matching its Node-side Playwright wrapper; install-deps"
        )
        lines.append("# adds the system libs Chromium needs at runtime.")
        lines.append("RUN rfbrowser init \\")
        lines.append(
            "    && cd /usr/local/lib/python3.12/site-packages/Browser/wrapper \\"
        )
        lines.append("    && npx playwright install-deps chromium \\")
        lines.append("    && rm -rf /var/lib/apt/lists/*")
        lines.append("")

    lines.append('CMD ["python", "-m", "robot", "--help"]')
    lines.append("")
    return "\n".join(lines)


def docker_pip_list(docker_image: str) -> list[dict]:
    """List packages installed in a Docker image via 'docker run --rm <image> uv pip list'."""
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", docker_image, "uv", "pip", "list", "--system", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.warning("docker pip list failed for %s: %s", docker_image, e)

    return []


# --- Keyword cache (libdoc-per-environment discovery) ---

def get_keyword_cache(db: Session, env_id: int) -> EnvironmentKeywordCache | None:
    """Return the cached keyword-introspection row for an environment, if any."""
    return db.execute(
        select(EnvironmentKeywordCache).where(
            EnvironmentKeywordCache.environment_id == env_id
        )
    ).scalar_one_or_none()


def keyword_cache_is_fresh(
    db: Session, env: Environment, cache: EnvironmentKeywordCache | None
) -> bool:
    """A cache is fresh when it is ready and no package change has happened since
    it was built.

    Uses the environment's `packages_changed_at` timestamp (already bumped
    whenever a package is installed/removed/upgraded) rather than shelling out
    to `uv pip list` on every read — that subprocess defeated the cache on the
    hot palette-load path. The libdoc digest is still recomputed off the hot
    path inside `rebuild_keyword_cache`."""
    if cache is None or cache.status != "ready" or cache.updated_at is None:
        return False
    changed = env.packages_changed_at
    if changed is None:
        return True  # packages never changed since the cache was built
    # Normalize tzinfo (SQLite returns naive; in-session values may be aware).
    built = cache.updated_at.replace(tzinfo=None)
    changed = changed.replace(tzinfo=None)
    return built >= changed


def rebuild_keyword_cache(db: Session, env_id: int) -> EnvironmentKeywordCache | None:
    """Introspect the environment's venv via libdoc and persist the result.

    Synchronous — intended to run inside the background task. Returns the
    updated cache row (or None if the environment vanished)."""
    from datetime import UTC, datetime

    from src.environments.keyword_introspection import (
        compute_packages_hash,
        introspect_keywords,
    )

    env = get_environment(db, env_id)
    if env is None:
        return None

    cache = get_keyword_cache(db, env_id)
    if cache is None:
        cache = EnvironmentKeywordCache(environment_id=env_id)
        db.add(cache)

    try:
        keywords = introspect_keywords(env.venv_path)
        cache.keywords_json = json.dumps(keywords)
        cache.source_hash = compute_packages_hash(env.venv_path)
        cache.status = "ready"
        cache.error = None
    except Exception as e:  # never let introspection crash the worker
        logger.warning("keyword introspection failed for env %s: %s", env_id, e)
        cache.status = "error"
        cache.error = str(e)[:500]
    cache.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(cache)
    return cache


def pip_list_installed(venv_path: str | None) -> list[dict]:
    """List all packages installed in a venv via uv pip list --format=json."""
    if not venv_path:
        return []

    from src.environments.venv_utils import pip_list_cmd, get_python_path

    python_path = get_python_path(venv_path)
    if not Path(python_path).exists():
        return []

    try:
        result = subprocess.run(
            pip_list_cmd(venv_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.warning("pip list failed: %s", e)

    return []
