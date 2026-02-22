"""API tests for AI module endpoints."""

from unittest.mock import MagicMock, patch

from tests.conftest import auth_header


class TestValidateSpecEndpoint:
    def test_validate_v1_spec(self, client, admin_user):
        """Validate a v1 .roboscope spec."""
        content = """
version: "1"
metadata:
  title: Test
  target_file: test.robot
test_sets:
  - name: Tests
    test_cases:
      - name: TC1
"""
        resp = client.post(
            "/api/v1/ai/validate",
            json={"content": content},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["test_count"] == 1

    def test_validate_v2_spec_with_preconditions(self, client, admin_user):
        """Validate a v2 spec with preconditions and external_id."""
        content = """
version: "2"
metadata:
  title: Test
  target_file: test.robot
  external_id: PROJ-100
test_sets:
  - name: Tests
    external_id: PROJ-50
    preconditions:
      - "System is running"
    test_cases:
      - name: TC1
        external_id: PROJ-101
        preconditions:
          - "User is logged in"
        steps:
          - "Click button"
          - action: "Enter text"
            data: "username: admin"
            expected_result: "Field is filled"
"""
        resp = client.post(
            "/api/v1/ai/validate",
            json={"content": content},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["test_count"] == 1

    def test_validate_invalid_structured_step(self, client, admin_user):
        """Structured step without 'action' should fail."""
        content = """
version: "2"
metadata:
  title: Test
  target_file: test.robot
test_sets:
  - name: Tests
    test_cases:
      - name: TC1
        steps:
          - data: "some data"
"""
        resp = client.post(
            "/api/v1/ai/validate",
            json={"content": content},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any("action" in e for e in data["errors"])


class TestRfKnowledgeStatus:
    def test_status_returns_available_flag(self, client, admin_user):
        """rf-knowledge status endpoint should return availability."""
        resp = client.get(
            "/api/v1/ai/rf-knowledge/status",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "url" in data
        assert data["available"] is False  # Not configured in tests


class TestRfMcpStatusEndpoint:
    def test_returns_status(self, client, admin_user):
        """GET /rf-mcp/status should return detailed status."""
        with patch("src.ai.rf_mcp_manager.get_status", return_value={
            "status": "stopped",
            "running": False,
            "port": None,
            "pid": None,
            "url": "",
            "environment_id": None,
            "error_message": "",
            "installed_version": None,
        }):
            resp = client.get("/api/v1/ai/rf-mcp/status", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["running"] is False

    def test_running_status_with_env_name(self, client, admin_user, db_session):
        """GET /rf-mcp/status resolves environment name when running."""
        from src.environments.models import Environment

        env = Environment(name="test-env", venv_path="/tmp/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)

        with patch("src.ai.rf_mcp_manager.get_status", return_value={
            "status": "running",
            "running": True,
            "port": 9090,
            "pid": 123,
            "url": "http://localhost:9090/mcp",
            "environment_id": env.id,
            "error_message": "",
            "installed_version": "1.0.0",
        }):
            resp = client.get("/api/v1/ai/rf-mcp/status", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["environment_name"] == "test-env"
        assert data["installed_version"] == "1.0.0"


class TestRfMcpSetupEndpoint:
    def test_setup_with_valid_env(self, client, admin_user, db_session):
        """POST /rf-mcp/setup should dispatch setup task and return installing status."""
        from src.environments.models import Environment

        env = Environment(name="setup-env", venv_path="/tmp/venv", created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)
        db_session.commit()

        with (
            patch("src.ai.rf_mcp_manager.stop_server", return_value={"status": "stopped"}),
            patch("src.ai.router.dispatch_task") as mock_dispatch,
        ):
            resp = client.post(
                "/api/v1/ai/rf-mcp/setup",
                json={"environment_id": env.id, "port": 9090},
                headers=auth_header(admin_user),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "installing"
        assert data["environment_name"] == "setup-env"
        mock_dispatch.assert_called_once()

    def test_setup_env_not_found(self, client, admin_user):
        """POST /rf-mcp/setup with nonexistent env should return 404."""
        resp = client.post(
            "/api/v1/ai/rf-mcp/setup",
            json={"environment_id": 99999, "port": 9090},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    def test_setup_env_without_venv(self, client, admin_user, db_session):
        """POST /rf-mcp/setup with env that has no venv_path should return 400."""
        from src.environments.models import Environment

        env = Environment(name="no-venv-env", venv_path=None, created_by=admin_user.id)
        db_session.add(env)
        db_session.flush()
        db_session.refresh(env)
        db_session.commit()

        resp = client.post(
            "/api/v1/ai/rf-mcp/setup",
            json={"environment_id": env.id, "port": 9090},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400

    def test_setup_requires_admin(self, client, runner_user):
        """POST /rf-mcp/setup should require ADMIN role."""
        resp = client.post(
            "/api/v1/ai/rf-mcp/setup",
            json={"environment_id": 1, "port": 9090},
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403


class TestRfMcpStopEndpoint:
    def test_stop_server(self, client, admin_user):
        """POST /rf-mcp/stop should stop the server."""
        with patch("src.ai.rf_mcp_manager.stop_server", return_value={"status": "stopped"}), \
             patch("src.ai.rf_mcp_manager.get_status", return_value={
                 "status": "stopped", "running": False, "port": None, "pid": None,
                 "url": "", "environment_id": None, "error_message": "", "installed_version": None,
             }):
            resp = client.post("/api/v1/ai/rf-mcp/stop", headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_stop_requires_admin(self, client, runner_user):
        """POST /rf-mcp/stop should require ADMIN role."""
        resp = client.post("/api/v1/ai/rf-mcp/stop", headers=auth_header(runner_user))
        assert resp.status_code == 403


class TestXrayExportEndpoint:
    def test_export_valid_spec(self, client, admin_user):
        """Export a .roboscope v2 spec as Xray JSON."""
        content = """
version: "2"
metadata:
  title: Login Tests
  target_file: tests/login.robot
  external_id: PROJ-100
  libraries:
    - SeleniumLibrary
test_sets:
  - name: Auth Tests
    tags: [smoke]
    external_id: PROJ-50
    preconditions:
      - "System is running"
    test_cases:
      - name: Valid Login
        priority: high
        external_id: PROJ-101
        preconditions:
          - "User is on login page"
        steps:
          - "Navigate to login page"
          - action: "Enter credentials"
            data: "user: admin, pass: secret"
            expected_result: "Fields are filled"
"""
        resp = client.post(
            "/api/v1/ai/xray/export",
            json={"content": content},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "info" in data
        assert "tests" in data
        assert data["info"]["testPlanKey"] == "PROJ-100"
        assert len(data["tests"]) == 1
        assert data["tests"][0]["testKey"] == "PROJ-101"
        # Verify steps conversion
        steps = data["tests"][0]["steps"]
        assert len(steps) == 2
        assert steps[0]["fields"]["Action"] == "Navigate to login page"
        assert steps[1]["fields"]["Data"] == "user: admin, pass: secret"
