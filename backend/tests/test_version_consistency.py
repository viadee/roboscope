"""VERSION drift trip-wire.

`/health`, the boot banner and the startup log all report
`settings.VERSION`, a hand-maintained string in `src/config.py`. The
0.11.0 AND 0.12.0 release bumps both missed it, so released builds
identified themselves as v0.10.0. Pin it to pyproject.toml so a release
bump cannot skip it again.
"""

import tomllib
from pathlib import Path

from src.config import settings


def test_config_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == settings.VERSION, (
        "src/config.py VERSION must be bumped together with "
        "backend/pyproject.toml (surfaced via /health and the boot banner)"
    )
