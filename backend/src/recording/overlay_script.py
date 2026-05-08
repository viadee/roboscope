"""Story W.4 — DevTools-style hover overlay injected into the Recorder v2
controlled browser.

Follows AR-4 — injected via `page.add_init_script()` so it survives
full-document loads + SPA navigations. Runs inside the same IIFE the
capture script uses; this module ships separately only because tests
want to assert on the overlay surface independently.

Key properties (AC-FR3):
  - semi-transparent highlight around the currently hovered element
    with a 2-px solid border.
  - info label shows tag + leading-class-summary + offsetX/Y + w/h.
  - `pointer-events: none` so the overlay never intercepts clicks.
  - respects `prefers-reduced-motion: reduce` — no transitions.
  - keyboard toggle: Ctrl+Shift+X shows/hides without re-recording.
"""

from __future__ import annotations

OVERLAY_SCRIPT: str = r"""
(() => {
  if (window.__roboscopeOverlayInstalled) return;
  window.__roboscopeOverlayInstalled = true;

  const prefersReducedMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const box = document.createElement("div");
  box.setAttribute("aria-hidden", "true");
  box.style.cssText = [
    "position: fixed",
    "pointer-events: none",
    "z-index: 2147483646",  // max int - 1
    "border: 2px solid rgba(59, 125, 216, 0.9)",
    "background: rgba(59, 125, 216, 0.15)",
    "box-sizing: border-box",
    "display: none",
    prefersReducedMotion ? "transition: none" : "transition: all 30ms linear",
  ].join("; ");

  const label = document.createElement("div");
  label.setAttribute("aria-hidden", "true");
  label.style.cssText = [
    "position: fixed",
    "pointer-events: none",
    "z-index: 2147483647",
    "background: #1a2d50",
    "color: white",
    "font: 11px/1.4 monospace",
    "padding: 3px 6px",
    "border-radius: 3px",
    "display: none",
    "white-space: nowrap",
  ].join("; ");

  function mount() {
    if (!box.parentNode) document.documentElement.appendChild(box);
    if (!label.parentNode) document.documentElement.appendChild(label);
  }

  let visible = true;
  let lastTarget = null;

  function describe(el) {
    const classes = (el.className && typeof el.className === "string")
      ? el.className.split(/\s+/).filter(Boolean).slice(0, 2).map(c => "." + c).join("")
      : "";
    const id = el.id ? "#" + el.id : "";
    return el.tagName.toLowerCase() + id + classes;
  }

  function position(el) {
    const r = el.getBoundingClientRect();
    box.style.left = r.left + "px";
    box.style.top = r.top + "px";
    box.style.width = r.width + "px";
    box.style.height = r.height + "px";
    box.style.display = visible ? "block" : "none";

    label.textContent = `${describe(el)}  ${Math.round(r.width)}×${Math.round(r.height)}`;
    label.style.left = r.left + "px";
    label.style.top = Math.max(0, r.top - 18) + "px";
    label.style.display = visible ? "block" : "none";
  }

  function onMove(ev) {
    mount();
    const el = ev.target;
    if (!(el instanceof Element) || el === lastTarget) return;
    lastTarget = el;
    position(el);
  }

  function hide() {
    box.style.display = "none";
    label.style.display = "none";
  }

  document.addEventListener("mousemove", onMove, true);
  document.addEventListener("mouseout", hide, true);
  window.addEventListener("blur", hide);
  window.addEventListener("scroll", () => { if (lastTarget) position(lastTarget); }, true);

  // Ctrl+Shift+X toggle (AC-FR3 hotkey).
  document.addEventListener("keydown", (ev) => {
    if (ev.ctrlKey && ev.shiftKey && ev.key.toLowerCase() === "x") {
      visible = !visible;
      if (!visible) hide();
      else if (lastTarget) position(lastTarget);
    }
  }, true);
})();
"""


def overlay_script() -> str:
    """Return the overlay IIFE. Shape kept symmetric with capture_script so
    future per-session tweaks are a one-line change."""
    return OVERLAY_SCRIPT
