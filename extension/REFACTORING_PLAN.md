# Refactoring Plan — RobotFramework Recorder

> Generated 2026-02-12. Based on full source analysis of all files in `src/`, `test/`, config, and assets.

---

## 1. Code Quality Issues

### 1.1 Dead Code
- **`src/popup.js:16-30`** — Commented-out Google Analytics block (`gaAccount`, `_gaq`). The `analytics()` function on line 32 is a no-op stub. Remove both entirely.
- **`src/popup.js:34`** — `analytics()` is called in 5 places but does nothing. Remove all call sites.
- **`src/content.js:8-17`** — Large commented-out `MutationObserver` block. Either implement or remove.
- **`src/background.js:8`** — `tab` is imported from constants but shadowed by the destructured `const [tab]` on line 72. The import is unused.
- **`src/background.js:7`** — `url` import is only used in the `info` operation (line 168) — consider inlining.
- **`src/background.js:14`** — `maxLength = 5000` is passed as the `length` parameter but `generateOutput` just uses it as a cap on list iteration. The name is misleading — it's max *actions*, not max *length*.
- **`src/background.js:4`** — `/* global instruction filename statusMessage url tab logo initializeTranslator */` lists globals that are now ES module imports. Remove the comment.
- **`src/popup.js:1`** — `/* global document chrome IntroTour t getCurrentLanguage setLanguage */` — `IntroTour` is loaded via `<script>` tag, and `t`/`getCurrentLanguage`/`setLanguage` are set on `window` by `translations.js`. These should be proper imports instead.
- **`src/constants.js:18`** — `statusMessage` is missing `failedScan` and `failedRecord` keys, yet `background.js` references `statusMessage.failedScan` (line 123) and `statusMessage.failedRecord` (line 138). These resolve to `undefined`.
- **`src/intro.js:197-199`** — `if (typeof exports !== 'undefined') exports.IntroTour = IntroTour;` — IntroTour is never imported as a module; it's loaded as a global script. This dual-export pattern is inconsistent.

### 1.2 Duplication
- **Port-closed error handling** — The pattern checking `portClosedPatterns` is duplicated verbatim 3 times in `popup.js` (lines ~258, ~278, ~305). Extract to a helper like `isPortClosedError(err)`.
- **`runtimeSendMessage` with retry** (`popup.js:230-250`) wraps `chrome.runtime.sendMessage` but `background.js` has its own `contentSendMessage` (line 70). Unify messaging helpers.
- **`copyToClipboard`** is implemented in both `popup.js` (line 39) and `actions-view.js` (line 40) with different approaches (one async clipboard API, one with textarea fallback). Extract to a shared utility.
- **`defaultLocatorOrder`** is defined in both `src/constants.js:22` and `src/content.js:103`. Use one source of truth.
- **Translator initialization** — `initializeTranslator(target, syntax)` is called in `background.js`, `actions-view.js`, and the save handler. The pattern of reading `storage.get(['target','syntax'])` then initializing is repeated 4+ times.
- **`renderActions` vs `renderActionsFromLines`** in `actions-view.js` — significant structural duplication (DOM construction of rows with index/input/controls). Extract a shared `createRow()` helper.

### 1.3 Inconsistencies
- **Module system mismatch**: `service-worker.js` and `background.js` use ES modules (`import/export`), but `popup.html` loads `intro.js` and `translations.js` as classic `<script>` tags, relying on globals (`IntroTour`, `t`, `getCurrentLanguage`). Content scripts (`classifier.js`, `scanner.js`, etc.) use CommonJS-style `if (typeof exports !== 'undefined')` guards.
- **`options.html`** loads scripts in `<head>` without `defer`; `popup.html` loads them at end of `<body>`. Inconsistent.
- **`actions-view.html:1`** — `<html lang="de">` hardcoded to German, but the app supports English too.
- **Naming**: `canSave` vs `isBusy` (boolean flags in storage), `target` means both "library target" and "active tab" depending on context.
- **`background.js` line 23**: `target = 'SeleniumLibrary'` but `popup.js` line 346 defaults to `target: 'Browser'`. Conflicting defaults.

---

## 2. Architecture Issues

