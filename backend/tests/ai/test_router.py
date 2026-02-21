"""API tests for AI module endpoints."""

from unittest.mock import patch

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
