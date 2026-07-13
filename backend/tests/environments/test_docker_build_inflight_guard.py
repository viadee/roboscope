"""POST /environments/{id}/docker-build must not dispatch a second build
while one is already in flight (audit finding 2.3) — mirrors the
120s in-flight guard `GET /environments/{id}/keywords` already had.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.environments.models import Environment, EnvironmentPackage
from tests.conftest import auth_header


@pytest.fixture
def env_with_package(db_session: Session, admin_user):
    e = Environment(name="docker-guard-env", python_version="3.12", created_by=admin_user.id)
    db_session.add(e)
    db_session.flush()
    db_session.refresh(e)
    db_session.add(EnvironmentPackage(environment_id=e.id, package_name="robotframework"))
    db_session.commit()
    db_session.refresh(e)
    return e


class TestDockerBuildInFlightGuard:
    @patch("src.environments.router.dispatch_task")
    def test_dispatches_when_no_build_in_flight(self, mock_dispatch, client, env_with_package, admin_user):
        mock_dispatch.return_value = MagicMock(id="task-1")
        resp = client.post(
            f"/api/v1/environments/{env_with_package.id}/docker-build",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert mock_dispatch.call_count == 1

    @patch("src.environments.router.dispatch_task")
    def test_rejects_second_dispatch_while_building(
        self, mock_dispatch, client, db_session, env_with_package, admin_user
    ):
        env_with_package.docker_build_status = "building"
        db_session.commit()
        db_session.refresh(env_with_package)
        assert env_with_package.updated_at is not None

        resp = client.post(
            f"/api/v1/environments/{env_with_package.id}/docker-build",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 409
        assert mock_dispatch.call_count == 0

    @patch("src.environments.router.dispatch_task")
    def test_dispatches_again_once_the_in_flight_window_expires(
        self, mock_dispatch, client, db_session, env_with_package, admin_user
    ):
        mock_dispatch.return_value = MagicMock(id="task-2")
        env_with_package.docker_build_status = "building"
        db_session.commit()
        # Simulate a stale/stuck build: push updated_at outside the 600s window.
        db_session.query(Environment).filter(Environment.id == env_with_package.id).update(
            {"updated_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=700)}
        )
        db_session.commit()

        resp = client.post(
            f"/api/v1/environments/{env_with_package.id}/docker-build",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert mock_dispatch.call_count == 1