### 2.1 Global Mutable State
- **`background.js`** — `list`, `script`, `recordTab`, `demo`, `verify`, `target`, `syntax` are all module-level mutable variables. The service worker can be terminated/restarted by Chrome at any time, losing this state. While `saveState()` exists, it's not called after every mutation (e.g., `target` and `syntax` set on line 163 via `settings` operation are stored to chrome.storage but the local vars may desync on restart).
- **`content.js`** — `strategyList` is module-level mutable state, re-pushed with `'index'` on every record/scan start (line 107, 116) causing duplicates if triggered multiple times.

### 2.2 Tight Coupling
- **`actions-view.js`** directly accesses `translator._generateVerify`, `_generatePath`, `_generateDemo` — private methods (prefixed `_`). The translator's internal structure is leaked into the view layer.
- **`popup.js` `toggle()` function** (lines 164-225) is a massive if/else chain that manually shows/hides elements by ID. This is a hand-rolled state machine with no clear state model. Any new button requires touching 10+ places.
- **`background.js` message handler** (lines 72-185) is a single 110+ line function with 13 `if/else if` branches. Each operation should be a separate handler.

### 2.3 Separation of Concerns
- **`popup.js`** mixes UI rendering, state management, messaging, clipboard operations, settings management, and intro tour initialization in one 400+ line file.
- **`background.js`** handles recording state, script generation, file download, tab management, icon changes, and storage — all in one file.
- No data layer / store abstraction — every file directly calls `chrome.storage.local.get/set` with its own default values.

### 2.4 Error Handling Gaps
- **`background.js:72`** — `onMessage.addListener` callback is `async` but Chrome's `onMessage` doesn't natively support async listeners returning promises for `sendResponse`. The `return true` at the end keeps the channel open, but some branches call `sendResponse({})` while others don't (e.g., `record`, `info`, `append`).
- **`content.js:106-126`** — `sendResponse` always sends `{ ok: true, status: 'record listeners attached' }` even for stop/scan operations. The status message is misleading.

---

## 3. Modernization

### 3.1 ES Modules Migration
- **Content scripts** (`classifier.js`, `scanner.js`, `tree-builder.js`, `xpath-locator.js`, `content.js`) use implicit globals (`builder`, `locator`, `classifier`, `scanner`). Migrate to ES modules using the manifest v3 `"type": "module"` for content scripts, or bundle them.
- **`translations.js`** and **`intro.js`** expose globals via `window.*`. Convert to proper ES module exports and import in `popup.js`/`options.js`/`actions-view.js`.
- **`options.js`** uses `if (typeof exports !== 'undefined') exports.update = update;` — convert to ES module.

### 3.2 Async/Await
- **`background.js:144-155`** (`save` operation) — wraps async logic in an IIFE inside an already-async function. Uses `FileReader.onload` callback instead of `URL.createObjectURL` (which is simpler and already used in `actions-view.js:33`).
- **`translations.js:getCurrentLanguage`** — wraps `chrome.storage.local.get` in a manual `new Promise()`. Use `chrome.storage.local.get()` which returns a promise in MV3.
- **`popup.js:runtimeSendMessage`** — manual promise wrapping with retry. Chrome MV3 `chrome.runtime.sendMessage` returns a promise natively.

### 3.3 Build System
- No bundler. Content scripts are loaded as individual files via manifest. Consider:
  - **Rollup/esbuild** to bundle content scripts into a single file
  - Enable tree-shaking to remove dead code
  - Minification for production builds
  - Source maps for debugging

### 3.4 TypeScript
- No type safety. The `translator` returns an object literal with methods — could be a class with typed interfaces.
- `classifier()` return type varies (`null | {type, value?}`) — would benefit from discriminated unions.

---

## 4. UI/UX Improvements

### 4.1 HTML Issues
- **`popup.html:48`** — Stray `´` character before `</div>`: `´  </div>`.
- **`popup.html`** — `<link async ...>` — `async` is not valid on `<link>` elements (only on `<script>`).
- **`options.html`** — Missing `<!DOCTYPE html>`, missing `lang` attribute, scripts in `<head>` without `defer` (blocks rendering).
- **`actions-view.html`** — Hardcoded German text as fallback (`Aufgenommene Aktionen`) but sets `lang="de"`. Should default to English.

