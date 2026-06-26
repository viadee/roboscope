"""Story D-5 — Windows-only low-level input capture for the desktop recorder.

Installs WH_MOUSE_LL + WH_KEYBOARD_LL hooks (pure `ctypes`, no extra dependency
for the hook layer) on a dedicated pump thread, and exposes a generator that
yields `RawMouse` / `RawKey` events with the UIA element already resolved.

Design (see `recorder-desktop-architecture.md` §3.1):

  - **Pump thread** — owns the hooks + a `GetMessage` loop. LL hook callbacks
    must return fast, so they only translate the keystroke and push a tiny
    tuple onto a queue; no UIA work happens in the callback.
  - **Generator (caller thread)** — drains the queue, does the *expensive* UIA
    resolution (`ElementFromPoint` / focused element via pywinauto), debounces
    double-clicks, and yields `RawMouse` / `RawKey`.

This module is imported ONLY inside the Windows branch of
`desktop_recorder_task._desktop_loop`; it is never imported on macOS / Linux.

The pywinauto resolution calls are each wrapped in try/except — a failure to
resolve one element skips that single event rather than crashing the session.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
from collections import deque
from typing import Iterator

from src.recording.desktop_capture import RawKey, RawMouse, extract_snapshot

logger = logging.getLogger("roboscope.recording.win32_input")


def pywinauto_available() -> bool:
    """Cheap, side-effect-free probe: is the Windows-optional dependency
    importable? Used by the capabilities endpoint so the launcher can
    DISABLE the Windows-desktop transport (instead of offering it and
    letting the background recorder task crash straight to "beendet"
    with the real cause buried in the backend log). Uses
    `importlib.util.find_spec` so we don't pay pywinauto's import cost
    on every capability poll.
    """
    import importlib.util

    return importlib.util.find_spec("pywinauto") is not None


def _require_pywinauto() -> None:
    """Fail loud + helpful if the Windows-optional dependency is missing."""
    try:
        import pywinauto  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only on Windows
        raise RuntimeError(
            "pywinauto is not installed; install the Windows extra "
            "(`pip install 'roboscope[windows]'` or add pywinauto to the env) "
            "before dispatching the desktop recorder"
        ) from exc


# ---------------------------------------------------------------------------
# UIA element resolution (pywinauto). Each guarded — returns None on failure.
# ---------------------------------------------------------------------------


def _snapshot_from_point(x: int, y: int) -> dict | None:  # pragma: no cover - Windows-only
    try:
        from pywinauto.uia_element_info import UIAElementInfo

        info = UIAElementInfo.from_point(x, y)
    except Exception:
        logger.debug("ElementFromPoint failed at (%d, %d)", x, y, exc_info=True)
        return None
    if info is None:
        return None
    try:
        return extract_snapshot(info)
    except Exception:
        logger.debug("extract_snapshot failed for point element", exc_info=True)
        return None


def _focused_snapshot() -> dict | None:  # pragma: no cover - Windows-only
    try:
        from pywinauto.uia_defines import IUIA
        from pywinauto.uia_element_info import UIAElementInfo

        raw = IUIA().iuia.GetFocusedElement()
        if raw is None:
            return None
        return extract_snapshot(UIAElementInfo(raw))
    except Exception:
        logger.debug("GetFocusedElement failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Pump thread — installs the hooks, translates keys, pushes raw tuples.
# ---------------------------------------------------------------------------


def _run_pump(  # pragma: no cover - Windows-only message loop
    raw_queue: "queue.SimpleQueue",
    stop_event: threading.Event,
    tid_box: dict,
    ready: threading.Event,
) -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WH_MOUSE_LL = 14
    WH_KEYBOARD_LL = 13
    HC_ACTION = 0
    WM_LBUTTONUP = 0x0202
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104

    ULONG_PTR = ctypes.c_size_t
    LRESULT = ctypes.c_ssize_t

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    HOOKPROC = ctypes.WINFUNCTYPE(
        LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    )

    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
    ]
    user32.CallNextHookEx.restype = LRESULT
    user32.CallNextHookEx.argtypes = [
        wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
    ]
    user32.ToUnicode.argtypes = [
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_wchar_p, ctypes.c_int, wintypes.UINT,
    ]

    def _vk_to_char(vk: int, scan: int) -> str:
        state = (ctypes.c_ubyte * 256)()
        if not user32.GetKeyboardState(ctypes.byref(state)):
            return ""
        buf = ctypes.create_unicode_buffer(8)
        n = user32.ToUnicode(vk, scan, state, buf, len(buf) - 1, 0)
        if n <= 0:
            return ""
        # Keep printable characters only — drop \r / \t / \x08 control chars so
        # buffered Type Text stays clean.
        return "".join(ch for ch in buf.value[:n] if ch.isprintable())

    @HOOKPROC
    def mouse_proc(n_code, w_param, l_param):
        if n_code == HC_ACTION and w_param == WM_LBUTTONUP:
            try:
                ms = ctypes.cast(
                    l_param, ctypes.POINTER(MSLLHOOKSTRUCT)
                ).contents
                raw_queue.put(("mouse", int(ms.pt.x), int(ms.pt.y), int(ms.time)))
            except Exception:
                pass
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    @HOOKPROC
    def kbd_proc(n_code, w_param, l_param):
        if n_code == HC_ACTION and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            try:
                kb = ctypes.cast(
                    l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)
                ).contents
                ch = _vk_to_char(int(kb.vkCode), int(kb.scanCode))
                if ch:
                    raw_queue.put(("key", ch))
            except Exception:
                pass
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    tid_box["tid"] = kernel32.GetCurrentThreadId()
    mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, mouse_proc, None, 0)
    kbd_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, kbd_proc, None, 0)
    # Keep callback refs alive for the lifetime of the loop (GC guard).
    tid_box["_procs"] = (mouse_proc, kbd_proc)
    ready.set()

    if not mouse_hook and not kbd_hook:
        logger.error("failed to install any Win32 input hook")
        return

    msg = wintypes.MSG()
    try:
        while not stop_event.is_set():
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res in (0, -1):  # WM_QUIT or error
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        if mouse_hook:
            user32.UnhookWindowsHookEx(mouse_hook)
        if kbd_hook:
            user32.UnhookWindowsHookEx(kbd_hook)


# ---------------------------------------------------------------------------
# Public generator — the `event_source` consumed by pump_raw_events.
# ---------------------------------------------------------------------------


def windows_event_source(
    stop_event: threading.Event,
) -> Iterator[RawMouse | RawKey]:
    """Yield desktop input events until `stop_event` is set. Windows-only.

    Double-clicks are debounced here (the OS layer owns the WM tick clock):
    a left-up is held for up to `GetDoubleClickTime()` to see whether a second
    left-up lands within the system double-click rectangle; if so a single
    `RawMouse(double=True)` is emitted instead of two clicks.
    """
    if not sys.platform.startswith("win"):  # defensive — caller already gates
        return

    _require_pywinauto()

    import ctypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    SM_CXDOUBLECLK = 36
    SM_CYDOUBLECLK = 37
    WM_QUIT = 0x0012

    dclick_ms = int(user32.GetDoubleClickTime()) or 500
    cx = int(user32.GetSystemMetrics(SM_CXDOUBLECLK)) or 4
    cy = int(user32.GetSystemMetrics(SM_CYDOUBLECLK)) or 4

    raw_queue: "queue.SimpleQueue" = queue.SimpleQueue()
    tid_box: dict = {}
    ready = threading.Event()
    pump = threading.Thread(
        target=_run_pump,
        args=(raw_queue, stop_event, tid_box, ready),
        name="desktop-recorder-pump",
        daemon=True,
    )
    pump.start()
    ready.wait(timeout=5)

    lookahead: deque = deque()

    def _next(timeout: float):
        if lookahead:
            return lookahead.popleft()
        try:
            return raw_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    try:
        while not stop_event.is_set():
            item = _next(0.1)
            if item is None:
                continue

            if item[0] == "mouse":
                _, x, y, _t = item
                double = False
                nxt = _next(dclick_ms / 1000.0)
                if nxt is not None:
                    if (
                        nxt[0] == "mouse"
                        and abs(nxt[1] - x) <= cx
                        and abs(nxt[2] - y) <= cy
                    ):
                        double = True
                    else:
                        lookahead.append(nxt)  # not a double — process it next
                snap = _snapshot_from_point(x, y)
                if snap is not None:
                    yield RawMouse(snapshot=snap, double=double)

            elif item[0] == "key":
                _, ch = item
                snap = _focused_snapshot()
                yield RawKey(char=ch, snapshot=snap)
    finally:
        tid = tid_box.get("tid")
        if tid:
            try:
                user32.PostThreadMessageW(int(tid), WM_QUIT, 0, 0)
            except Exception:
                pass
        pump.join(timeout=2)
