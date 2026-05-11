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

  // RECORDER-FRAMES — `add_init_script` runs in every document including
  // iframes. The original v2 design aborted in non-top frames to keep
  // ad/tracker iframes from polluting the recording, but that also
  // meant Sourcepoint / OneTrust / TCF consent banners (which are
  // virtually always in cross-origin iframes) were silently dropped —
  // a real recording on heise.de produced a flow with the cookie
  // accept missing. Now we ALWAYS run, and tag every payload with the
  // originating `frame_url`. The backend treats the top frame as
  // "default" (no frame qualifier in the emitted Click) and any other
  // frame as a composite-locator target (`iframe[src*="..."] >>> sel`).
  // Suppression of ad-iframe noise happens server-side now, with the
  // benefit of context — see translate_payload's frame allow-list.
  let isTopFrame = true;
  try { isTopFrame = window.top === window; } catch (e) { /* cross-origin parent → treat as iframe */ isTopFrame = false; }

  // Capture phase fires before the page's own click handlers, so even
  // a banner that calls stopPropagation never silences us. The binding
  // is exposed on the BrowserContext, which Playwright propagates to
  // every frame in every page.

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
      // Tag every payload with the frame URL it came from. Top-frame
      // payloads carry the page URL; iframe payloads carry the iframe
      // document URL. Empty for `about:blank` etc.
      payload.frame_url = location.href;
      payload.is_top_frame = isTopFrame;
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

  // SHADOW-DOM — `parentElement` returns null at a shadow root boundary,
  // so a naïve walk would stop at the deepest open shadow root and miss
  // the host's ancestors entirely. `crossShadow(el)` jumps from a node
  // whose `parentElement` is null to the host (`getRootNode().host`)
  // when the root is a ShadowRoot, otherwise returns null. Closed
  // shadow roots are still opaque to userspace JS — those will surface
  // a `null` parentNode and we stop, same as before.
  function crossShadow(el) {
    if (!el) return null;
    if (el.parentElement) return el.parentElement;
    const root = el.getRootNode && el.getRootNode();
    if (root && root.host && root.host !== el) return root.host;
    return null;
  }

  function snapshot(el) {
    if (!el || !(el instanceof Element)) return null;
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    const ancestors = [];
    let p = crossShadow(el), depth = 0;
    let crossedShadow = false;
    while (p && depth < 12) {
      const pa = {};
      for (const a of p.attributes) pa[a.name] = a.value;
      // Mark the ancestor as a shadow host iff its `shadowRoot` contains
      // (or transitively contains) the element we just came from. The
      // backend uses this to emit a `>>` chained Playwright locator that
      // pierces shadow boundaries explicitly when needed.
      const isShadowHost = !!(p.shadowRoot);
      ancestors.push({
        tag: p.tagName.toLowerCase(),
        attributes: pa,
        is_shadow_host: isShadowHost || undefined,
      });
      if (isShadowHost) crossedShadow = true;
      p = crossShadow(p);
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
      // True iff the captured element lives inside one or more open
      // shadow roots. Used by the synthesis layer to prefer pierce-
      // friendly selector strategies (testid / aria, which Playwright
      // resolves through open shadow boundaries by default) over raw
      // CSS that may match the wrong element across the boundary.
      in_shadow_dom: crossedShadow || (el.getRootNode() instanceof ShadowRoot),
    };
  }

  // SHADOW-DOM target retargeting: an event fired inside an open shadow
  // root surfaces with `ev.target` pointing at the *host* in the light
  // DOM, NOT the actually-clicked element. `composedPath()[0]` is the
  // deepest, true target. We keep the original `ev.target` as a
  // fallback when composedPath is empty (closed shadow roots, very old
  // browsers, or synthetic events with no path).
  function realTarget(ev) {
    try {
      const path = ev.composedPath && ev.composedPath();
      if (path && path.length > 0 && path[0] instanceof Element) {
        return path[0];
      }
    } catch (_) { /* fallthrough to ev.target */ }
    return ev.target;
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
      element: snapshot(realTarget(ev)),
      modifiers: {
        ctrlKey: ev.ctrlKey, shiftKey: ev.shiftKey, altKey: ev.altKey,
      },
    });
    markClickForNavSuppress();
  }, true);

  document.addEventListener("dblclick", (ev) => {
    send({ kind: "dblclick", element: snapshot(realTarget(ev)) });
  }, true);

  // ---- text input (commits on change, not every keystroke) ---------------
  document.addEventListener("change", (ev) => {
    const el = realTarget(ev);
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
      element: snapshot(realTarget(ev)),
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
    dragFrom = snapshot(realTarget(ev));
  }, true);
  document.addEventListener("drop", (ev) => {
    const dragTo = snapshot(realTarget(ev));
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
    // RECORDER-FRAMES — iframe documents navigate independently
    // (consent flow internal redirects, ad-frame document swaps,
    // OAuth pop-ups inside iframes). None of those are user-meaningful
    // page navigations; emitting `Go To <iframe-url>` from them would
    // pollute the recording with URLs the user never typed. Only the
    // top frame contributes navigation events.
    if (!isTopFrame) return;
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

  // RECORDER-FRAMES-2 — proactive iframe inventory (top-frame only).
  // The capture script in the iframe document can't see the iframe
  // element it lives inside. The top-frame script can. We enumerate
  // iframes once the DOM is ready, synthesise candidate selectors
  // per iframe, count matches synchronously, and post the result so
  // the backend has the iframe's id/name/testid before any user
  // click possibly detaches it.
  if (isTopFrame) {
    function _registerIframesOnce() {
      var iframes = document.querySelectorAll("iframe");
      for (var i = 0; i < iframes.length; i++) {
        var iframe = iframes[i];
        var src = iframe.getAttribute("src") || "";
        var id = iframe.id || "";
        var name = iframe.name || "";
        var testid = iframe.getAttribute("data-testid") || "";
        var classes = [];
        try { classes = Array.prototype.slice.call(iframe.classList); }
        catch (e) { classes = []; }
        function countSel(sel) {
          try { return document.querySelectorAll(sel).length; }
          catch (e) { return 0; }
        }
        var cands = [];
        if (testid) {
          var v1 = 'iframe[data-testid="' + testid + '"]';
          cands.push({ strategy: "testid", value: v1, quality_score: 95, count: countSel(v1) });
        }
        if (id) {
          var v2 = "iframe#" + id;
          cands.push({ strategy: "css", value: v2, quality_score: 90, count: countSel(v2) });
        }
        if (name) {
          var v3 = 'iframe[name="' + name + '"]';
          cands.push({ strategy: "css", value: v3, quality_score: 85, count: countSel(v3) });
        }
        if (src) {
          var v4 = 'iframe[src="' + src + '"]';
          cands.push({ strategy: "css", value: v4, quality_score: 75, count: countSel(v4) });
        }
        send({
          kind: "iframe_register",
          iframe_src: src,
          iframe_id: id,
          iframe_name: name,
          iframe_testid: testid,
          iframe_classes: classes,
          candidates: cands,
        });
      }
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", _registerIframesOnce);
    } else {
      _registerIframesOnce();
    }
  }
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