### 4.2 CSS Issues
- **`assets/style.css`** — `@import url(...)` for Google Fonts blocks rendering. Use `<link rel="preconnect">` + `<link>` in HTML instead.
- **`assets/style.css`** — `#script-actions` is defined twice (lines ~200 and ~250) with conflicting values. The second definition silently overrides the first.
- **`assets/options.css:2-4`** — `height: 20px` on `.panel-options` seems way too small; likely a bug.
- **`assets/options.css`** — Uses CSS nesting (`h1 { ... }` inside `.heading { ... }`) which requires modern browsers or a preprocessor. Not guaranteed to work in all Chrome versions.
- Button icons (SVG references) — many referenced SVGs (e.g., `btn-scan.svg`, `btn-record.svg`) are not verified to exist. Missing assets would show blank buttons.

### 4.3 UX Issues
- **Popup width** — `width: min(1200px, 96vw)` on `.container` seems excessive for a browser extension popup (typically 300-400px wide).
- **No loading indicators** — Scan operation shows "Scanning..." but no spinner/progress.
- **No undo** — Clear script is destructive with no confirmation or undo.
- **Status messages** — `displayStatus(resp)` in `popup.js:254` passes the raw response object, resulting in "[Object object]" display (noted in the FIXME comment on line 252).

---

## 5. Dependency Updates

| Package | Current | Latest (approx.) | Notes |
|---------|---------|-------------------|-------|
| `eslint` | `^5.0.0` | `^9.x` | Major upgrade; flat config needed |
| `eslint-config-airbnb-base` | `^13.0.0` | `^15.x` | Must match eslint version |
| `mocha` | `^5.2.0` | `^10.x` | Breaking changes in v8+ |
| `chai` | `^4.1.2` | `^5.x` | ESM-only in v5 |
| `jsdom` | `^11.12.0` | `^24.x` | Major improvements |
| `playwright` | `^1.7.1` | `^1.41+` | Many new features |
| `nyc` | `^15.1.0` | Consider `c8` | `nyc` is maintenance-mode |
| `sinon-chrome` | `^2.3.2` | `^3.x` | Or switch to `@anthropic/webextension-polyfill` |
| `husky` | `^5.0.6` | `^9.x` | Setup changed significantly |
| `yarn` (as devDep) | `^1.22.19` | Remove | Yarn shouldn't be a devDependency |

- **`.travis.yml`** — References Node 10. Travis CI is largely deprecated; remove in favor of GitHub Actions.
- **GitHub Actions** — Uses `actions/checkout@v1` and `actions/setup-node@v1` (ancient). Update to `@v4`.
- **GitHub Actions** — `node-version: 12` is EOL. Use 20 or 22.
- **`.eslintrc.json`** — References `.eslintrc-todo` which doesn't exist in the repo.
- **`package.json:6`** — `"main": "src.background.js"` has a typo (`.` instead of `/`).

---

## 6. Possible Extensions (New Features)

1. **Selector strategies** — Support CSS selectors alongside XPath. Many modern frameworks prefer CSS.
2. **Action editing in popup** — Currently read-only in popup; editing only in actions-view. Allow inline editing everywhere.
3. **Session management** — Save/load multiple recording sessions with names.
4. **Drag-and-drop reorder** — Script lines currently use ↑/↓ buttons. Add drag-and-drop.
5. **Assertions generation** — Auto-generate `Page Should Contain` / `Element Text Should Be` assertions based on visible text.
6. **Wait strategies** — Auto-insert intelligent waits based on page load events instead of fixed `Sleep`.
7. **Export formats** — Support Playwright, Cypress, or Selenium WebDriver exports in addition to Robot Framework.
8. **Variable extraction** — Detect repeated values and extract them as `*** Variables ***`.
9. **Shadow DOM support** — `scanner.js` has a FIXME for shadowRoot handling (line 38). Implement shadow DOM traversal.
10. **Keyboard/navigation recording** — Record keyboard shortcuts, tab navigation, scrolling.
11. **More languages** — i18n infrastructure exists for en/de; add fr, es, ja, zh.
12. **Dark/light theme toggle** — Currently actions-view is dark, popup is light. Unify with theme support.

