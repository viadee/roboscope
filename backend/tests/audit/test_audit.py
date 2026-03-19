"""Tests for audit log service and router."""

import json

import pytest
from sqlalchemy.orm import Session

from src.audit.service import (
    export_audit_csv,
    get_distinct_actions,
    get_distinct_resource_types,
    list_audit_logs,
    log_audit,
)
from tests.conftest import auth_header


class TestAuditService:
    """Unit tests for audit service functions."""

    def test_log_audit_basic(self, db_session: Session):
        entry = log_audit(
            db_session,
            user_id=1,
            username="admin",
            action="create",
            resource_type="run",
            resource_id=42,
            ip_address="127.0.0.1",
        )
        assert entry.id is not None
        assert entry.action == "create"
        assert entry.resource_type == "run"
        assert entry.resource_id == 42

    def test_log_audit_with_dict_detail(self, db_session: Session):
        entry = log_audit(
            db_session,
            action="update",
            resource_type="setting",
            detail={"key": "timeout", "old": 3600, "new": 7200},
        )
        assert entry.detail is not None
        parsed = json.loads(entry.detail)
        assert parsed["key"] == "timeout"

    def test_log_audit_with_string_detail(self, db_session: Session):
        entry = log_audit(
            db_session,
            action="delete",
            resource_type="report",
            detail="Bulk delete all reports",
        )
        assert entry.detail == "Bulk delete all reports"

    def test_list_audit_logs_empty(self, db_session: Session):
        logs, total = list_audit_logs(db_session)
        assert logs == []
        assert total == 0

    def test_list_audit_logs_pagination(self, db_session: Session):
        for i in range(10):
            log_audit(db_session, action="create", resource_type="run", resource_id=i)
        logs, total = list_audit_logs(db_session, page=1, page_size=5)
        assert len(logs) == 5
        assert total == 10

    def test_list_audit_logs_filter_by_action(self, db_session: Session):
        log_audit(db_session, action="create", resource_type="run")
        log_audit(db_session, action="delete", resource_type="run")
        log_audit(db_session, action="create", resource_type="report")
        logs, total = list_audit_logs(db_session, action="create")
        assert total == 2

    def test_list_audit_logs_filter_by_resource_type(self, db_session: Session):
        log_audit(db_session, action="create", resource_type="run")
        log_audit(db_session, action="create", resource_type="report")
        logs, total = list_audit_logs(db_session, resource_type="run")
        assert total == 1

    def test_list_audit_logs_filter_by_user_id(self, db_session: Session):
        log_audit(db_session, user_id=1, action="create", resource_type="run")
        log_audit(db_session, user_id=2, action="create", resource_type="run")
        logs, total = list_audit_logs(db_session, user_id=1)
        assert total == 1

    def test_export_csv(self, db_session: Session):
        log_audit(db_session, user_id=1, username="admin", action="create", resource_type="run", resource_id=1)
        log_audit(db_session, user_id=2, username="runner", action="delete", resource_type="report", resource_id=5)
        csv = export_audit_csv(db_session)
        assert "timestamp" in csv  # header
        assert "create" in csv
        assert "delete" in csv
        lines = csv.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_get_distinct_actions(self, db_session: Session):
        log_audit(db_session, action="create", resource_type="run")
        log_audit(db_session, action="delete", resource_type="run")
        log_audit(db_session, action="create", resource_type="report")
        actions = get_distinct_actions(db_session)
        assert sorted(actions) == ["create", "delete"]

    def test_get_distinct_resource_types(self, db_session: Session):
        log_audit(db_session, action="create", resource_type="run")
        log_audit(db_session, action="create", resource_type="report")
        types = get_distinct_resource_types(db_session)
        assert sorted(types) == ["report", "run"]


class TestAuditRouter:
    """API endpoint tests for audit log."""

    def test_list_audit_logs_admin(self, client, admin_user):
        resp = client.get(
            "/api/v1/audit",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_audit_logs_non_admin_forbidden(self, client, runner_user):
        resp = client.get(
            "/api/v1/audit",
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403

    def test_export_csv_admin(self, client, admin_user):
        resp = client.get(
            "/api/v1/audit/export",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_export_csv_non_admin_forbidden(self, client, runner_user):
        resp = client.get(
            "/api/v1/audit/export",
            headers=auth_header(runner_user),
        )
        assert resp.status_code == 403

    def test_get_filter_options(self, client, admin_user):
        resp = client.get(
            "/api/v1/audit/filters",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        assert "resource_types" in data

    def test_pagination_params(self, client, admin_user):
        resp = client.get(
            "/api/v1/audit?page=1&page_size=10",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["page"] == 1
        assert resp.json()["page_size"] == 10

    def test_filter_by_action(self, client, admin_user):
        resp = client.get(
            "/api/v1/audit?action=create",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200


class TestAuditMiddlewareHelpers:
    """Tests for the audit middleware helper functions."""

    def test_method_to_action_mapping(self):
        from src.audit.middleware import _method_to_action
        assert _method_to_action("POST") == "create"
        assert _method_to_action("PUT") == "update"
        assert _method_to_action("PATCH") == "update"
        assert _method_to_action("DELETE") == "delete"

    def test_resource_type_extraction(self):
        from src.audit.middleware import _get_resource_type
        assert _get_resource_type("/api/v1/runs/123") == "run"
        assert _get_resource_type("/api/v1/repos/5") == "repository"
        assert _get_resource_type("/api/v1/settings") == "setting"
        assert _get_resource_type("/api/v1/webhooks/tokens") == "api_token"
        assert _get_resource_type("/api/v1/webhooks/hooks") == "webhook"
        assert _get_resource_type("/api/v1/auth/users") == "user"

    def test_resource_id_extraction(self):
        from src.audit.middleware import _extract_resource_id
        assert _extract_resource_id("/api/v1/runs/42") == 42
        assert _extract_resource_id("/api/v1/runs/42/cancel") == 42
        assert _extract_resource_id("/api/v1/runs") is None

    def test_should_skip(self):
        from src.audit.middleware import _should_skip
        assert _should_skip("/health") is True
        assert _should_skip("/ws/notifications") is True
        assert _should_skip("/api/v1/audit") is True
        assert _should_skip("/api/v1/runs") is False

    def test_manual_audit_helper(self, db_session: Session, admin_user):
        """The manual audit() helper logs correctly."""
        from unittest.mock import MagicMock
        from src.audit.middleware import audit

        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"

        audit(
            db_session, admin_user, mock_request,
            action="create", resource_type="run", resource_id=99,
            detail={"target": "tests/"},
        )

        logs, total = list_audit_logs(db_session)
        assert total == 1
        assert logs[0].action == "create"
        assert logs[0].resource_id == 99
        assert logs[0].ip_address == "10.0.0.1"
