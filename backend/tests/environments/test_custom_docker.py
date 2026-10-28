"""Story V15.5 — user-edited/imported Dockerfile and user-provided image."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.environments.models import Environment, EnvironmentPackage
from src.environments.schemas import EnvResponse
from src.environments.tasks import build_docker_image
from tests.conftest import auth_header

ENV_FLAG = "ROBOSCOPE_FEATURE_PACKAGE_MANAGEMENT"
CUSTOM = "# my file\nARG PY=3.12\nFROM python:${PY}-slim\nRUN pip install robotframework\n"


@pytest.fixture
def env(db_session: Session, admin_user):
    e = Environment(name="custom-docker-env", python_version="3.12", created_by=admin_user.id)
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


def _url(env_id: int, suffix: str = "dockerfile") -> str:
    return f"/api/v1/environments/{env_id}/{suffix}"


class TestDockerfileOverride:
    def test_put_get_reset_roundtrip(self, client, env, admin_user):
        h = auth_header(admin_user)
        # No packages, no override → 400 as before.
        assert client.get(_url(env.id), headers=h).status_code == 400

        resp = client.put(_url(env.id), json={"content": CUSTOM}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["dockerfile_customized"] is True
        assert "dockerfile_override" not in resp.json()  # text never ships in env responses

        got = client.get(_url(env.id), headers=h)
        assert got.status_code == 200 and got.text == CUSTOM

        listed = client.get("/api/v1/environments", headers=h).json()
        assert next(e for e in listed if e["id"] == env.id)["dockerfile_customized"] is True

        resp = client.put(_url(env.id), json={"content": None}, headers=h)
        assert resp.json()["dockerfile_customized"] is False
        assert client.get(_url(env.id), headers=h).status_code == 400

    def test_empty_content_clears(self, client, env, admin_user):
        h = auth_header(admin_user)
        client.put(_url(env.id), json={"content": CUSTOM}, headers=h)
        resp = client.put(_url(env.id), json={"content": "   \n"}, headers=h)
        assert resp.json()["dockerfile_customized"] is False

    @pytest.mark.parametrize(
        "content",
        [
            "RUN echo hi\nFROM python:3.12\n",  # FROM not first
            "# only a comment\n",
            "ARG X=1\n",
            "FROM python:3.12\nRUN echo \x00\n",
            "FROM python:3.12\n" + "#" * (100 * 1024),
        ],
    )
    def test_validation_rejects(self, client, env, admin_user, content):
        resp = client.put(_url(env.id), json={"content": content}, headers=auth_header(admin_user))
        assert resp.status_code == 422

    def test_lowercase_from_accepted(self, client, env, admin_user):
        h = auth_header(admin_user)
        resp = client.put(_url(env.id), json={"content": "from alpine\n"}, headers=h)
        assert resp.status_code == 200

    @pytest.mark.parametrize("user_fixture", ["viewer_user", "runner_user"])
    def test_put_forbidden_below_editor(self, client, env, request, user_fixture):
        user = request.getfixturevalue(user_fixture)
        resp = client.put(_url(env.id), json={"content": CUSTOM}, headers=auth_header(user))
        assert resp.status_code == 403

    def test_put_forbidden_when_flag_off(self, client, env, admin_user, monkeypatch):
        monkeypatch.setenv(ENV_FLAG, "false")
        resp = client.put(_url(env.id), json={"content": CUSTOM}, headers=auth_header(admin_user))
        assert resp.status_code == 403
        assert "feature_disabled:packageManagement" in resp.json()["detail"]

    @patch("src.environments.router.dispatch_task")
    def test_build_with_override_needs_no_packages(
        self, mock_dispatch, client, env, admin_user, db_session
    ):
        h = auth_header(admin_user)
        assert client.post(_url(env.id, "docker-build"), headers=h).status_code == 400
        env.dockerfile_override = CUSTOM
        db_session.commit()
        assert client.post(_url(env.id, "docker-build"), headers=h).status_code == 200
        assert mock_dispatch.call_count == 1


def _run_build(db_session, env_id, client_mock):
    with (
        patch("src.environments.tasks.get_sync_session") as mock_gs,
        patch("src.docker_client.get_docker_client", return_value=client_mock),
        patch("src.environments.tasks._broadcast_docker_build_log"),
        patch("src.environments.tasks._check_docker_disk_space"),
    ):
        mock_gs.return_value.__enter__ = MagicMock(return_value=db_session)
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)
        return build_docker_image(env_id)


def _dockerfile_sent(client_mock) -> str:
    import tarfile

    fileobj = client_mock.api.build.call_args.kwargs["fileobj"]
    fileobj.seek(0)
    with tarfile.open(fileobj=fileobj) as tar:
        return tar.extractfile("Dockerfile").read().decode()


class TestBuildTask:
    def _client(self):
        c = MagicMock()
        c.api.build.return_value = iter([{"stream": "Step 1/1\n"}])
        c.images.prune.return_value = {}
        return c

    def test_build_uses_override_and_resets_custom_flag(self, db_session, env):
        env.dockerfile_override = CUSTOM
        env.docker_image = "myorg/rf:1"
        env.docker_image_custom = True
        db_session.commit()
        c = self._client()

        result = _run_build(db_session, env.id, c)

        assert result["status"] == "success"
        assert _dockerfile_sent(c) == CUSTOM
        db_session.refresh(env)
        assert env.docker_image == "roboscope/custom-docker-env:latest"
        assert env.docker_image_custom is False

    def test_build_without_override_uses_generated(self, db_session, env):
        db_session.add(
            EnvironmentPackage(environment_id=env.id, package_name="robotframework-requests")
        )
        db_session.commit()
        c = self._client()
        _run_build(db_session, env.id, c)
        sent = _dockerfile_sent(c)
        assert sent.startswith("FROM python:3.12-slim")
        assert "robotframework-requests" in sent


class TestCustomImage:
    def test_custom_image_is_never_stale(self, env):
        env.docker_image = "myorg/rf:1"
        env.docker_image_custom = True
        assert EnvResponse.model_validate(env).docker_image_stale is False
        env.docker_image_custom = False
        assert EnvResponse.model_validate(env).docker_image_stale is True  # never built

    def test_patch_sets_and_clears_custom_image(self, client, env, admin_user):
        h = auth_header(admin_user)
        resp = client.patch(
            f"/api/v1/environments/{env.id}",
            json={"docker_image": " myorg/rf:1 ", "docker_image_custom": True},
            headers=h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["docker_image"] == "myorg/rf:1"
        assert body["docker_image_custom"] is True
        assert body["docker_image_stale"] is False

        resp = client.patch(
            f"/api/v1/environments/{env.id}",
            json={"docker_image": None, "docker_image_custom": False},
            headers=h,
        )
        assert resp.json()["docker_image"] is None and resp.json()["docker_image_custom"] is False

    @pytest.mark.parametrize("image", ["my image", "x" * 501])
    def test_patch_rejects_bad_reference(self, client, env, admin_user, image):
        resp = client.patch(
            f"/api/v1/environments/{env.id}",
            json={"docker_image": image, "docker_image_custom": True},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 422

    def test_custom_without_image_rejected(self, client, env, admin_user):
        resp = client.patch(
            f"/api/v1/environments/{env.id}",
            json={"docker_image_custom": True},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 422

    def test_image_change_forbidden_when_flag_off(self, client, env, admin_user, monkeypatch):
        monkeypatch.setenv(ENV_FLAG, "false")
        h = auth_header(admin_user)
        resp = client.patch(
            f"/api/v1/environments/{env.id}",
            json={"docker_image": "myorg/rf:1", "docker_image_custom": True},
            headers=h,
        )
        assert resp.status_code == 403
        # Unrelated fields stay editable with the flag off.
        resp = client.patch(f"/api/v1/environments/{env.id}", json={"description": "x"}, headers=h)
        assert resp.status_code == 200


def test_lightweight_migration_adds_columns(tmp_path):
    """An environments table from before V15.5 gains both columns, idempotently."""
    import src.database as database
    import src.main  # noqa: F401 — register every model on Base.metadata

    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    database.Base.metadata.create_all(eng)
    with eng.begin() as conn:
        conn.execute(text("ALTER TABLE environments DROP COLUMN dockerfile_override"))
        conn.execute(text("ALTER TABLE environments DROP COLUMN docker_image_custom"))
        conn.execute(
            text(
                "INSERT INTO environments (name, python_version, default_runner_type, "
                "max_docker_containers, is_default, created_by, created_at, updated_at) "
                "VALUES ('old', '3.12', 'subprocess', 1, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    for _ in range(2):  # idempotent
        with eng.begin() as conn:
            database._migrate_sqlite(conn)

    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT dockerfile_override, docker_image_custom FROM environments")
        ).one()
        assert row == (None, 0)
