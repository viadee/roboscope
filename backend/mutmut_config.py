"""mutmut hook (docs/TESTING.md).

Per mutant, run only the unit test files that belong to the mutated module
(`tests/<pkg>/test_<module>*.py` by convention, plus EXTRA_TESTS), instead
of the whole unit tier. `make mutation-backend` passes `--rerun-all`, so a
mutant that survives the focused run is re-checked against the full tier
before it is reported as survived.
"""

from pathlib import Path

# module → test files beyond the test_<module>*.py naming convention
EXTRA_TESTS = {
    "src/encryption.py": ["tests/audit/test_encryption.py"],
    "src/execution/resolver.py": ["tests/execution/test_runner_parity.py"],
    "src/execution/modifiers/registry.py": ["tests/execution/test_modifier_registry.py"],
    "src/explorer/rf_sections.py": ["tests/ai/test_rf_knowledge_repo_scan.py"],
    "src/recording/robot_emit.py": [
        "tests/recording/test_iframe_capture.py",
        "tests/recording/test_iframe_locator_contract.py",
    ],
    "src/recording/selector_synthesis.py": ["tests/recording/test_iframe_locator_contract.py"],
    "src/reports/parser.py": [
        "tests/reports/test_parser_hierarchy.py",
        "tests/reports/test_exec4_longname_id.py",
    ],
    "src/auth/return_to.py": ["tests/auth/test_return_to_validation.py"],
}

_FOCUSED = ".venv/bin/python -m pytest -x -q -p no:cacheprovider -o addopts="


def pre_mutation(context):
    module = Path(context.filename)
    tests = {str(p) for p in Path("tests").rglob(f"test_{module.stem}*.py")}
    tests.update(EXTRA_TESTS.get(module.as_posix(), []))
    tests = sorted(t for t in tests if Path(t).is_file())
    if tests:
        context.config.test_command = f"{_FOCUSED} {' '.join(tests)}"