---

## 7. Testing Gaps

### 7.1 Missing Unit Tests
- **`src/background.js`** — Zero test coverage. The entire message handler (13 operations) is untested.
- **`src/popup.js`** — Zero test coverage. UI toggle logic, state management, settings updates untested.
- **`src/actions-view.js`** — Zero test coverage.
- **`src/content.js`** — Zero test coverage. Event recording logic untested.
- **`src/translations.js`** — Zero test coverage. `t()` fallback logic, `getCurrentLanguage()` untested.
- **`src/intro.js`** — Zero test coverage.
- **`src/logger.js`** — Zero test coverage.
- **`src/options.js`** — Only `update()` is tested (2 tests). Missing: language change, DOMContentLoaded handler.

### 7.2 Existing Test Issues
- **`test/setup.js`** — Sets `chrome` as a bare global (line 23) without `var/let/const` — relies on sloppy mode. Uses `sinon-chrome` mock implicitly via the global.
- **`test/locator/scanner_spec.js`** — Tests rely on globals (`locator`, `builder`, `classifier`) being set in test body. Fragile and would break with ES modules.
- **`test/locator/xpath-locator_spec.js:59`** — `sandbox` used without declaration (`sandbox = sinon.sandbox.create()`), relies on implicit global. Will fail in strict mode.
- **`sinon.sandbox.create()`** — Deprecated API. Use `sinon.createSandbox()`.

### 7.3 E2E Scenarios Needed
1. **Full record → stop → download flow** — Record clicks/inputs on a test page, stop, verify `.robot` file content.
2. **Scan page** — Navigate to a form-heavy page, scan, verify all inputs are discovered.
3. **Pause/resume** — Start recording, pause, interact with page, resume, verify only post-resume actions captured.
4. **Settings persistence** — Change target library to Browser, close popup, reopen, verify setting persisted.
5. **XPath validation** — Enter valid/invalid XPath, verify highlight/error display.
6. **Export formats** — Record actions, export as SeleniumLibrary vs Browser library, verify different keywords.
7. **Language switching** — Switch to German, verify all UI strings update, persist across popup reopens.
8. **Actions-view sync** — Record actions in popup, open actions-view tab, verify they appear and stay in sync.
9. **Service worker restart** — Record actions, simulate service worker termination, verify state survives via storage.
10. **Content script injection on navigation** — Start recording, navigate to a new page, verify recording continues.
11. **Multi-frame recording** — Test on page with iframes (`all_frames: true` in manifest).
12. **Clear and re-record** — Clear script, start new recording, verify old data is gone.

### 7.4 Test Infrastructure
- **No CI test execution** — GitHub Actions workflow references `xvfb-run` for headless tests but uses Node 12 (EOL) and `actions/checkout@v1`.
- **No test for content script loading** — `test/integration/extension_install_spec.js` only checks service worker activation.
- **Coverage** — `nyc` configured but no coverage thresholds set. Add minimum coverage gates.

---

## Priority Order

| Priority | Area | Impact | Effort |
|----------|------|--------|--------|
| 🔴 P0 | Fix missing `statusMessage` keys (failedScan/failedRecord) | Bugs | Low |
| 🔴 P0 | Fix `package.json` main typo (`src.background.js` → `src/background.js`) | Broken | Low |
| 🔴 P0 | Fix stray `´` in `popup.html:48` | Parse error | Low |
| 🟠 P1 | Unify module system (all ES modules) | Maintainability | Medium |
| 🟠 P1 | Extract message handler branches into separate functions | Readability | Medium |
| 🟠 P1 | Add unit tests for `background.js` and `content.js` | Reliability | High |
| 🟠 P1 | Update all dependencies to non-EOL versions | Security | Medium |
| 🟡 P2 | Extract shared utilities (clipboard, messaging, storage helpers) | DRY | Medium |
| 🟡 P2 | Introduce state management layer for popup | Architecture | High |
| 🟡 P2 | Add build system (esbuild/rollup) | DX | Medium |
| 🟢 P3 | TypeScript migration | Safety | High |
| 🟢 P3 | New export formats | Features | High |
| 🟢 P3 | Shadow DOM support | Features | Medium |
