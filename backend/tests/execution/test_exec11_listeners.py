"""EXEC.11: custom listeners coexist with system listeners + resolve curated keys."""

from src.execution.tasks import _format_modifiers, _merge_listeners


def test_system_listeners_come_first_and_are_never_dropped():
    system = ["src.execution.runners.quarantine_listener.QuarantineSkipListener:/snap"]
    user = ["org.pkg.TmsStream", "src.execution.modifiers.builtin.LiveProgressListener"]
    merged = _merge_listeners(system, user)
    assert merged[0] == system[0]  # system-first
    assert merged[1:] == user  # user appended, order preserved
    # a user listener cannot remove the system one
    assert system[0] in merged


def test_merge_handles_empty_sides():
    assert _merge_listeners(None, None) is None
    assert _merge_listeners(["sys"], None) == ["sys"]
    assert _merge_listeners(None, ["usr"]) == ["usr"]
    assert _merge_listeners([], []) is None


def test_merge_dedups_a_user_listener_equal_to_a_system_one():
    # A user listener cannot double a system listener's callbacks.
    system = ["sys.Quarantine:/snap"]
    user = ["sys.Quarantine:/snap", "org.Tms"]
    assert _merge_listeners(system, user) == ["sys.Quarantine:/snap", "org.Tms"]


def test_curated_listener_key_resolves_to_registry_class_path():
    specs = _format_modifiers([{"key": "roboscope_live_progress"}])
    assert specs == ["src.execution.modifiers.builtin.LiveProgressListener"]


def test_usercode_listener_emitted_as_given():
    specs = _format_modifiers([{"key": "org.pkg.TmsStream", "args": ["live"]}])
    assert specs == ["org.pkg.TmsStream:live"]
