"""libdoc-per-environment keyword introspection.

Story: Flow Editor — Verification & Hardening (libdoc-per-environment keyword
discovery). Runs ``robot.libdoc`` inside an environment's own venv to extract
the keywords + signatures of every installed keyword library (standard AND
third-party). This makes the Flow Editor's keyword palette work offline-first,
without depending on the optional rf-mcp live server.

The introspection runs as ONE subprocess in the target venv's Python (so it
sees exactly the libraries that env has installed — Browser, SeleniumLibrary,
…), emitting a combined JSON list to stdout.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from pathlib import Path

from src.environments.service import pip_list_installed
from src.environments.venv_utils import get_python_path
from src.explorer.library_mapping import BUILTIN_LIBRARIES, identify_rf_libraries

logger = logging.getLogger("roboscope.environments.keyword_introspection")

# Inline script executed by the TARGET venv's Python. Introspects each library
# via robot.libdoc and prints a combined JSON list. A library that can't be
# imported (missing system dep, needs a display, …) is skipped, not fatal.
_LIBDOC_SCRIPT = r"""
import json, sys
try:
    from robot.libdocpkg import LibraryDocumentation
except Exception as e:  # robotframework not installed in this venv
    print("[]")
    sys.exit(0)

out = []
for lib in sys.argv[1:]:
    try:
        doc = LibraryDocumentation(lib)
    except Exception:
        continue
    try:
        d = doc.to_dictionary()
        lib_name = d.get("name", lib)
        for kw in d.get("keywords", []):
            args = []
            for a in kw.get("args", []):
                args.append(a.get("repr") or a.get("name") or "")
            out.append({
                "name": kw.get("name", ""),
                "library": lib_name,
                "args": args,
                "shortdoc": (kw.get("shortdoc") or "").strip(),
            })
    except Exception:
        # Older RF without to_dictionary() — fall back to attribute access.
        try:
            lib_name = getattr(doc, "name", lib)
            for kw in getattr(doc, "keywords", []):
                out.append({
                    "name": getattr(kw, "name", ""),
                    "library": lib_name,
                    "args": [str(a) for a in getattr(kw, "args", [])],
                    "shortdoc": (getattr(kw, "shortdoc", "") or "").strip(),
                })
        except Exception:
            continue

print(json.dumps(out))
"""


def compute_packages_hash(venv_path: str | None) -> str:
    """Digest of the venv's installed (name, version) set. Drifts whenever a
    package is added / removed / upgraded → signals the cache is stale.

    Empty string when there is no venv (callers treat that as "nothing to do").
    """
    if not venv_path:
        return ""
    pkgs = pip_list_installed(venv_path)
    items = sorted(
        f"{p.get('name', '').lower()}=={p.get('version', '')}" for p in pkgs
    )
    return hashlib.sha256("\n".join(items).encode()).hexdigest()


def target_library_names(venv_path: str | None) -> list[str]:
    """All keyword libraries to introspect for an environment: the always-
    present standard libraries plus every installed third-party RF library."""
    names: list[str] = sorted(BUILTIN_LIBRARIES)
    if venv_path:
        installed = pip_list_installed(venv_path)
        for entry in identify_rf_libraries(installed):
            lib = entry.get("library_name")
            if lib and lib not in names:
                names.append(lib)
    return names


def introspect_keywords(venv_path: str | None, timeout: int = 90) -> list[dict[str, object]]:
    """Run libdoc for all target libraries in the env venv and return a flat
    list of ``{name, library, args, shortdoc}`` dicts. Returns ``[]`` when the
    venv is missing or the subprocess fails."""
    if not venv_path:
        return []
    python_path = get_python_path(venv_path)
    if not Path(python_path).exists():
        return []

    libs = target_library_names(venv_path)
    if not libs:
        return []

    try:
        result = subprocess.run(
            [python_path, "-c", _LIBDOC_SCRIPT, *libs],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("libdoc introspection failed: %s", e)
        return []

    if result.returncode != 0:
        logger.warning("libdoc introspection non-zero exit: %s", result.stderr[:500])
        return []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        logger.warning("libdoc introspection produced invalid JSON")
        return []
    return data if isinstance(data, list) else []
