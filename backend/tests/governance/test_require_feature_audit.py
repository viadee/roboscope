"""require_feature must write (and commit) its own AuditLog row on block.

The audit middleware skips responses >= 400, so a 403 raised from this
dependency would otherwise leave no trace (same FMEA gap already closed for
require_package_op / gate_advanced_execution — see
test_advanced_run_audit.py). Pins the fix for audit finding 1.1.
"""

from fastapi import HTTPException
import pytest

from src.audit.models import AuditLog
from src.auth.constants import Role
from src.auth.service import hash_password
from src.governance.dependencies import require_feature
from src.governance.flags import settings_key
from src.settings.models import AppSetting


class _FakeRequest:
    client = None  # dep reads request.client.host; None → ip_address None


def _user(db_session, role=Role.EDITOR):
    from src.auth.models import User

    u = User(
        email=f"reqfeat-{role}@test.com",
        username=f"reqfeat-{role}",
        hashed_password=hash_password("pw123456"),
        role=role,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _enable(db_session, flag):
    db_session.add(
        AppSetting(key=settings_key(flag), value="true", value_type="bool", category="features")
    )
    db_session.flush()


def _blocked_rows(db_session):
    return db_session.query(AuditLog).filter(AuditLog.action == "blocked").all()


def test_flag_off_blocks_and_audits(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    user = _user(db_session)
    dep = require_feature("executionAdvancedArgs")

    with pytest.raises(HTTPException) as exc:
        dep(_FakeRequest(), db=db_session, current_user=user)

    assert exc.value.status_code == 403
    rows = _blocked_rows(db_session)
    assert any(
        "feature_disabled:executionAdvancedArgs" in (r.detail or "")
        and r.resource_type == "feature_flag"
        and r.user_id == user.id
        for r in rows
    )


def test_flag_on_does_not_audit_or_raise(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session)
    dep = require_feature("executionAdvancedArgs")

    dep(_FakeRequest(), db=db_session, current_user=user)  # must not raise

    assert _blocked_rows(db_session) == []
