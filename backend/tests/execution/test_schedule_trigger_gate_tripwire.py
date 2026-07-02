"""Trip-wire for audit finding 2.4: `Schedule.advanced_config` /
`Schedule.variables` are currently INERT (see the comment on the model) —
no scheduler job reads them, because no schedule-trigger path exists yet.

WHEN a future schedule-trigger path is added, it MUST route through
`gate_advanced_execution` (the same gate `POST /runs` uses) before
dispatching a run from a schedule's `advanced_config` — a schedule runs
unattended, so skipping the gate would be a code-exec bypass with no
request-time review at all.

This test can't call code that doesn't exist yet, so it does the next
best thing: it fails LOUDLY the moment someone reads
`schedule.advanced_config` / `schedule.variables` anywhere in the backend
without `gate_advanced_execution` appearing in the same file. Today there
are zero such usages (columns are write-only-by-nobody, read-by-nobody),
so both assertions hold trivially — that emptiness IS the thing being
pinned. If this test starts failing because a legitimate new call site
was added, wire it through `gate_advanced_execution` rather than
adjusting the scan.
"""

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

# Deliberately narrow patterns: attribute access on a variable literally
# named `schedule` (the established convention — see
# `execution/service.py::toggle_schedule(db, schedule: Schedule)` and
# every `get_schedule(db, schedule_id)` call site). Broader matching would
# false-positive on `ExecutionRun.advanced_config` (a different, already
# gate-protected field) which shares the attribute name.
PATTERNS = ("schedule.advanced_config", "schedule.variables")

# This test file's own docstring/comments mention the patterns; exclude it
# (and the model file, which only carries the warning comment) from the scan.
EXCLUDED_FILES = {"models.py"}


def _iter_backend_source_files():
    for path in SRC_ROOT.rglob("*.py"):
        if path.name in EXCLUDED_FILES:
            continue
        yield path


def test_no_schedule_advanced_config_reads_exist_yet():
    """Pins the CURRENT state: nothing reads these columns. If this
    assertion fails, a schedule-trigger path was added — the next
    assertion (test_any_future_reader_must_call_the_gate) is the one
    that actually matters once that happens."""
    offenders = []
    for path in _iter_backend_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(p in text for p in PATTERNS):
            offenders.append(str(path.relative_to(SRC_ROOT.parent)))

    assert offenders == [], (
        "schedule.advanced_config / schedule.variables is now read somewhere "
        f"({offenders}) — a schedule-trigger path was added. Verify EACH of "
        "those files also calls gate_advanced_execution before dispatching "
        "a run (see the warning comment on Schedule.advanced_config in "
        "src/execution/models.py), then update this test's expectations."
    )


def test_any_future_reader_must_call_the_gate():
    """Belt-and-suspenders: even if the file-exclusion list above needs to
    grow for a legitimate future PR, any file that reads
    schedule.advanced_config / schedule.variables must ALSO reference
    gate_advanced_execution — the actual invariant being protected."""
    for path in _iter_backend_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(p in text for p in PATTERNS):
            assert "gate_advanced_execution" in text, (
                f"{path.relative_to(SRC_ROOT.parent)} reads "
                "schedule.advanced_config/variables but never calls "
                "gate_advanced_execution — unaudited code-exec bypass risk "
                "for unattended schedule runs."
            )
