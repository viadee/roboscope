"""V14.2 — environment variable CRUD, validation and run-injection resolution."""

import pytest

from src.encryption import is_encrypted
from src.environments.models import Environment, EnvironmentVariable
from src.environments.service import decrypt_variable_value, resolve_env_vars
from src.execution.tasks import _get_env_config
from tests.conftest import auth_header

URL = "/api/v1/environments"


def _vurl(env_id, var_id):
    return f"{URL}/{env_id}/variables/{var_id}"


@pytest.fixture
def env(db_session, admin_user):
    e = Environment(name="vars-env", python_version="3.12", created_by=admin_user.id)
    db_session.add(e)
    db_session.flush()
    return e


def _add(client, user, env_id, key, value, is_secret=False):
    return client.post(f"{URL}/{env_id}/variables", headers=auth_header(user),
                       json={"key": key, "value": value, "is_secret": is_secret})


def test_patch_and_delete_happy_path(client, db_session, admin_user, env):
    var_id = _add(client, admin_user, env.id, "BASE_URL", "https://a").json()["id"]
    r = client.patch(_vurl(env.id, var_id), headers=auth_header(admin_user),
                     json={"key": "BASE_URL2", "value": "https://b"})
    assert r.status_code == 200
    assert (r.json()["key"], r.json()["value"]) == ("BASE_URL2", "https://b")
    r = client.delete(_vurl(env.id, var_id), headers=auth_header(admin_user))
    assert r.status_code == 204
    assert db_session.get(EnvironmentVariable, var_id) is None


def test_variable_from_other_env_is_404(client, db_session, admin_user, env):
    other = Environment(name="other-env", python_version="3.12", created_by=admin_user.id)
    db_session.add(other)
    db_session.flush()
    var_id = _add(client, admin_user, other.id, "K", "v").json()["id"]
    h = auth_header(admin_user)
    assert client.patch(_vurl(env.id, var_id), headers=h, json={"value": "x"}).status_code == 404
    assert client.delete(_vurl(env.id, var_id), headers=h).status_code == 404


def test_duplicate_key_is_409(client, admin_user, env):
    _add(client, admin_user, env.id, "K", "1")
    assert _add(client, admin_user, env.id, "K", "2").status_code == 409
    var_id = _add(client, admin_user, env.id, "J", "3").json()["id"]
    r = client.patch(_vurl(env.id, var_id), headers=auth_header(admin_user), json={"key": "K"})
    assert r.status_code == 409


@pytest.mark.parametrize("key", ["PATH", "path", "VIRTUAL_ENV", "PYTHONPATH", "PythonHome",
                                 "LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "NODE_OPTIONS",
                                 "1BAD", "has-dash", "a b"])
def test_reserved_or_invalid_key_is_422(client, admin_user, env, key):
    assert _add(client, admin_user, env.id, key, "x").status_code == 422
    var_id = _add(client, admin_user, env.id, "OK_KEY", "x").json()["id"]
    r = client.patch(_vurl(env.id, var_id), headers=auth_header(admin_user), json={"key": key})
    assert r.status_code == 422


def test_secret_reencrypted_and_empty_value_keeps_old(client, db_session, admin_user, env):
    r = _add(client, admin_user, env.id, "API_KEY", "s3cr3t", is_secret=True)
    assert r.json()["value"] == "********"
    var_id = r.json()["id"]
    h = auth_header(admin_user)

    # Empty value keeps the stored secret.
    r = client.patch(_vurl(env.id, var_id), headers=h, json={"value": ""})
    assert r.status_code == 200 and "s3cr3t" not in r.text
    var = db_session.get(EnvironmentVariable, var_id)
    db_session.refresh(var)
    assert decrypt_variable_value(var) == "s3cr3t"

    # A new value is re-encrypted at rest and never echoed.
    r = client.patch(_vurl(env.id, var_id), headers=h, json={"value": "n3w"})
    assert r.json()["value"] == "********"
    db_session.refresh(var)
    assert is_encrypted(var.value) and decrypt_variable_value(var) == "n3w"

    # Listing masks and must not overwrite the stored secret (the session commits).
    assert client.get(f"{URL}/{env.id}/variables", headers=h).json()[0]["value"] == "********"
    db_session.refresh(var)
    assert decrypt_variable_value(var) == "n3w"


def test_toggle_secret_with_empty_value_keeps_value(client, db_session, admin_user, env):
    var_id = _add(client, admin_user, env.id, "TOKEN", "abc").json()["id"]
    client.patch(_vurl(env.id, var_id), headers=auth_header(admin_user),
                 json={"value": "", "is_secret": True})
    var = db_session.get(EnvironmentVariable, var_id)
    db_session.refresh(var)
    assert var.is_secret and is_encrypted(var.value) and decrypt_variable_value(var) == "abc"


def test_viewer_cannot_mutate(client, admin_user, viewer_user, env):
    var_id = _add(client, admin_user, env.id, "K", "v").json()["id"]
    h = auth_header(viewer_user)
    assert _add(client, viewer_user, env.id, "K2", "v").status_code == 403
    assert client.patch(_vurl(env.id, var_id), headers=h, json={"value": "x"}).status_code == 403
    assert client.delete(_vurl(env.id, var_id), headers=h).status_code == 403


def test_env_config_resolves_decrypted_env_vars(client, db_session, admin_user, env):
    _add(client, admin_user, env.id, "BASE_URL", "https://staging")
    _add(client, admin_user, env.id, "API_KEY", "s3cr3t", is_secret=True)
    # A legacy row predating validation is skipped at injection.
    db_session.add(EnvironmentVariable(environment_id=env.id, key="PYTHONPATH",
                                       value="/evil", is_secret=False))
    db_session.flush()
    expected = {"BASE_URL": "https://staging", "API_KEY": "s3cr3t"}
    assert resolve_env_vars(db_session, env.id) == expected
    assert _get_env_config(db_session, env.id)["env_vars"] == expected


def test_clone_copies_variables(client, db_session, admin_user, env):
    _add(client, admin_user, env.id, "BASE_URL", "https://staging")
    r = client.post(f"{URL}/{env.id}/clone", headers=auth_header(admin_user),
                    params={"new_name": "vars-clone"})
    assert r.status_code == 201
    assert resolve_env_vars(db_session, r.json()["id"]) == {"BASE_URL": "https://staging"}
