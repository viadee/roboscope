"""Story D-5 — pure capture logic for the Windows desktop recorder.

This module is **OS-free** so the full classification pipeline runs in unit
tests on any host (macOS / Linux dev boxes + CI). The Windows-only glue
(`win32_input.py`) installs the low-level hooks, resolves UIA elements, and
feeds the raw events produced here through `pump_raw_events`.

Pipeline (see `recorder-desktop-architecture.md` §3):

    Win32 LL hook  →  RawMouse / RawKey / RawFocus  (element already resolved
                                                      to a snapshot dict)
                   →  DesktopEventAccumulator        (buffers typed text,
                                                      coalesces, classifies)
                   →  translator payload dict        ({kind, element, text|value})
                   →  translate_uia_event()          (RecordedCommand)

The accumulator owns NO timing and NO threads — double-click detection lives in
the OS layer (which has the WM tick timestamps) and arrives here as a flag.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, runtime_checkable

# Payload dict produced for the translator. Kept as a plain dict (not a model)
# to match `translate_uia_event`'s existing contract.
Payload = dict[str, Any]
ElementSnapshot = dict[str, Any]


@runtime_checkable
class ElementInfoLike(Protocol):
    """Structural type for a UIA element wrapper (e.g. pywinauto's
    ``UIAElementInfo``). Only the attributes `extract_snapshot` reads are
    declared; the OS layer passes the real thing, tests pass a fake."""

    control_type: str
    automation_id: str | None
    name: str | None
    class_name: str | None
    # pywinauto exposes `parent` as a property returning an info or None;
    # `extract_snapshot` also tolerates a `parent()` callable for fakes.
    parent: "ElementInfoLike | None"


def _clean(value: Any) -> str | None:
    """Normalise a UIA string property: strip, empty → None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_parent(info: Any) -> Any | None:
    """Return the parent of a UIA element wrapper, tolerating both the
    property form (`info.parent`) and the callable form (`info.parent()`)."""
    parent = getattr(info, "parent", None)
    if callable(parent):
        try:
            return parent()
        except Exception:
            return None
    return parent


def extract_snapshot(info: Any, max_ancestors: int = 8) -> ElementSnapshot:
    """Build the translator's element snapshot dict from a UIA element wrapper.

    Walks up the ancestor chain (capped at `max_ancestors` to bound payload
    size and guard against pathological / cyclic trees). The shape matches
    `desktop_recorder_task._element_from_uia_payload`:

        {control_type, automation_id, name, class_name,
         ancestors: [{control_type, automation_id, name}, ...]}
    """
    snapshot: ElementSnapshot = {
        "control_type": str(getattr(info, "control_type", "") or ""),
        "automation_id": _clean(getattr(info, "automation_id", None)),
        "name": _clean(getattr(info, "name", None)),
        "class_name": _clean(getattr(info, "class_name", None)),
    }

    ancestors: list[dict[str, Any]] = []
    seen: set[int] = {id(info)}
    parent = _resolve_parent(info)
    depth = 0
    while parent is not None and depth < max_ancestors:
        # Cycle / self-parent guard (UIA roots sometimes report themselves).
        if id(parent) in seen:
            break
        seen.add(id(parent))
        ancestors.append(
            {
                "control_type": str(getattr(parent, "control_type", "") or ""),
                "automation_id": _clean(getattr(parent, "automation_id", None)),
                "name": _clean(getattr(parent, "name", None)),
            }
        )
        parent = _resolve_parent(parent)
        depth += 1

    snapshot["ancestors"] = ancestors
    return snapshot


# ---------------------------------------------------------------------------
# Raw events — emitted by the OS layer, consumed by the accumulator.
# ---------------------------------------------------------------------------


@dataclass
class RawMouse:
    """A committed left-button mouse interaction with its resolved element."""

    snapshot: ElementSnapshot
    double: bool = False


@dataclass
class RawKey:
    """One printable character typed. `snapshot` is the focused element at
    key time — only the FIRST key of a typing run needs to carry it (the
    accumulator latches it), but the OS layer may set it on every key."""

    char: str
    snapshot: ElementSnapshot | None = None


@dataclass
class RawFocus:
    """The active top-level window changed."""

    snapshot: ElementSnapshot


RawEvent = RawMouse | RawKey | RawFocus


def _ancestor_has_control_type(snapshot: ElementSnapshot, control_type: str) -> bool:
    return any(
        a.get("control_type") == control_type
        for a in snapshot.get("ancestors", [])
    )


class DesktopEventAccumulator:
    """Stateful, pure classifier from raw events to translator payloads.

    Responsibilities:
      - Buffer consecutive printable keystrokes into ONE `Type Text` payload,
        flushed when focus changes, a click occurs, or the session stops.
      - Coalesce a double-click (the OS layer sets `RawMouse.double`).
      - Classify a click into `combobox_select` / `menu_select` / `click`.
      - Emit `window_focus` on active-window changes.

    `feed()` and `flush()` return a list of payloads (possibly empty) so the
    whole thing is trivially unit-testable with no I/O.
    """

    def __init__(self) -> None:
        self._buf: list[str] = []
        self._buf_el: ElementSnapshot | None = None

    def feed(self, event: RawEvent) -> list[Payload]:
        out: list[Payload] = []

        if isinstance(event, RawKey):
            if event.char:
                if not self._buf:
                    self._buf_el = event.snapshot
                self._buf.append(event.char)
            return out

        # Any non-key event commits pending typed text first so ordering is
        # "type then click" / "type then focus-change".
        out.extend(self._flush())

        if isinstance(event, RawMouse):
            out.append(self._classify_mouse(event))
        elif isinstance(event, RawFocus):
            out.append({"kind": "window_focus", "element": event.snapshot})

        return out

    def flush(self) -> list[Payload]:
        """Commit any buffered text — call at session stop."""
        return self._flush()

    def _flush(self) -> list[Payload]:
        payloads: list[Payload] = []
        if self._buf and self._buf_el is not None:
            payloads.append(
                {
                    "kind": "type",
                    "element": self._buf_el,
                    "text": "".join(self._buf),
                }
            )
        self._buf = []
        self._buf_el = None
        return payloads

    def _classify_mouse(self, event: RawMouse) -> Payload:
        snap = event.snapshot
        control_type = snap.get("control_type", "")

        if event.double:
            return {"kind": "dblclick", "element": snap}
        if control_type == "ListItem" and _ancestor_has_control_type(snap, "ComboBox"):
            return {
                "kind": "combobox_select",
                "element": snap,
                "value": snap.get("name") or "",
            }
        if control_type == "MenuItem":
            return {
                "kind": "menu_select",
                "element": snap,
                "value": snap.get("name") or "",
            }
        return {"kind": "click", "element": snap}


def pump_raw_events(
    events: Iterable[RawEvent],
    emit: Callable[[Payload], None],
    stop_event: "threading.Event | None" = None,
) -> None:
    """Drain a raw-event iterator through the accumulator into `emit`.

    `emit(payload)` is responsible for translating the payload into a
    `RecordedCommand` and enqueueing it (the desktop task supplies a closure
    that owns the running command index). This function is the deterministic
    test seam: feed it a fake iterator of raw events and assert on `emit`
    calls — no OS, no threads required.
    """
    acc = DesktopEventAccumulator()
    for event in events:
        if stop_event is not None and stop_event.is_set():
            break
        for payload in acc.feed(event):
            emit(payload)
    for payload in acc.flush():
        emit(payload)
