"""Story W.5 — right-click context menu for keyword-family additions.

When the user right-clicks inside the controlled Recorder browser, we
suppress the native menu and render an in-page menu organised by AR-6
keyword families (Assert/Read, Wait, Interact, State). Picking an item
emits a `custom_action` event carrying the keyword name + optional arg
prompt; the Python layer maps it to a RecordedCommand and enqueues it.

Keyword names are Robot-Framework-English literals (not localised);
only the group headings are candidates for i18n in a follow-up.
"""

from __future__ import annotations

import json

KEYWORD_CATALOG: dict[str, list[dict[str, str]]] = {
    "Assert / Read": [
        {"keyword": "Get Element Value", "arg_prompt": None},
        {"keyword": "Get Text", "arg_prompt": None},
        {"keyword": "Get Attribute", "arg_prompt": "attribute name (e.g. href)"},
        {"keyword": "Should Be Equal", "arg_prompt": "expected value"},
        {"keyword": "Should Contain", "arg_prompt": "expected substring"},
    ],
    "Wait": [
        {"keyword": "Wait For Elements State", "arg_prompt": "state (visible / hidden / attached / ...)"},
        {"keyword": "Wait Until Network Is Idle", "arg_prompt": None},
        {"keyword": "Wait For Condition", "arg_prompt": "condition expression"},
    ],
    "Interact": [
        {"keyword": "Double Click", "arg_prompt": None},
        {"keyword": "Hover", "arg_prompt": None},
        {"keyword": "Focus", "arg_prompt": None},
        {"keyword": "Press Keys", "arg_prompt": "key(s) — e.g. Enter, Ctrl+A"},
    ],
    "State": [
        {"keyword": "Scroll To Element", "arg_prompt": None},
        {"keyword": "Take Screenshot", "arg_prompt": None},
        {"keyword": "Highlight Elements", "arg_prompt": None},
    ],
}


def _catalog_as_js() -> str:
    return json.dumps(KEYWORD_CATALOG)


CONTEXT_MENU_SCRIPT: str = (
    r"""
(() => {
  if (window.__roboscopeContextMenuInstalled) return;
  window.__roboscopeContextMenuInstalled = true;

  const CATALOG = """
    + _catalog_as_js()
    + r""";

  const menu = document.createElement("div");
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "RoboScope Recorder actions");
  menu.style.cssText = [
    "position: fixed",
    "min-width: 240px",
    "background: white",
    "border: 1px solid #ddd",
    "border-radius: 4px",
    "box-shadow: 0 4px 16px rgba(0,0,0,.12)",
    "border-left: 4px solid #D4883E",
    "z-index: 2147483647",
    "font: 13px/1.4 -apple-system, Segoe UI, sans-serif",
    "color: #1A2D50",
    "padding: 4px 0",
    "display: none",
  ].join("; ");
  document.documentElement.appendChild(menu);

  let lastTarget = null;

  function hide() {
    menu.style.display = "none";
  }

  function emit(keyword, argPrompt) {
    let value = null;
    if (argPrompt) {
      value = window.prompt(`${keyword} — ${argPrompt}`, "");
      if (value === null) return;  // user cancelled
    }
    try {
      if (typeof window.__roboscopeCapture === "function") {
        window.__roboscopeCapture({
          kind: "custom_action",
          keyword,
          args: value !== null && value !== "" ? { value } : {},
          element: (lastTarget instanceof Element) ? lastTarget.__rsSnapshot || null : null,
        });
      }
    } catch (e) { /* never throw into the page */ }
  }

  function build(target) {
    menu.innerHTML = "";
    lastTarget = target;

    for (const groupName of Object.keys(CATALOG)) {
      const header = document.createElement("div");
      header.textContent = groupName;
      header.style.cssText = [
        "padding: 4px 10px",
        "color: #666",
        "font-size: 11px",
        "text-transform: uppercase",
        "letter-spacing: 0.04em",
      ].join("; ");
      menu.appendChild(header);

      for (const item of CATALOG[groupName]) {
        const row = document.createElement("div");
        row.setAttribute("role", "menuitem");
        row.tabIndex = -1;
        row.textContent = item.keyword;
        row.style.cssText = [
          "padding: 5px 14px",
          "cursor: pointer",
        ].join("; ");
        row.addEventListener("mouseenter", () => {
          row.style.background = "rgba(59, 125, 216, 0.12)";
        });
        row.addEventListener("mouseleave", () => {
          row.style.background = "transparent";
        });
        row.addEventListener("click", () => {
          hide();
          emit(item.keyword, item.arg_prompt);
        });
        menu.appendChild(row);
      }

      const sep = document.createElement("div");
      sep.style.cssText = "height: 1px; background: #eee; margin: 4px 0";
      menu.appendChild(sep);
    }
  }

  document.addEventListener("contextmenu", (ev) => {
    if (!(ev.target instanceof Element)) return;
    ev.preventDefault();
    build(ev.target);
    const vw = window.innerWidth, vh = window.innerHeight;
    const mw = 240, mh = 360;  // conservative estimate for first paint
    menu.style.left = Math.min(ev.clientX, vw - mw - 8) + "px";
    menu.style.top = Math.min(ev.clientY, vh - mh - 8) + "px";
    menu.style.display = "block";
  }, true);

  document.addEventListener("click", (ev) => {
    if (!menu.contains(ev.target)) hide();
  }, true);

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") hide();
  }, true);
})();
"""
)


def context_menu_script() -> str:
    return CONTEXT_MENU_SCRIPT


def keyword_catalog() -> dict[str, list[dict[str, str]]]:
    """Returned for backend tests that want to validate the emitted
    keyword is in the catalog (guards against typos in the menu list).
    """
    return KEYWORD_CATALOG
