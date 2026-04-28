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

  // RECORDER-1A v2: `add_init_script` runs in EVERY document — including
  // every iframe (ads, embedded video players, OAuth widgets). Capturing
  // events from those frames pollutes the recording with URLs and clicks
  // the user never made. Restrict the entire capture to the top frame.
  // (iframe support requires RF Browser's `frame=` selector dialect and
  // is a separate story when the need arises.)
  let isTopFrame = true;
  try { isTopFrame = window.top === window; } catch (e) { /* cross-origin parent → treat as iframe */ isTopFrame = false; }
  if (!isTopFrame) return;

  const MAX_TEXT = 60;
  const NAV_DEBOUNCE_MS = 100;
  // RECORDER-1A: start as empty so the first `maybeEmitNav("load")` call
  // ALWAYS emits — the init script re-runs on every new document, so a
  // full-page navigation (link click, address-bar entry, popup open)
  // gets a fresh script with `lastNavUrl=""`. Comparing against
  // `location.href` would silently skip the emission, which is exactly
  // the bug we're fixing.
  let lastNavUrl = "";

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
  // RECORDER-1B: stash the click timestamp so the post-navigation
  // `maybeEmitNav("load")` in the *next* document can suppress its
  // emission (the click already implies the navigation; recording both
  // would replay as Click → page navigates → Go To explicit re-nav,
  // wiping any state set by the click).
  const CLICK_NAV_KEY = "__roboscopeLastClickAt";
  function markClickForNavSuppress() {
    try { sessionStorage.setItem(CLICK_NAV_KEY, String(Date.now())); } catch (e) { /* noop */ }
  }
  document.addEventListener("click", (ev) => {
    send({
      kind: "click",
      element: snapshot(ev.target),
      modifiers: {
        ctrlKey: ev.ctrlKey, shiftKey: ev.shiftKey, altKey: ev.altKey,
      },
    });
    markClickForNavSuppress();
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
  // RECORDER-1B: window in which a `load` is treated as click-caused
  // and skipped. Browsers schedule the new-document parse a few hundred
  // ms after the click; 1500ms is generous enough to handle slow
  // app-server round-trips without swallowing genuine user-typed URLs.
  const CLICK_NAV_WINDOW_MS = 1500;

  function maybeEmitNav(source) {
    const now = location.href;
    if (now === lastNavUrl) return;
    // Placeholder URLs that browsers / Playwright use as the "no real
    // page yet" sentinel. A new context's first page starts here before
    // the user (or test) navigates anywhere — recording it would surface
    // a useless `Go To about:blank` as the test's very first step.
    if (now === "about:blank" || now.startsWith("about:") || now.startsWith("chrome:") || now.startsWith("data:")) {
      lastNavUrl = now;
      return;
    }
    if (source === "load") {
      // Suppress when the navigation is the consequence of a click that
      // we already recorded — the click implies the navigation, and a
      // Go To on top would re-navigate explicitly on replay (wiping
      // state the click set).
      try {
        const ts = parseInt(sessionStorage.getItem(CLICK_NAV_KEY) || "0", 10);
        if (ts && Date.now() - ts < CLICK_NAV_WINDOW_MS) {
          sessionStorage.removeItem(CLICK_NAV_KEY);
          lastNavUrl = now;
          return;
        }
      } catch (e) { /* sessionStorage unavailable — emit anyway */ }
    }
    lastNavUrl = now;
    send({ kind: "navigate", url: now, source });
  }

  // Full-document load — init script runs on EVERY new document, so firing
  // once here captures the address-bar navigation the user performed.
  // We emit *synchronously* AND on the debounce tick: the synchronous
  // call wins for fast back-to-back navigations (Playwright auto-wait
  // could fire the next click before a 100ms timeout elapses, and the
  // unfired timeout dies with the document); the timeout is the safety
  // net for races where `location.href` settles after document-start.
  maybeEmitNav("load");
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
