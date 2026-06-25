# Changelog

## [Unreleased]

## [0.12.0] - 2026-06-25

### Robot Framework execution configuration (Epic EXEC)

- The **New Run dialog gains a governed "Advanced" section** (Editor and up,
  behind the `executionAdvancedArgs` feature flag): a **variables** key/value
  editor and a **freeform `robot` arguments** field. Arguments are validated by
  a single resolver seam against a three-zone safety model — output-owning and
  code-loading flags (`--outputdir`, `--listener`, `--pythonpath`,
  `--variablefile`, `--argumentfile`, …, including short aliases and
  abbreviations) are **always rejected, for every role** — and are passed as a
  list, never through a shell. Every advanced run is audited.
- **Tag discovery**: include/exclude tag fields now offer the tags actually
  present in your repo's suites as a pick-list (free-typing still allowed).
- **Long name & structural id** of each test are surfaced read-only in the
  report detail view.
- **`__init__.robot` suite-init files** are editable in the editor, with a
  non-blocking warning when an init file declares a `*** Test Cases ***`
  section (which Robot Framework forbids).
- **DataDriver** dynamic test generation from a CSV data source is available
  behind the `executionDataDriver` flag.

### Curated & organization-extensible execution modifiers and listeners

- A **curated registry** of pre-run / post-run **modifiers** and live
  **listeners** with three trust tiers: RoboScope-shipped (vendor), your
  **organization's own** (registered via the `roboscope.modifiers` entry-point
  or a `ROBOSCOPE_MODIFIERS_CONFIG` file — backend config, no UI), and
  admin-gated runtime user code. Post-run modifiers (`--prerebotmodifier`) and
  live listeners are the hook to **push results to a test-management system** or
  emit custom reports as a run finishes — without ever exposing a free-typed
  code-loading flag.
- Admin-only, repository-confined **`--pythonpath`** and **`--variablefile`**
  levers, each behind its own default-off flag and an explicit code-loading
  consent.
- Full in-app documentation (EN/DE/FR/ES) covering the trust tiers, both
  organization-registration mechanisms, and the live-vs-post-run distinction.

### Settings — clarity & safety

- A **sticky "unsaved changes" bar** on the General tab (with a per-row marker,
  a Discard action, and a leave guard) so edits are never silently abandoned
  before the far-below Save button.
- Toggling a feature flag now **takes effect immediately** (no hard reload).
- The **advanced-execution feature flags** appear as toggles under
  Settings → Features (all default off).
- **All settings descriptions and category headers are now localized**
  (EN/DE/FR/ES/ZH) instead of always English.

## [0.11.0] - 2026-06-19

### Flow Editor — your repository keywords are first-class

- A dedicated, top-pinned **"Your resources"** section groups the keywords from
  your repo's `.robot`/`.resource` files (file glyph + relative-path subtitle),
  separate from the library list; the imports panel now splits into distinct
  **Resources** and **Libraries** lists.
- Inserting a resource keyword shows a **localized import-confirmation toast**
  (the auto-`Resource`-import is no longer silent) and **pre-fills the node's
  required argument slots** from the keyword's `[Arguments]` signature.
- Long keyword names get a **hover tooltip** (full name) and stay legible; a new
  **sort control** (Most used / A–Z / Imported first) and a **"what's shown"
  filter** with an *adaptive default* (hides not-installed example libraries for
  repos that already have an environment and a non-trivial test file) let you
  shape the palette. All choices persist.
- Fixed a duplicate where a repo's resource keywords appeared both under
  "Your resources" and again as a library group.

### Explorer — quiet, repo-scoped keyword loading

- Keyword data is now cached **per repository**: switching files no longer
  re-invalidates and refetches the whole keyword set every time (it only
  refreshes on real changes — imports added, package installs, saves).
- The "Loading keywords…" indicator is now a **subtle slim line** instead of a
  prominent bar, and only appears on first repo open.

### Deployment governance (Epic GOV)

- Operators can **lock down feature areas per deployment** — first up, package
  management. Flags resolve **ENV > DB > default-on**; enforcement is
  per-endpoint (a disabled feature returns **403 even for admins**) and audited.
  A token-guarded `useFeatureFlags()` gates the UI; an env override locks the
  matching Settings toggle.

### Robot Framework execution config (Epic EXEC)

- The **New Run dialog exposes Include/Exclude tags**, threaded to the existing
  `robot --include/--exclude` runner.

### AI provider & output (Epic AIX)

- Added a **LiteLLM** provider type (gateway to many models) and a
  **verbosity control** for AI failure analysis.

### Security

- Cleared **all open Dependabot advisories**: `cryptography` → 49.0.0,
  `PyJWT` → 2.13.0, `starlette` → 1.3.1 (with `fastapi` → 0.137.2 and
  `robotframework-roboview` → 1.0.0), and `dompurify` → 3.4.11
  (GHSA-cmwh-pvxp-8882).

### CI / Docs

- New **i18n & docs consistency** gate keeps EN/FR/ES documentation subsections
  in lockstep so a section can't ship in one language but not the others.

## [0.10.0] - 2026-06-17

### Flow Editor — control-structure authoring

- Added **EXCEPT** and **FINALLY** palette items, and adding a **TRY** now
  scaffolds `TRY → EXCEPT → END` so the block is valid Robot Framework the
  moment it is added (a bare `TRY … END` is a syntax error and could not be
  completed through the UI before). New E2E coverage builds IF/ELSE and
  TRY/EXCEPT through the Flow Editor and asserts they land cleanly in the
  Code tab, on disk after Save, and across a reload.

### AI failure analysis — localized output + one-click fixes

- The analysis now runs in the **frontend's current language** (EN/DE/FR/ES/ZH);
  prose is translated while code, keywords, and patches stay verbatim.
