"""Story FLAKY-2 — Robot Framework listener that skips quarantined tests.

Registered via the runner's `--listener` argument whenever the running
repository has at least one `FlakyQuarantine` row. Reads the snapshot
written by `execute_test_run` and calls `BuiltIn().skip(...)` for each
matching test at `start_test` time — the test is marked SKIP in
output.xml, not FAIL.

Robot Framework Listener API v3 semantics:
  start_test(self, data, result) → called before the test body runs.
  Calling BuiltIn().skip(msg) here short-circuits the body.

A bug in this module must NEVER take the run down. All lookups are
guarded by try/except; a failed read of the quarantine file means the
listener effectively becomes a no-op (the test just runs normally).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROBOT_LISTENER_API_VERSION = 3


class QuarantineSkipListener:
    """Listener constructor takes one argument: the path to a JSON file
    holding `[{"suite_name": "...", "test_name": "...", "reason": "..."}]`.
    Robot invokes ``QuarantineSkipListener("/path/to/quarantine.json")``
    via the ``--listener`` CLI flag."""

    def __init__(self, quarantine_json_path: str) -> None:
        self._entries: list[dict[str, str]] = []
        try:
            p = Path(quarantine_json_path)
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                # Filter down to records we actually understand.
                for r in raw:
                    if not isinstance(r, dict):
                        continue
                    if "test_name" not in r:
                        continue
                    self._entries.append({
                        "suite_name": str(r.get("suite_name", "")),
                        "test_name": str(r["test_name"]),
                        "reason": str(r.get("reason", "") or ""),
                    })
        except Exception:
            # Any parse / IO issue → listener is effectively inert.
            self._entries = []

    def start_test(self, data: Any, result: Any) -> None:
        """Check the incoming test against the quarantine list. On match,
        call BuiltIn().skip() with a prefixed, localised-safe message."""
        if not self._entries:
            return
        # data.name is the test's short name. Matching on test_name
        # only — suite_name match would require canonical comparison
        # which Robot's listener API doesn't easily expose.
        target = getattr(data, "name", None)
        if not isinstance(target, str):
            return
        match = next(
            (e for e in self._entries if e["test_name"] == target),
            None,
        )
        if match is None:
            return
        reason = match.get("reason") or "quarantined"
        msg = f"[roboscope-quarantine] {reason}"
        try:
            from robot.libraries.BuiltIn import BuiltIn  # local import
            BuiltIn().skip(msg)
        except Exception:
            # BuiltIn isn't reachable outside a running Robot execution
            # (e.g. unit tests) — fall back to tagging the result as
            # SKIP via the v3 result object when possible.
            try:
                result.status = "SKIP"
                result.message = msg
            except Exception:
                pass


def write_quarantine_snapshot(
    output_dir: Path,
    entries: list[dict[str, str]],
) -> Path:
    """Serialise the per-repo quarantine snapshot for the listener to
    read. Called by `execute_test_run` once per run; the file is
    discarded with the rest of `output_dir`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    p = output_dir / "quarantine.json"
    p.write_text(
        json.dumps(
            [
                {
                    "suite_name": e.get("suite_name", ""),
                    "test_name": e.get("test_name", ""),
                    "reason": e.get("reason") or "",
                }
                for e in entries
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p
