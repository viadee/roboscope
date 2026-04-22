"""Story W.3 — capture script injected by the Recorder v2 controlled browser.

A single string of JS that Playwright calls `page.add_init_script()` with
on every new document (per AR-4 — init scripts survive SPA navigation).
It listens for the AC-FR2 primitives (click / input / scroll / nav /
drag-drop) and pushes a structured payload back to the backend via a
binding Playwright exposes (`window.__roboscopeCapture(payload)`).

The script is layout-independent: selectors come from a snapshot of
the target element's attributes + ancestor chain, and the backend's
Story S.2 `synthesise_selectors()` does the actual strategy synthesis.

Single source of truth — the JS text is kept in-repo as a Python
multiline string so both runtime + tests read the same bytes.
"""

from __future__ import annotations

CAPTURE_SCRIPT: str = r"""
(() => {
  if (window.__roboscopeCaptureInstalled) return;
  window.__roboscopeCaptureInstalled = true;

  const MAX_TEXT = 60;
  const NAV_DEBOUNCE_MS = 100;
  let lastNavUrl = location.href;

  function send(payload) {
    try {
      if (typeof window.__roboscopeCapture === "function") {
        window.__roboscopeCapture(payload);
      }
    } catch (e) { /* do not ever throw back into the page */ }
  }

  function truncate(s) {
    if (!s) return "";
    const t = String(s).trim();
    return t.length > MAX_TEXT ? t.slice(0, MAX_TEXT - 1) + "…" : t;
  }

  function snapshot(el) {
    if (!el || !(el instanceof Element)) return null;
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    const ancestors = [];
    let p = el.parentElement, depth = 0;
    while (p && depth < 8) {
      const pa = {};
      for (const a of p.attributes) pa[a.name] = a.value;
      ancestors.push({ tag: p.tagName.toLowerCase(), attributes: pa });
      p = p.parentElement;
      depth += 1;
    }
    return {
      tag: el.tagName.toLowerCase(),
      attributes: attrs,
      text: truncate(el.textContent || ""),
      aria_role: el.getAttribute("role") || el.role || null,
      aria_name:
        el.getAttribute("aria-label") ||
        el.getAttribute("aria-labelledby") ||
        null,
      ancestors,
    };
  }

  // ---- click / dblclick ---------------------------------------------------
  document.addEventListener("click", (ev) => {
    send({
      kind: "click",
      element: snapshot(ev.target),
      modifiers: {
        ctrlKey: ev.ctrlKey, shiftKey: ev.shiftKey, altKey: ev.altKey,
      },
    });
  }, true);

  document.addEventListener("dblclick", (ev) => {
    send({ kind: "dblclick", element: snapshot(ev.target) });
  }, true);

  // ---- text input (commits on change, not every keystroke) ---------------
  document.addEventListener("change", (ev) => {
    const el = ev.target;
    if (!el || !(el instanceof HTMLElement)) return;
    const isText =
      (el instanceof HTMLInputElement &&
        ["text", "email", "password", "search", "tel", "url", "number"].includes(el.type)) ||
      el instanceof HTMLTextAreaElement ||
      el.isContentEditable;
    if (!isText) return;
    send({
      kind: "type",
      element: snapshot(el),
      text: truncate(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement ? el.value : el.textContent),
    });
  }, true);

  // ---- Enter keypress — surface explicitly as a submit-y signal ---------
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter") return;
    send({
      kind: "press",
      element: snapshot(ev.target),
      key: "Enter",
    });
  }, true);

  // ---- scroll (debounced; coarse page vs. container differentiation) ----
  let scrollTimer = null;
  let scrollTarget = null;
  document.addEventListener("scroll", (ev) => {
    scrollTarget = ev.target;
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      send({
        kind: "scroll",
        element: scrollTarget === document ? null : snapshot(scrollTarget),
        scroll_y:
          (scrollTarget && scrollTarget !== document && scrollTarget.scrollTop != null)
            ? scrollTarget.scrollTop
            : window.scrollY,
      });
    }, 200);
  }, true);

  // ---- drag-and-drop (paired events → one command) ----------------------
  let dragFrom = null;
  document.addEventListener("dragstart", (ev) => {
    dragFrom = snapshot(ev.target);
  }, true);
  document.addEventListener("drop", (ev) => {
    const dragTo = snapshot(ev.target);
    if (dragFrom) {
      send({ kind: "drag_drop", from: dragFrom, to: dragTo });
      dragFrom = null;
    }
  }, true);

  // ---- navigation (SPA pushState + popstate + full loads) ---------------
  function maybeEmitNav(source) {
    const now = location.href;
    if (now === lastNavUrl) return;
    lastNavUrl = now;
    send({ kind: "navigate", url: now, source });
  }

  // Full-document load — init script runs on EVERY new document, so firing
  // once here captures the address-bar navigation the user performed.
  setTimeout(() => maybeEmitNav("load"), NAV_DEBOUNCE_MS);

  // SPA routing.
  const origPush = history.pushState;
  const origReplace = history.replaceState;
  history.pushState = function (...args) {
    const rv = origPush.apply(this, args);
    maybeEmitNav("pushState");
    return rv;
  };
  history.replaceState = function (...args) {
    const rv = origReplace.apply(this, args);
    maybeEmitNav("replaceState");
    return rv;
  };
  window.addEventListener("popstate", () => maybeEmitNav("popstate"));
})();
"""


def capture_script_for_session(session_id: int) -> str:
    """Return the capture script text to hand to Playwright for this session.

    The session id is not templated in today — the binding is session-scoped
    on the Python side. This helper exists so future per-session tweaks
    (e.g., feature flags) have a natural extension point.
    """
    del session_id  # reserved for future use
    return CAPTURE_SCRIPT


# Event kinds the script emits. Tests use this to pin the surface area
# so accidentally dropping an event handler breaks the build.
EMITTED_KINDS: tuple[str, ...] = (
    "click",
    "dblclick",
    "type",
    "press",
    "scroll",
    "drag_drop",
    "navigate",
)