- Suggested unified-diff patches can now be **applied automatically** with one
  click. The backend applies them context-first and refuses (HTTP 422) when the
  hunks no longer match the file, so a stale patch can never corrupt a test.
- The analysis is **scoped to its execution/report** — it no longer lingers
  when switching to a different run, and is discarded on leave.

### Statistics

- The **success-rate-over-time** chart now renders one slot per calendar day:
  days without executions keep their width and show a faint baseline instead of
  collapsing the gap, so the time axis is continuous and evenly spaced.

### Internationalization

- **Complete Simplified Chinese (中文)** translation — every section of the UI
  is now translated. Previously only high-traffic sections were covered and the
  rest fell back to English; zh still deep-merges over en so future keys resolve
  until translated.

### Security & CI

- Bumped **fastmcp to >=3.2.4,<4** and cleared all remaining open Dependabot
  advisories (closes #35).
- Added a **Windows online-install smoke gate** to the Phase 4 release gates (#49).

### Self-healing library distribution model

- **`robotframework-roboscopeheal` now visible + installable from
  the Package Management UI.** The library is added to the
  `/api/v1/environments/packages/popular` list with a new
  `shipped_with_roboscope: true` flag. The Environments view renders
  a blue "ships with RoboScope" / "mit RoboScope ausgeliefert" badge
  on entries that carry the flag (translated in EN/DE/FR/ES).
- **Install resolution: vendor for default, PyPI for explicit
  pins.** The install path (`environments/tasks.py::install_package`)
  now consults a `_SHIPPED_VENDOR_PACKAGES` registry. When the UI
  asks to install a shipped package WITHOUT specifying a version,
  the install resolves to the on-disk vendored source tree
  (`backend/vendor/<dir>/`) and the wheel is built from there. An
  EXPLICIT version request bypasses the vendor and goes to PyPI —
  that's the "I want to upgrade past what RoboScope ships" path.
  Today this means a no-version click installs heal 0.2.1 from the
  bundled tree; tomorrow (once PyPI carries the package) a pinned
  `0.4.0` request fetches PyPI as expected. No code change needed
  at flip-time other than potentially removing entries from the
  registry when a vendored library is replaced by a hard PyPI
  dependency. Backend test pin in
  `test_tasks.py::test_shipped_no_version_installs_from_vendor_path`
  + `test_shipped_with_version_goes_to_pypi`. Registry contract
  pinned in `test_vendored_heal_auto_install.py` (case-insensitive
  lookup, missing-vendor-dir warns + falls back to None).

### Recorder lifecycle visibility (RECORDER-VIS epic)

- **RECORDER-VIS-1 — lifecycle SSE events + Restart browser.** The
  Live recording view now shows what the recorder is actually
  doing instead of an ambiguous "Connecting…" badge. The backend
  SSE `/commands` stream carries a new `event: lifecycle` channel
  alongside the existing `event: command` channel; `v2_recorder_
  task` emits four phases as it boots and runs:
  - `browser_starting` — right before `pw.chromium.launch(...)`.
  - `browser_ready` — after the initial `page.goto` (or
    `new_page` when there is no target URL) — the user can click
    and see events.
  - `browser_restarting` — emitted by the new
    `POST /recordings/sessions/{id}/restart-browser` endpoint
    just before it tears the current task down.
  - `browser_crashed` — emitted in `_on_disconnect` when the
    browser dies without a prior user stop, and from the outer
    `except` wrapper with the exception message when the
    Playwright loop raises (e.g. missing `$DISPLAY` on a Linux
    server).
  `RecordingLiveView.vue` consumes the channel, renders a phase
  pill + live `mm:ss` uptime counter once ready, and offers an
  always-visible "Restart browser" button enabled in
  `browser_ready` / `browser_crashed` and disabled during the
  transient `browser_starting` / `browser_restarting` phases.
  Captured commands are preserved across a restart — the in-
  process FIFO is keyed by session id, not task id, so the new
  task slots into the same queue + DB row.
- Internal: `v2_command_queue` generalised to a heterogeneous
  `RecordedCommand | LifecycleEvent` stream via the new
  `iterate_events()` iterator. `iterate_commands()` is kept as a
  filter-only wrapper for backward compatibility. The recorder
  task wrapper moved its terminal-status update
  (`_mark_status(COMPLETED)`) out of the inner `_recorder_loop`
  and into the wrapper so it can distinguish stop-for-restart
  (skip mark, keep queue) from clean stop (mark, finalise).
- 14 new backend tests in `test_v2_recorder_vis.py` cover the
  queue's heterogeneous yield order, `signal_restart_v2`
  behaviour, the restart endpoint's 404 / 403 / 409 / 501 paths
  plus two happy-path branches (with and without a live task),
  and end-to-end SSE multiplexing of `event: lifecycle` +
  `event: command` over the streaming response. 17 frontend
  tests in `RecordingLiveView.lifecycle.spec.ts` pin the
  state-machine transitions across every lifecycle entry point,
  the command-first fallback, and the `mm:ss` uptime formatter.
- i18n complete in EN/DE/FR/ES.

### Self-Healing opt-in ergonomics (HEAL epic)

- **HEAL-1 — per-step toggle in the Flow Editor.** When the
  currently selected keyword step is one of the 13 RoboScopeHeal-
  supported Browser keywords (Click, Fill Text, Hover, Press Keys,
  Wait For Elements State, Upload File, Check Checkbox, Uncheck
  Checkbox, Select Options By, Get Text, Get Element Count,
  Drag And Drop, Type Text), the detail panel renders a
  *Self-Healing* checkbox. Toggling rewrites that single step's
  keyword name (`Click` ↔ `Heal Click`) via the form path — never
  via raw-text regex — and adds or removes the bare
  `Library    RoboScopeHeal` row in Settings based on whether any
  Heal* keyword is left in the file. A user-configured library
  row (`Library    RoboScopeHeal    budget=…`) is always
  preserved.
- **HEAL-2 — suite-level toggle in the editor toolbar.** A
  `Self-Healing: On / Off` button next to the `.robot` badge,
  visible only when the file contains heal-able keywords. One
  click promotes every supported Browser keyword to its Heal
  variant (and adds the library import); one more click reverts.
  Operates through the same parsed-form path as HEAL-1 — every
  rewrite is a one-line source diff the user reviews and saves
  explicitly. The existing `no-heal` Robot tag is still the
  per-test runtime opt-out layered on top of this source choice.
- Both toggles share the new `frontend/src/utils/healToggle.ts`
  utility (`HEAL_VARIANTS` map + `applyHealToForm` rewrite
  function), pinned by 42 unit tests covering the 13-keyword map,
  library-row idempotence, the `Run Keyword    Click ...`
  edge case (keyword-as-argument is never rewritten), Heal-
  prefixed user keywords outside the supported set (e.g.,
  `Heal Login`) being left alone, and immutability of input
  forms. i18n complete in EN/DE/FR/ES.

## [0.9.0] — 2026-05-06

Headline: a substantial round of UX polish + stabilization driven
by hands-on user testing — Flow Editor, Recorder, Reports, Repos
and Dashboard all touched.

### Security

- New `SECURITY.md` documenting the disclosure process, supported
  versions, and known third-party advisories. Three open Dependabot
  alerts on `fastmcp 2.14.x` (transitive via `rf-mcp`) are
  documented as not exploitable in RoboScope's usage — none of
  the vulnerable APIs (`OpenAPIProvider`, `OAuthProxy`,
  `gemini-cli`) are reached. Tracked for the bump in #35.
- `picomatch` advisory (GHSA-3v7f-55p6-f55p) closed via top-level
  override pinning `>= 4.0.4`; `follow-redirects` advisory closed
  by the axios 1.16 bump merged from main.

### Dashboard rebuild

The landing page is now a card grid pointing into every navigable
section of the app (Repos, Explorer, Runs, Stats, Recorder,
Environments, Docs, Settings) plus a "Tip of the day" card that
rotates through 30 RoboScope-specific tips daily. The previous
KPIs / recent-runs / repo-grid layout is retired — KPIs and
recent-runs live under their dedicated views (Stats, Runs).

### Default "Robot Framework Examples" git project

First-time users get a ready-to-use reference suite seeded on
startup: <https://github.com/raffelino/robot-framework-examples>
— public repo, Apache-2.0, 61 headless tests covering BuiltIn,
Collections, String, DateTime, OperatingSystem, Process,
RequestsLibrary, Browser (headless), DatabaseLibrary plus
control-flow + templates + setup/teardown + variables-file +
custom-library concepts. Auto-sync is off by default; manual sync
button still works.

### Recorder — visibility-aware selector verification

The Story S.3 verifier evolved beyond uniqueness:

- `LocatorFactory` now returns `MatchInfo(total, visible, actionable)`
  rather than a plain count. Playwright resolves each candidate's
  visibility + enabled state in one `evaluate_all` round-trip per
  candidate (was N×2 RPC calls before — pushed e2e budgets past
  30 s).
- Candidates rank by `actionable_rank` (0 = gold, 1 = visible-only,
  2 = hidden, 3 = unverified-multi) then quality_score — gold
  candidates always sort before disambiguated multi-match ones.
- Penalty schedule: visible-but-disabled −5; total ≥ 1 visible 0
  −25 (kept as fallback for auto-heal but always loses to a
  visible alternative).
- Page-level scrolls (no element captured) are dropped — Browser
  library's `Scroll To Element` requires a selector and crashed
  replay with "expected 1 argument, got 0".
- Targeted-keyword-without-selector lines are now emitted as pure
  RF comments (`# RBSCOPE: dropped …`) instead of
  `<Keyword>    # WARNING:` (which RF parsed as a zero-arg call
  and crashed at replay).

### Reports — clickable HTML report + Detailbericht merge

- Run-Detail panel and standalone `/reports/<id>` view now ship
  the keyword tree (formerly the "Detailbericht" tab) inside the
  summary tab so the deep view is one scroll away rather than a
  tab click. HTML Report keeps its own tab.
- The HTML report's iframe loads from
  `/api/v1/reports/{id}/assets/report.html?at=<token>` (302 from
  the legacy `/html` endpoint) so JS-driven navigation
  (`location.href = "log.html#xxx"`) lands at the right path.
- HTML files served by the asset endpoint get a `<base href>`
  injection carrying a freshly minted asset token + a
  fragment-fix script for `<a href="#…">` clicks. Clicking on a
  test row now opens its log, no more "authentication required".
- Two new "↗ open in new tab" affordances: one on the
  Detailbericht header (opens `/reports/<id>/detailed`, a minimal
  layout that renders ONLY the keyword tree), one on the HTML
  Report tab (pops the iframe URL out).

### Repos — UX and stability

- Clicking a repo name or URL/path in the Repos card now jumps
  straight into the Explorer for that project.
- New `(i)` info pills next to Sync / Auto-Sync / Pre-Run-Sync
  with click-toggle popovers explaining each term.
- Auto-recovery for stale `sync_status='syncing'` rows: the
  5-min auto-sync tick now scans for rows with
  `updated_at < now − 10 min` and resets them to `error` with a
  clear message so the user is no longer stuck waiting for a
  backend restart.

### Flow Editor — many small fixes

- Backspace (Mac) / Delete (Win/Linux) on a selected node deletes
  it.
- Library palette categories sort by usage in the current file —
  the libs you use most bubble to the top.
- Project: category for the currently-open file is pinned to the
  top of the palette and badged "this file".
- Switching files auto-collapses the palette; explorer keyword
  refresh re-collapses too — palette always opens condensed.
- Selected element gets a thicker primary-color outline + halo +
  10 % tint background.
- "+" palette add inserts directly after the selected node, not
  at the bottom.
- Adding the first return-variable to a `keyword` step
  auto-promotes it to `assignment` syntax (`${var}=  Keyword …`);
  removing the last var flips it back.
- Detail panel spans the full canvas height; left-edge resizer
  lets the user widen it for keywords with many arguments.
- Library auto-imports trigger after save (not before), and the
  RF-bundled set (Collections, String, DateTime, …) is no longer
  filtered from libdoc introspection — explicitly imported
  bundled libs now show their full keyword surface, not the
  curated 10-keyword "(examples)" subset.
- Keyword doc modal renders libdoc HTML output directly; doc cap
  raised from 200 → 4000 chars; `doc_format` field now flows
  through search-keywords schema → router → store → modal.

### Code Editor

- `\#` is now treated as a single escape token; the inline
  comment regex no longer eats the rest of the line after a
  backslashed hash.

### Stats / Heal-rate

- Heal-rate KPI card moved from the top of Overview to the bottom
  (under Flaky Tests). Lila gradient and accent border replaced
  with the standard card chrome — the card reads as one of N
  stats rather than a hero metric.

### Navigation

- Identity Providers and Teams entries are marked `preview` in
  the sidebar (small accent pill) — features are still in active
  development.

---

Older work that landed during the same release window
(`feat/recorder-and-bmad` branch) follows.

### Recorder quality (loop session 2026-04-29 evening)

Landed as 14 commits all driven by hands-on user testing on
heise.de. The flow:

1. **Stuck-recorder reset button** (`b8fb5ff`) — new "Reset stuck
   recordings" panic button on the launcher view. Idempotent
   `POST /recordings/sessions/reset` cleans up any DB rows in
   `RECORDING` for the current user (graceful stop signals + force
   to `CANCELLED`). For the case where the recorder thread crashed
   but the DB and orphan Chromium are still around. 5 backend tests.
2. **Cross-origin iframe capture** (`feb0029`) — Sourcepoint /
   OneTrust / TCF consent banners live in cross-origin iframes; the
   capture script aborted in non-top frames and silently dropped
   every cookie-accept click. Now runs in every frame, tags payloads
   with `frame_url`, emitter wraps the active selector with
   `iframe[src*="<host>"] >>> <inner>` (Browser-library cross-frame
   piercer). 12 tests.
3. **Iframe-origin chip in RecordingLiveView** (`c1b0feb`) — small
   `⇣ <host>` badge next to each command from a non-top frame so the
   user can tell at a glance which clicks came from the consent
   widget vs. the page under test.
4. **Ad/tracker iframe deny-list** (`3a39e1d`) — server-side
   suppression of events from doubleclick / criteo / taboola / 17
   total well-known ad networks. Conservative — Sourcepoint /
   OneTrust / Stripe / reCAPTCHA / OAuth iframes pass through. 7
   tests.
5. **Per-step delete in RecordingLiveView** (`92d5b1f`) — small `✕`
   button per row for noise the deny-list misses. Local prune; saved
   sidecar excludes pruned rows. Visually subdued (40% opacity until
   hover). 5 tests.
6. **`wait_until=domcontentloaded` in recorded `New Page`**
   (`4648b9d`, earlier) — the Playwright default `wait_until="load"`
   waits for every ad/tracker subresource and reliably exceeds the
   Browser-library 10s timeout on real sites (run 32 hit this on
   heise.de). Both emitters write the explicit form. 26 tests.
7. **`${HEADLESS}` is defined under `*** Variables ***`**
   (`dce2ced`, earlier) — the recorder referenced `${HEADLESS}` in
   its bootstrap but never declared it; RF refused to start with
   "Variable not found." Now emits a Variables block with default
   `${HEADLESS}    false`.
8. **`verify_candidates` actually wired into capture**
   (`d339584`) — the Story-S.3 verifier (run each candidate against
   `page.locator(...).count()`, mark unique, demote multi-match) was
   implemented months ago but never called by the v2 recorder; every
   sidecar shipped with `verified_unique=False` on every candidate.
   Now plumbed through `_verify_command_candidates` in
   `v2_recorder_task.on_capture`, scoped to the originating frame
   (not the top page) so iframe selectors verify in their own
   document.
9. **Multi-match disambiguation for text/aria/testid via
   `>> nth=0`** (`af43856`) — the verifier already disambiguated CSS
   / xpath / pw_locator with `:nth-match(1)` / `[1]` / `.first`, but
   text / aria / testid passed through unchanged with
   `verified_unique=False`. On heise.de's Sourcepoint banner
   `text=Zustimmen` matched 3 elements (paragraph + 2 buttons),
   strict-mode rejected the click, replay failed. Playwright's
   chained-locator `<base> >> nth=0` now disambiguates these too.
10. **Exact-match `text="..."` instead of substring `text=...`**
    (`57f58bb`) — substring match caught the paragraph "Unter
    Einstellungen können Sie zustimmen" together with the actual
    button on heise.de. Exact match scopes to elements whose
    textContent equals the recorded string after trim. Tests with
    embedded `"` in the value drop the text candidate and fall back
    to CSS / testid (escape complexity in the .robot wire format
    isn't worth it).
11. **Autogen-class heuristic catches CSS-in-JS / CSS-modules
    hashes** (`fd370f6`) — old `_looks_autogenerated` only flagged
    20+ char alphanumerics. Real heise.de class `div.jw8mI` (5
    chars, letter-digit-letter sandwich) sailed through. Three new
    pattern checks: short letter-digit-letter sandwich, CSS-modules
    `__<hash>` suffix, Emotion `^css-…digit…$` prefix. Negative
    guard so human-named `btn1 step3` keep working. 4 tests.
12. **RF token escape for leading `#`** (`e4406d1`,
    `5b14d56`) — Robot Framework treats any token starting with `#`
    as a comment marker. A recorded CSS-ID selector like
    `#login-form` rendered as `Click    #login-form` made Click
    silently run with zero arguments. Backend
    `_escape_rf_token` adds `\#`; FE serializer mirrors with
    `escapeRfToken`; FE parser unescapes via `unescapeRfToken` so
    the picker compares logical values. Mirror pair must stay in
    lockstep. 6 backend + 7 frontend tests.
13. **Position-independent command id (RECORDER-IDMAP, two
    phases)** (`9035768` + `65dc45f`) — the structural fix the user
    explicitly asked for. The selector group ↔ Robot step mapping
    used pure positional lookup in `flowConverter.matchStepToCommand`
    (`sidecar.commands[recordedIndex(...)]`); reorder / delete /
    insert in the FlowEditor silently shifted candidate groups onto
    the wrong rows. Now:
    - Backend mints a 12-char hex id per `RecordedCommand`.
    - Emitter writes `# rbs:<id>` as a trailing line comment.
    - Frontend parser extracts it onto `RobotStep.rbs_id`.
    - Matcher prefers id-lookup; falls back to positional only when
      no step in the file has an id (legacy recordings). Mid-file
      "step has no id but other steps do" returns null instead of
      phantom-matching, so hand-inserted rows don't show wrong
      selectors.
    - Serializer re-appends `# rbs:<id>` on save → identity round-
      trips through full edit cycles. 5 backend + 8 frontend tests.

### Fixes — User-reported papercuts (loop session 2026-04-29)

#### Timezone display ("vor 2 Std." right after a sync)
- **Frontend `parseBackendDate`** — naive ISO strings (no `Z` / no
  offset) are now treated as UTC. Was: JS parsed `2026-04-29T07:58:04`
  as local time, so a CEST user saw a fresh sync as 2 hours old.
  Applied at four `now − parsed` sites: `formatTimeAgo`,
  `useBypassStatus.remainingMinutes`,
  `IdpProviderListView.formatRelative`, `StatsView.stalenessText`.
- **Backend `UtcJSONResponse`** — wired as FastAPI's
  `default_response_class`, post-processes outgoing JSON so naive
  datetime literals always carry `Z` on the wire. Belt-and-suspenders
  for the frontend fix; either layer alone closes the bug, both layers
  protect future endpoints.

#### FlowEditor papercuts
- **Detail panel closed mid-keystroke** — `stepsToFlow`'s
  `step: { ...step }` left `args` / `returnVars` / `loopValues` as
  shared array references with the form. v-model writes during typing
  fired the deep `props.form` watcher and reset selection. Fix: deep-
  clone the step's array fields in a new `cloneStep()` helper. Form is
  updated on blur via `Object.assign` as before.
- **Add-arg picker clipped by panel scroll** — popover Teleported to
  `<body>` with `position: fixed` and a bounding-rect-derived inline
  style; outside-click handler updated to allow clicks inside the
  popover (Teleport breaks the wrapper-subtree check).
- **Bool checkbox dropped `name=` prefix on toggle** — toggling
  `force=True` overwrote the slot with bare `True`, so on re-render
  `specForSlot` fell back to a different positional spec and the
  checkbox vanished. Fix: regex strips the `name=` prefix in both
  `isBoolChecked` and `onBoolToggle`; signature default is consulted
  for empty value-half (`force=`) slots; `pickAddArg` pre-fills the
  default so freshly-added named args are valid `.robot`.
- **Bool↔text input toggle** — small `{}` button next to any typed
  control (bool/select/number/duration) flips into free-text input
  for that slot, so users can enter `${HEADLESS}` on a bool slot.
  Reverts via the same button (icon flips to `⌨`). Auto-text mode
  still triggered when value-half is a Robot variable reference;
  detection now strips the `name=` prefix so `headless=${HEADLESS}`
  is correctly recognised as variable-bearing.
- **Move up/down lost selection** — selection was pinned to the OLD
  position-id which after the swap pointed at the SWAPPED step.
  `rebuildAndReselect(targetId?)` now accepts an explicit override;
  `moveStepUp/Down` pass the moved step's NEW slot id so the user can
  press Up repeatedly to walk a step to the top.
- **Drag-arm hold delay** — keyword/control node drag handles only
  flip `draggable=true` after a 200 ms hold. Brief misclicks no
  longer start a reorder. Visual highlight (blue/amber) while armed.
- **Drop-zone math respects node heights** — `findInsertIndex` and
  `getDropIndicatorY` now use each node's midpoint and actual gap
  geometry via `estimateNodeHeight()`. Was top-edge-only, so the
  insertion point felt like a fixed grid; tall arg-heavy nodes
  pushed the boundary to wrong place.

#### Recorder
- **`New Page    <url>    wait_until=domcontentloaded`** — was the
  Playwright default `wait_until="load"` which on real-world pages
  (heise.de etc.) waited for every ad/tracker subresource and timed
  out at 10 s even though the page was visually loaded. Run 32
  reproduced this exactly. Both emitters (`generator.py`,
  `robot_emit.py`) now write the explicit `wait_until=`.
- **`${HEADLESS}` is now defined** — recorder emits a
  `*** Variables ***` block with `${HEADLESS}    false` so Robot
  Framework doesn't refuse the test with "Variable not found." The
  reference itself was already there (so users could flip head/headless
  without editing the body); the block defining it was missing.

#### Repository management
- **`name` optional on Git repos** — derived from the Git URL
  basename when omitted (`viadee/roboscope.git` → `roboscope`,
  `git@host:owner/repo.git` → `repo`). Local repos still require an
  explicit name. Validator handles HTTPS, SSH-shorthand, and
  filesystem-unsafe basenames (collapsed to `-`).

### Security hardening
- **XXE / billion-laughs on `output.xml`** — switched
  `src/reports/parser.py` and `src/recording/heal/heal_report.py`
  to `defusedxml.ElementTree`. Robot's `output.xml` is built from
  user-authored `.robot` tests, so external-entity payloads in the
  XML could exfiltrate files or DoS the parser. Custom exception
  bridging (`ValueError → ET.ParseError`) keeps existing callers
  working.
- **Windows authenticated-RCE on Open-In-Editor** —
  `subprocess.Popen(["start", "", target], shell=True)` interpreted
  shell metacharacters in the target path. EDITOR-rights user could
  create a file named `foo&calc.exe.txt` and trigger backend-host
  command execution. Fix: `os.startfile(target)` (Windows
  ShellExecuteW directly, no cmd.exe).
- **Production asserts compiled out under `python -O`** —
  4 `assert db is not None` mypy-hint asserts in `retention_cleanup.py`
  replaced with `if db is None: db = SessionLocal()` so flow-typing
  narrows naturally and behaviour survives `-O`.

### Type-strict cleanups
- **mypy `--strict` clean on `roboscope-rfheal/src/`** — caught a
  latent `@library(scope="TEST SUITE", ...)` bug: Robot's typing
  stubs declare scope as `Literal['GLOBAL','SUITE','TEST','TASK']`,
  the legacy "TEST SUITE" alias would break with a future RF release.
  Switched to `SUITE`. Same fix mirrored in the in-tree
  `src/recording/heal/library.py`.
- **Real-bug filter on backend `mypy --strict`** —
  `_broadcast_docker_build_log` was the lone helper missing the
  `_event_loop.is_running()` guard (every other broadcast helper had
  it). `oidc_discovery.py` lacked null narrowing on `jwks_data` and
  emitted `str` where `Literal["passed","failed"]` was expected.
  Variable-shadow `browser_pkg = ....scalars().all()` rebound to
  `Sequence | None` cleaned up.

Highlights from the prior loop session of 2026-04-28/29 (24 stories
on top of the Phase-4 SSO/Teams + Recorder + BMAD foundation):

### Features
- **REPO save loop for non-Git users** (REPO-1) — `GET /repos/{id}/status`,
  `POST /repos/{id}/commit`, `/push`, `/publish` endpoints; in-app
  Save modal with conflict-recovery state; tree-header `Save N changes`
  badge in Explorer.
- **Auto-Sync actually pulls on schedule** (REPO-2) — APScheduler
  5-minute heartbeat invokes `due_repos(now)`; per-repo
  `sync_interval_minutes` honoured. Was previously a stored-but-unused
  toggle.
- **Pre-run sync** (REPO-3) — opt-in per-repo flag pulls
  `origin/<default_branch>` synchronously before each run, with a
  60 s wall-clock timeout and graceful fall-through on failure.
- **Webhook pre-sync** (REPO-4) — `POST /webhooks/git` now dispatches
  `sync_repo` before `execute_test_run`; the single-worker task
  executor guarantees order.
- **Default-password banner** (SECURITY-1, revised) — non-blocking
  yellow banner shown when an admin still uses the seed password,
  links to a `POST /auth/change-password` endpoint. Server logs a
  WARNING on every flagged login.

### Security
- **Authenticated report assets** (REPORT-1) — `/reports/{id}/assets/`
  was anonymous; now requires Bearer header or `?token=<jwt>`. Closes
  the first item under CLAUDE.md known issues.
- **Asset token replaces JWT in iframe URLs** (SECURITY-3) — new
  HMAC-signed, report-scoped, 1-hour-TTL `?at=<asset_token>` embedded
  in `<base href>` instead of the user's JWT. Iframe URLs leaking out
  no longer expose the user's full access token.
- **Streaming upload size guard** (ROBUSTNESS-1) — `/reports/upload`
  previously read the full body into RAM before the 500 MB check. Now
  streamed in 1 MiB chunks with an early-abort plus a Content-Length
  pre-check.

### Performance
- **Lazy-loaded docs locales** (PERF-1) — DocsView chunk shrunk from
  413 kB → 4 kB (gzipped 124 kB → 1.8 kB). Each locale's content
  streams on demand.

### Robustness / Ops
- **Deep `/health` endpoint** (ROBUSTNESS-1) — runs `SELECT 1`; returns
  503 with `{"status":"unhealthy","reason":"database_unreachable"}`
  on DB outage so kubelet liveness probes can flag the pod.
- **Request-ID correlation in logs** (LOGGING-1) — every log record
  emitted during an HTTP request carries the `X-Request-ID` header
  value via a `ContextVar`, propagated automatically through the
  pythonjsonlogger formatter.

### Refactor / DevEx
- **Single Docker client bootstrap** (REFACTOR-1) — three near-identical
  copies of the `from_env()` + `docker context inspect` recipe
  replaced with `src/docker_client.py:get_docker_client()`.
- **`as any` cleanup** (TYPE-1..TYPE-4) — went 25 → 0 real casts in
  source. New exported unions (`AnalysisStatus`, `PackageInstallStatus`),
  discriminated union for the keyword palette, runtime type-guard
  for drag-drop step-type strings.

### Accessibility
- **A11Y baseline pass** (A11Y-1) — `<html lang>` follows i18n locale,
  icon-only AppHeader buttons get `aria-label`, language switcher
  gets `aria-pressed`, skip-to-main link mounted in DefaultLayout.

### Tests (5 new files, 99 new tests)
- WebSocket `ConnectionManager` (TEST-1, 15)
- DockerRunner (TEST-2, 24)
- AI provider CRUD endpoints (TEST-3, 19)
- AI generate / reverse / analyze / status / accept (TEST-4, 20)
- `execute_test_run` early-exit branches (TEST-5, 3)

### Sibling repos (local-only, pre-publish)
- `roboscope-rfheal/` — heal package, packaged for PyPI; commit
  ready, not pushed.
- `roboscope-examples/` — Apache-2.0 starter examples for the most-used
  Robot Framework libraries (Collections, String/DateTime, Process/OS,
  RequestsLibrary, DatabaseLibrary, JSONLibrary, Browser); 26 tests
  green via `uv run robot examples/`. Initial commit ready, not
  pushed.
## [0.8.2] - 2026-03-26

### Features
- **YouTube Demo Videos on Landing Page** — Embedded YouTube demo videos (DE/EN) on the landing/login page for new users

### Fixes
- **Windows Offline Build** — Split Windows build to native PowerShell script (`build-windows.ps1`) running on Windows host, fixing missing `tzdata` and other Windows-conditional dependencies that could not be resolved when cross-building on Linux CI
- Fix test venv directory creation in rfbrowser tests for CI

### Build
- New `scripts/build-windows.ps1` and `scripts/test-install-windows.ps1` for native Windows builds
- CI workflow now runs Windows offline build on `windows-latest` instead of `ubuntu-latest`
- `build-mac-and-linux.sh` simplified to only handle Linux/macOS platforms

## [0.8.1] - 2026-03-26

### Features
- **Browser Library Variant Support** — Support for `robotframework-browser-batteries` (self-contained, no Node.js needed) as alternative to standard `robotframework-browser`. Conflict detection prevents installing both variants simultaneously. Dockerfile generation skips Node.js/rfbrowser init for batteries variant.
- **rfbrowser init Status in Environments** — Browser packages now show initialization status: ✅ "Browser initialized" or ⚠️ "rfbrowser init required" with a manual trigger button. `POST /environments/{id}/rfbrowser-init` endpoint for manual init.
- **Default Environment Auto-Assignment** — Explorer auto-assigns the "default" environment to projects that have none. Environment badge displayed next to the project selector with link to configuration.
- **Keyword Autocomplete from All Installed Libraries** — rf_knowledge now discovers all RF-related packages in the venv (not just explicitly imported ones), providing broader keyword autocomplete coverage.
- **Keyword Cache Invalidation** — `POST /ai/rf-knowledge/keywords/invalidate` endpoint to force re-scan of keywords when environment packages change.
- **Browser-Batteries as Default** — `setup-default` environment now installs `robotframework-browser-batteries` instead of `robotframework-browser`.

### Fixes
- Fix keyword search wildcard `*` not returning any results (preloadKeywords was broken)
- Fix stuck package installations showing perpetual spinner — packages in `pending`/`installing` without an active task are auto-reset to `failed`
- Fix package install retry failing when venv doesn't exist — auto-creates venv before pip install
- Fix E2E test flakiness for explorer run overlay (handle all intermediate dialogs)

### Tests
- 885 backend tests passing (up from 865)
- New tests for browser variant conflict detection, auto-create venv on retry
- E2E test robustness improvements for execution run overlay

## [0.8.0] - 2026-03-23

### Features
- **Visual Flow Editor** — Node-based graphical editor as third tab "Flow" in RobotEditor. Vue Flow with custom nodes: KeywordNode (library calls + arguments), ControlNode (IF/FOR/WHILE/TRY), StartEndNode. MiniMap, Controls, Background Grid, Detail Panel on node click.
- **Flow Editor Keyword Palette** — 5 categories (BuiltIn, Collections, String, Browser, Control), search filter, click-to-add and drag & drop, dynamic loading from rf-mcp libraries and .resource files.
- **Flow Editor UX** — Editable node panel, accordion palette, node reorder & delete, expand/collapse all, select-then-add mode, stable viewport on move.
- **CI/CD Integration (Phase 1)** — API Tokens with SHA256 hash, `rbs_` prefix, role scoping (RUNNER/EDITOR), expiry dates. Auth accepts JWT + API Token. CRUD under `/api/v1/webhooks/tokens`. Frontend: Settings tab "API Tokens".
- **Outbound Webhooks** — HMAC-SHA256 signed (`X-RoboScope-Signature`), 6 events (run.started/passed/failed/error/cancelled/timeout), retry with backoff, test ping, delivery log. Frontend: Settings tab "Webhooks".
- **Git Webhook Trigger** — `POST /api/v1/webhooks/git` accepts GitHub/GitLab push payloads, matches repo via `git_url`, auto-creates ExecutionRun.
- **Audit Log (Phase 2)** — `AuditLog` model with automatic middleware for all POST/PUT/PATCH/DELETE. Admin UI: filterable log, CSV export, manual `audit()` helper.
- **Retention Enforcement** — APScheduler (24h interval) deletes reports/runs older than `report_retention_days`. Dry-run mode, manual trigger via API.
- **Secrets Encryption** — Fernet encryption (derived from SECRET_KEY) for environment variables with `is_secret=True`. Legacy plaintext graceful degradation.
- **Demo Video Recording** — Playwright-based automated demo video generation with overlay text injection, TTS voice-over (OpenAI), EN/DE versions. `DEMO_VIDEO=1 DEMO_LANG=de` env vars.

### Fixes
- Fix Google Fonts CDN links for offline compatibility (#29)
- Fix auth redirect loop in Safari (stale token + HMR reload)
- Fix Flow Editor detail panel stays open on arg add/reorder, viewport stable on move (#28)
- Fix greenlet as explicit dependency for offline package builds
- Fix default environment name and human-readable validation errors
- Fix audit middleware DB writes in daemon thread to avoid event loop blocking

### Security
- Secrets encryption at rest for environment variables (Fernet)
- API Token authentication with SHA256 hashing
- HMAC-SHA256 webhook signatures

### Tests
- 865 backend tests passing (up from 792)
- 267 E2E tests passing
- 113 frontend tests passing
- 34 new tests for API tokens, webhooks, audit log, secrets encryption

### Docs
- In-app documentation updated for API Tokens, Webhooks, Audit Log, Secrets, Flow Editor (EN/DE/FR/ES)
- Demo video scripts and TTS voice-over in EN/DE

## [0.7.0] - 2026-03-12

### Features
- **RobotEditor Visual Improvements** — Section colors, variable highlighting, expand/collapse, lazy keyword loading, vertical args overflow
- **Docker Error Handling** — `DockerNotAvailableError`, `DockerImageNotFoundError` with translated error banners
- **Docker Image Staleness Detection** — `docker_image_built_at`, `packages_changed_at`, computed `docker_image_stale`, amber warnings in Execution + Explorer views
- **Persistent Docker Build Status** — `docker_build_status`/`docker_build_error` on Environment model, server-driven UI
- **Docker Build Terminal Output** — WebSocket-streamed live build logs with terminal component (pulsing dot, auto-scroll, show/hide toggle)
- **Docker Build Robustness** — Playwright base image, pre-build disk space check, large base image hint, dangling image cleanup, enriched Docker error messages
- **Execution View** — Project name column in runs table and detail panel, duration column
- **rfbrowser Init Visibility** — Post-install node_modules verification, pre-run Browser lib check, "initializing" UI status
- **Run Cancellation** — Actually kills spawned subprocess via runner registry pattern; status check after execution prevents overwrite
- **Branch Switching** — `POST /repos/{id}/checkout` endpoint, branch dropdown on project cards
- **Auto-Sync Toggle** — Checkbox on project cards to enable/disable periodic Git sync

### Fixes
- **Report Tree** — Fix `.//tag` XPath finding keyword descendant tags as test tags (now `tags/tag`); fix CSS connector lines (`:first-child` → `:last-child`)
- **Explorer Editor Chain** — Fix v-if/v-else-if chain where no-environment banner blocked RobotEditor from rendering
- **Startup Cleanup** — Reset stuck `docker_build_status=building` → `error` and stuck packages on app start
- **Windows Offline Build** — Fix missing httptools wheels by using separate `requirements-windows.txt` without `uvicorn[standard]` extras (#12)

### Tests
- 136 new backend tests (656 → 792 total) covering previously untested modules:
  - `task_executor.py` (15 tests), `ai/encryption.py` (15 tests), `ai/llm_client.py` (35 tests)
  - `websocket/manager.py` (42 tests), `execution/tasks.py` (21 tests)
  - `repos/service.py` branch functions (8 tests), `repos/router.py` checkout endpoints (13 tests)
- All 267 E2E tests passing

### Docs
- In-app documentation updated for Docker build terminal, image staleness, branch switching, auto-sync, run cancellation, rfbrowser init (EN/DE/FR/ES)

## [0.6.0] - 2026-03-11

### Features
- **RoboView Code Quality KPIs**: 6 new Deep Analysis KPIs integrated from `robotframework-roboview` — keyword reuse rate, unused keywords, keyword duplicates, keyword similarity, documentation coverage, Robocop violations (#11)
- **Private Registry Support**: `index_url` / `extra_index_url` per environment for custom PyPI registries (#6)
- **RF Keyword Library Scan** + SpecEditor help text (#7)
- **Python Version Validation**: normalize patch versions (3.12.5→3.12), reject unsupported versions, warn on pre-release (#5)

### Security
- Remove default SECRET_KEY — require explicit configuration (startup error if unset) (#4)
- Move JWT tokens from URL query params to Authorization headers for report HTML/ZIP endpoints (#4)
- Add optional auth + audit logging on report asset endpoint (#4)
- Add global API rate limiting via slowapi (1000/min default, stricter on expensive endpoints) (#4, #11)
- Add upload size limits: Nginx 500m + FastAPI 500MB check (HTTP 413) (#4)
- Add subprocess resource limits (RLIMIT_AS 2GB) on Linux/macOS (#4)
- Add thread safety to WebSocket manager (lock + copy-iterate pattern) (#4)
- Replace plaintext logging with structured JSON logging (python-json-logger) (#4)
- Add request-ID middleware for log correlation (X-Request-ID header) (#4)
- Add PostgreSQL `pool_recycle` (3600s) to prevent stale connections (#4)

### Fixes
- Hardened private registry: validation, credential masking, migrations (#9)
- Fix interleaved test functions in `environments/test_router.py` from bad merge (#11)
- AI ProviderConfig: curated model dropdowns with current model IDs (#11)
- **Makefile**: `make install` now creates `.venv` automatically; all targets use `.venv/bin/` prefix so the 3-step install works on fresh clones
- CI: set SECRET_KEY for build workflow and dist test scripts

### Tests
- 13 new security E2E tests: API auth, WebSocket auth, request-ID, health check, rate limiting (#11)
- 4 new code quality KPI E2E tests: API + UI for RoboView integration (#11)
- 40 backend tests for RoboView compute functions (#11)

### Docs
- In-app documentation updated for security hardening, code quality KPIs (EN/DE/FR/ES) (#11)
