"""Tests for AuditEventType StrEnum + log_event helper."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from src.audit.event_types import AuditEventType, resource_type_for
from src.audit.models import AuditLog
from src.audit.service import log_event


def test_event_type_enum_values_match_string_literals():
    """Rename-guard: downstream SIEMs match on these literals."""
    assert AuditEventType.SSO_LOGIN_SUCCESS == "sso.login.success"
    assert AuditEventType.SSO_LOGIN_FAILURE == "sso.login.failure"
    assert AuditEventType.TEAM_MEMBER_SYNCED_FROM_IDP == "team.member.synced_from_idp"


def test_resource_type_is_first_segment():
    assert resource_type_for(AuditEventType.SSO_LOGIN_SUCCESS) == "sso"
    assert resource_type_for(AuditEventType.TEAM_MEMBER_SYNCED_FROM_IDP) == "team"


def test_log_event_helper_round_trip(db_session: Session):
    log_event(
        db_session,
        AuditEventType.SSO_LOGIN_SUCCESS,
        user_id=None,
        detail={"email": "a@b.c", "return_to": "/"},
    )
    db_session.flush()

    row = db_session.query(AuditLog).filter_by(action="sso.login.success").one()
    assert row.resource_type == "sso"
    assert row.user_id is None
    assert row.detail is not None
    parsed = json.loads(row.detail)
    assert parsed["email"] == "a@b.c"


def test_log_event_without_detail_stores_null(db_session: Session):
    log_event(db_session, AuditEventType.SSO_LOGIN_FAILURE)
    db_session.flush()
    row = db_session.query(AuditLog).filter_by(action="sso.login.failure").one()
    assert row.detail is None
    assert row.resource_type == "sso"
