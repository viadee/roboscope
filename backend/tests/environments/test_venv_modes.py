"""Environments backed by RoboScope's own interpreter or an imported venv.

Pins: non-managed venvs are ADMIN-only, never auto-created, never deleted
from disk, and RoboScope's own interpreter refuses package uninstalls.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.environments.venv_utils import get_python_path, is_managed_venv, venv_kind
from tests.conftest import auth_header

URL = "/api/v1/environments"


@pytest.fixture(autouse=True)
def _no_dispatch():
    with patch("src.environments.router.dispatch_task") as disp:
        disp.return_value = MagicMock(id="fake")
        yield disp


def test_system_mode_uses_roboscope_interpreter(client, admin_user, _no_dispatch):
    r = client.post(URL, json={"name": "own-python", "venv_mode": "system"}, headers=auth_header(admin_user))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["venv_path"] == sys.prefix
    assert body["venv_kind"] == "system"
    assert body["python_version"] == "%d.%d" % sys.version_info[:2]
    _no_dispatch.assert_not_called()  # nothing to create or seed


def test_existing_mode_imports_venv(client, admin_user, _no_dispatch):
    r = client.post(URL, json={"name": "imported", "venv_mode": "existing", "venv_path": sys.prefix},
                    headers=auth_header(admin_user))
    assert r.status_code == 201, r.text
    assert r.json()["venv_kind"] in ("system", "external")
    _no_dispatch.assert_not_called()


def test_existing_mode_rejects_path_without_python(client, admin_user, tmp_path):
    r = client.post(URL, json={"name": "bogus", "venv_mode": "existing", "venv_path": str(tmp_path)},
                    headers=auth_header(admin_user))
    assert r.status_code == 422
    assert "No Python interpreter" in r.json()["detail"]


def test_existing_mode_requires_path(client, admin_user):
    r = client.post(URL, json={"name": "nopath", "venv_mode": "existing"}, headers=auth_header(admin_user))
    assert r.status_code == 422


def test_non_managed_modes_are_admin_only(client, db_session):
    from src.auth.constants import Role
    from src.auth.models import User
    from src.auth.service import hash_password

    editor = User(email="ed@test.com", username="ed", hashed_password=hash_password("x12345678"), role=Role.EDITOR)
    db_session.add(editor)
    db_session.flush()
    for mode in ("system", "existing"):
        r = client.post(URL, json={"name": f"x-{mode}", "venv_mode": mode, "venv_path": sys.prefix},
                        headers=auth_header(editor))
        assert r.status_code == 403


def test_delete_never_removes_unmanaged_venv(client, admin_user, tmp_path):
    fake = tmp_path / "keepme"
    (fake / "bin").mkdir(parents=True)
    with patch("src.environments.venv_utils.probe_python_version", return_value="3.12"):
        r = client.post(URL, json={"name": "keep", "venv_mode": "existing", "venv_path": str(fake)},
                        headers=auth_header(admin_user))
    assert r.status_code == 201, r.text
    assert client.delete(f"{URL}/{r.json()['id']}", headers=auth_header(admin_user)).status_code == 204
    assert fake.is_dir()


def test_uninstall_blocked_in_own_interpreter(client, admin_user):
    r = client.post(URL, json={"name": "own", "venv_mode": "system"}, headers=auth_header(admin_user))
    env_id = r.json()["id"]
    r = client.delete(f"{URL}/{env_id}/packages/fastapi", headers=auth_header(admin_user))
    assert r.status_code == 409


def test_managed_detection(tmp_path):
    from src.config import settings

    assert is_managed_venv(str(Path(settings.VENVS_DIR) / "abc"))
    assert not is_managed_venv(str(tmp_path))
    assert not is_managed_venv(None)
    assert venv_kind(sys.prefix) == "system"


def test_python_path_falls_back_to_python3(tmp_path):
    if sys.platform == "win32":
        pytest.skip("posix layout")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python3").touch()
    assert get_python_path(str(tmp_path)).endswith("bin/python3")
    (tmp_path / "bin" / "python").touch()
    assert get_python_path(str(tmp_path)).endswith("bin/python")
