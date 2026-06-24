"""EXEC.9 — DataDriver dependency availability.

DataDriver runs as a normal Library import (Listener v3) inside a data-driven
suite, so the only backend requirement is that the dependency is installed and
importable. This is the in-repo equivalent of the offline `import DataDriver`
CI gate (mirrors the roboscopeheal gate). The feature itself is gated behind the
`executionDataDriver` flag (default OFF, EXEC.2).
"""

import importlib

from src.governance.flags import FEATURE_FLAGS


def test_datadriver_is_importable():
    mod = importlib.import_module("DataDriver")
    assert mod is not None


def test_datadriver_feature_flag_registered_off():
    assert FEATURE_FLAGS["executionDataDriver"] is False
