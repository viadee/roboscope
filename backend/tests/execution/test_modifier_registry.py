"""EXEC.10: curated execution-modifier registry + Tier-B org loaders.

Pins: vendor entry present, build_modifier_spec module-path form, and the two
org-registration mechanisms (entry-point + config file) incl. bad-entry skip.
"""

import json

import pytest

from src.execution.modifiers import registry


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.reset_cache()
    yield
    registry.reset_cache()


def test_vendor_entry_present_and_curated():
    reg = registry.load_registry()
    assert "roboscope_tag_stamp" in reg
    entry = reg["roboscope_tag_stamp"]
    assert entry.tier == "vendor"
    assert entry.kind == "prerun"
    assert registry.is_curated_key("roboscope_tag_stamp")
    assert not registry.is_curated_key("some.user.Class")


def test_build_modifier_spec_uses_module_path():
    spec = registry.build_modifier_spec("roboscope_tag_stamp", ["smoke"])
    assert spec == "src.execution.modifiers.builtin.TagStamper:smoke"


def test_get_available_modifiers_filters_by_kind():
    assert all(e.kind == "prerun" for e in registry.get_available_modifiers("prerun"))
    assert registry.get_available_modifiers("prerebot") == [
        e for e in registry.get_available_modifiers() if e.kind == "prerebot"
    ]


def test_vendor_listener_present():
    # EXEC.11: the registry gains a listener kind + a vendor listener.
    assert "listener" in registry.VALID_KINDS
    entries = registry.get_available_modifiers("listener")
    keys = {e.key for e in entries}
    assert "roboscope_live_progress" in keys
    entry = registry.get_modifier("roboscope_live_progress")
    assert entry.kind == "listener" and entry.tier == "vendor"


def test_public_dict_hides_class_path():
    pub = registry.load_registry()["roboscope_tag_stamp"].public_dict()
    assert "class_path" not in pub
    assert pub["key"] == "roboscope_tag_stamp"


# --- Tier-B: config-file loader -------------------------------------------------


def _write_config(tmp_path, entries, name="mods.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"modifiers": entries}), encoding="utf-8")
    return str(p)


def test_config_file_loads_valid_and_skips_bad(tmp_path, monkeypatch):
    cfg = _write_config(
        tmp_path,
        [
            {
                "key": "org_tms_sync",
                # a real importable class (reuse the vendor module for the test)
                "class_path": "src.execution.modifiers.builtin.TagStamper",
                "kind": "prerebot",
                "label": "Org TMS sync",
            },
            {  # bad: un-importable class → must be skipped, not crash
                "key": "org_broken",
                "class_path": "nope.does.not.Exist",
                "kind": "prerun",
            },
            {  # bad: invalid kind → skipped
                "key": "org_badkind",
                "class_path": "src.execution.modifiers.builtin.TagStamper",
                "kind": "whenever",
            },
        ],
    )
    monkeypatch.setenv(registry.CONFIG_ENV_VAR, cfg)
    reg = registry.load_registry(force=True)
    assert "org_tms_sync" in reg
    assert reg["org_tms_sync"].tier == "org"
    assert reg["org_tms_sync"].kind == "prerebot"
    assert registry.is_curated_key("org_tms_sync")
    # bad entries skipped, server still up
    assert "org_broken" not in reg
    assert "org_badkind" not in reg


def test_listener_kind_requires_valid_api_version(tmp_path, monkeypatch):
    # EXEC.11: a class registered as kind=listener must declare a v2/v3 RF
    # listener API version, else it is skipped (a SuiteVisitor is not a listener).
    cfg = _write_config(
        tmp_path,
        [
            {  # valid listener (LiveProgressListener has ROBOT_LISTENER_API_VERSION=2)
                "key": "org_live",
                "class_path": "src.execution.modifiers.builtin.LiveProgressListener",
                "kind": "listener",
            },
            {  # NOT a listener (TagStamper is a SuiteVisitor) → skipped
                "key": "org_fake_listener",
                "class_path": "src.execution.modifiers.builtin.TagStamper",
                "kind": "listener",
            },
        ],
    )
    monkeypatch.setenv(registry.CONFIG_ENV_VAR, cfg)
    reg = registry.load_registry(force=True)
    assert "org_live" in reg
    assert "org_fake_listener" not in reg


def test_config_missing_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv(registry.CONFIG_ENV_VAR, str(tmp_path / "nope.json"))
    reg = registry.load_registry(force=True)
    assert "roboscope_tag_stamp" in reg  # vendor still loads


def test_org_key_cannot_override_vendor(tmp_path, monkeypatch):
    cfg = _write_config(
        tmp_path,
        [
            {
                "key": "roboscope_tag_stamp",  # collides with vendor
                "class_path": "src.execution.modifiers.builtin.TagStamper",
                "kind": "prerebot",
                "label": "hijack",
            }
        ],
    )
    monkeypatch.setenv(registry.CONFIG_ENV_VAR, cfg)
    reg = registry.load_registry(force=True)
    assert reg["roboscope_tag_stamp"].tier == "vendor"  # vendor wins
    assert reg["roboscope_tag_stamp"].kind == "prerun"


# --- Tier-B: entry-point loader -------------------------------------------------


class _FakeEP:
    def __init__(self, name, value, cls):
        self.name = name
        self.value = value
        self._cls = cls

    def load(self):
        if self._cls is None:
            raise ImportError("boom")
        return self._cls


def test_entry_point_discovery(monkeypatch):
    from src.execution.modifiers.builtin import TagStamper

    good = _FakeEP("org_ep_mod", "mypkg.mods:TmsSync", TagStamper)
    bad = _FakeEP("org_ep_broken", "nope:Nope", None)

    def fake_eps(group=None):
        assert group == registry.ENTRY_POINT_GROUP
        return [good, bad]

    monkeypatch.setattr(registry.importlib_metadata, "entry_points", fake_eps)
    reg = registry.load_registry(force=True)
    assert "org_ep_mod" in reg
    assert reg["org_ep_mod"].tier == "org"
    assert reg["org_ep_mod"].class_path == "mypkg.mods:TmsSync"
    assert "org_ep_broken" not in reg  # load failure skipped
