"""EXEC.2: the advanced-execution GOV flags must resolve OFF by default.

These flags are the deliberate exception to the registry's "default-ON"
convention. Because `resolve_flag` falls back to `FEATURE_FLAGS.get(key, True)`,
an unregistered key would default ON — so this pins that all three are
registered explicitly with False and resolve OFF when unset.
"""

import pytest

from src.governance.flags import FEATURE_FLAGS, env_key, resolve_flag

EXEC_FLAGS = (
    "executionAdvancedArgs",
    "executionPreRunModifierUserCode",
    "executionDataDriver",
)


@pytest.mark.parametrize("flag", EXEC_FLAGS)
def test_exec_flag_registered_default_false(flag):
    assert flag in FEATURE_FLAGS, f"{flag} must be explicitly registered (else it defaults ON)"
    assert FEATURE_FLAGS[flag] is False


@pytest.mark.parametrize("flag", EXEC_FLAGS)
def test_exec_flag_resolves_off_when_unset(flag, db_session, monkeypatch):
    monkeypatch.delenv(env_key(flag), raising=False)
    r = resolve_flag(db_session, flag)
    assert r.value is False
    assert r.locked is False
