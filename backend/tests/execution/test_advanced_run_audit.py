"""EXEC.3: advanced-execution gating writes audit rows on block AND success.

The audit middleware skips responses >= 400, so a 403/422 raised from the gate
must write (and commit) its own AuditLog row. Pins the FMEA "block-path audit
gap" guard and the success-path audit.
"""

import json

import pytest
from fastapi import HTTPException

from src.audit.models import AuditLog
from src.auth.constants import Role
from src.auth.service import hash_password
from src.governance.dependencies import gate_advanced_execution
from src.governance.flags import settings_key
from src.settings.models import AppSetting


class _FakeRequest:
    client = None  # gate reads request.client.host; None → ip_address None


def _user(db_session, role=Role.EDITOR):
    from src.auth.models import User

    u = User(
        email=f"exec3-{role}@test.com",
        username=f"exec3-{role}",
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


def _audit_rows(db_session, action):
    return db_session.query(AuditLog).filter(AuditLog.action == action).all()


def test_flag_off_blocks_and_audits(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    user = _user(db_session)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(db_session, _FakeRequest(), user, {"args": ["--randomize", "all"]})
    assert exc.value.status_code == 403
    blocked = _audit_rows(db_session, "blocked")
    assert any("feature_disabled:executionAdvancedArgs" in (r.detail or "") for r in blocked)


def test_denied_arg_blocks_with_422_and_audits(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(
            db_session, _FakeRequest(), user, {"args": ["--listener", "evil.Mod"]}
        )
    assert exc.value.status_code == 422
    blocked = _audit_rows(db_session, "blocked")
    assert any("advanced_arg_rejected" in (r.detail or "") for r in blocked)


def test_insufficient_role_blocks_and_audits(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session, role=Role.VIEWER)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(db_session, _FakeRequest(), user, {"args": ["--randomize", "all"]})
    assert exc.value.status_code == 403
    assert any(
        "insufficient_role" in (r.detail or "") for r in _audit_rows(db_session, "blocked")
    )


def test_permitted_advanced_run_is_audited(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session)
    gate_advanced_execution(db_session, _FakeRequest(), user, {"args": ["--randomize", "all"]})
    rows = _audit_rows(db_session, "advanced_run")
    assert len(rows) == 1
    # The audit records the RESOLVED argv in the mandated structured shape, not
    # a raw input string (code-review 2026-06-24).
    payload = json.loads(rows[0].detail)
    assert payload["resolved_argv"] == ["--randomize", "all"]
    assert payload["prerun_modifiers"] == []
    assert payload["zones_used"] == ["z3"]
    assert payload["blocked"] is False


def test_empty_advanced_config_is_noop(db_session):
    user = _user(db_session)
    # No flag enabled, but empty config must not raise or audit.
    gate_advanced_execution(db_session, _FakeRequest(), user, None)
    gate_advanced_execution(db_session, _FakeRequest(), user, {"args": []})
    assert _audit_rows(db_session, "advanced_run") == []


# --- EXEC.10: curated vs user-code modifier routing + code-loading levers -------


def test_curated_modifier_permitted_for_editor(db_session, monkeypatch):
    # A registered (vendor) key needs only executionAdvancedArgs + EDITOR — no
    # user-code flag, no ADMIN.
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session, role=Role.EDITOR)
    gate_advanced_execution(
        db_session,
        _FakeRequest(),
        user,
        {"prerun_modifiers": [{"key": "roboscope_tag_stamp", "args": ["smoke"]}]},
    )
    rows = _audit_rows(db_session, "advanced_run")
    assert len(rows) == 1
    assert "prerun_modifier" in json.loads(rows[0].detail)["zones_used"]


def test_noncurated_modifier_requires_usercode_flag(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session, role=Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(
            db_session, _FakeRequest(), user, {"prerun_modifiers": [{"key": "evil.pkg.Mod"}]}
        )
    assert exc.value.status_code == 403
    assert any(
        "feature_disabled:executionPreRunModifierUserCode" in (r.detail or "")
        for r in _audit_rows(db_session, "blocked")
    )


def test_noncurated_modifier_requires_admin(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    _enable(db_session, "executionPreRunModifierUserCode")
    user = _user(db_session, role=Role.EDITOR)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(
            db_session, _FakeRequest(), user, {"prerun_modifiers": [{"key": "evil.pkg.Mod"}]}
        )
    assert exc.value.status_code == 403


def test_pythonpath_requires_flag_and_admin(db_session, monkeypatch, tmp_path):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    (tmp_path / "libs").mkdir()
    cfg = {"python_paths": ["libs"], "code_load_consent": True}

    # flag off → 403
    admin = _user(db_session, role=Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(db_session, _FakeRequest(), admin, cfg, str(tmp_path))
    assert exc.value.status_code == 403

    # flag on but EDITOR → 403
    _enable(db_session, "executionPythonPath")
    editor = _user(db_session, role=Role.EDITOR)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(db_session, _FakeRequest(), editor, cfg, str(tmp_path))
    assert exc.value.status_code == 403

    # flag on + ADMIN + confined path → permitted + audited
    gate_advanced_execution(db_session, _FakeRequest(), admin, cfg, str(tmp_path))
    rows = _audit_rows(db_session, "advanced_run")
    assert any("pythonpath" in json.loads(r.detail).get("zones_used", []) for r in rows)


def test_pythonpath_escaping_repo_is_422(db_session, monkeypatch, tmp_path):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    _enable(db_session, "executionPythonPath")
    admin = _user(db_session, role=Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(
            db_session,
            _FakeRequest(),
            admin,
            {"python_paths": ["../../etc"], "code_load_consent": True},
            str(tmp_path),
        )
    assert exc.value.status_code == 422
    assert any("path_rejected" in (r.detail or "") for r in _audit_rows(db_session, "blocked"))


def test_code_loading_lever_requires_server_consent(db_session, monkeypatch, tmp_path):
    # EXEC.10 review fix: consent is enforced server-side, not just in the UI.
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    _enable(db_session, "executionPythonPath")
    (tmp_path / "libs").mkdir()
    admin = _user(db_session, role=Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        # flag on, ADMIN, valid path — but NO code_load_consent
        gate_advanced_execution(
            db_session, _FakeRequest(), admin, {"python_paths": ["libs"]}, str(tmp_path)
        )
    assert exc.value.status_code == 422
    assert any("consent_required" in (r.detail or "") for r in _audit_rows(db_session, "blocked"))


def test_curated_modifier_kind_mismatch_is_422(db_session, monkeypatch):
    # A curated prerun modifier submitted in the prerebot list is rejected.
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session, role=Role.EDITOR)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(
            db_session,
            _FakeRequest(),
            user,
            {"prerebot_modifiers": [{"key": "roboscope_tag_stamp"}]},  # it's a prerun modifier
        )
    assert exc.value.status_code == 422
    blocked = _audit_rows(db_session, "blocked")
    assert any("modifier_kind_mismatch" in (r.detail or "") for r in blocked)


def test_modifier_arg_with_colon_is_422(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session, role=Role.EDITOR)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(
            db_session,
            _FakeRequest(),
            user,
            {"prerun_modifiers": [{"key": "roboscope_tag_stamp", "args": ["http://x"]}]},
        )
    assert exc.value.status_code == 422
    assert any("modifier_arg_colon" in (r.detail or "") for r in _audit_rows(db_session, "blocked"))


def test_non_list_advanced_field_is_422(db_session, monkeypatch):
    monkeypatch.delenv("ROBOSCOPE_FEATURE_EXECUTION_ADVANCED_ARGS", raising=False)
    _enable(db_session, "executionAdvancedArgs")
    user = _user(db_session, role=Role.EDITOR)
    with pytest.raises(HTTPException) as exc:
        gate_advanced_execution(db_session, _FakeRequest(), user, {"args": "--randomize all"})
    assert exc.value.status_code == 422
