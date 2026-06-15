# Demo Scenarios — Areas B, C, E, F, G, H, I, J, K

Seed: auto-seeded **Examples** repo + admin login, unless noted. Format:
feature → demo entry → key edge cases. (Areas A and D have dedicated files.)

---

## B. Repos & Git
- **Add repo (git URL / local)** — `/repos` → +New → toggle git/local → save.
  Edge: invalid URL (validation); private SSH (encrypted key); sync conflict.
- **Branch ops** — repo detail → branch dropdown → checkout; commit; publish.
  Edge: local repo limited ops; missing git identity → fallback author.
- **Inbound webhook** — `POST /webhooks/inbound/<token>` with a push payload →
  auto-sync + optional run. Edge: bad HMAC → 403; token is SHA256-hashed.
- **Auto-sync scheduler** — set per-repo interval; observe sync. Edge: skips
  in-flight sync.
- **Library check** — repo row → Library Check → flags missing Browser lib +
  offers install. Capture: `repos.spec.ts`, `git-sync.spec.ts`, `library-check.spec.ts`.

## C. Explorer & Editors
- **File tree** — `/explorer/:repoId` browse/search/create/rename/delete.
  Edge: empty repo; invalid name; binary file; 1000-line file responsive.
- **RobotEditor (Code)** — syntax highlight, undo/redo, keyword autocomplete.
- **FlowEditor (Visual)** — drag keyword nodes, edit params, control nodes
  (if/for/while). Edge: 0 nodes placeholder; 50+ nodes; node-edit isolation
  (cloneStep — typing doesn't tear down the panel); bool-checkbox `name=`
  prefix preserved; read-only for VIEWER.
- **FlowEditor setting-meta side notes** — [Documentation]/[Tags]/[Setup]
  nodes; draft buffer (typing doesn't reset selection); section switch.
- **SpecEditor → AI generation** — Spec tab → write spec → Generate → diff →
  accept/reject. Edge: no provider configured; timeout; reject keeps file.
  Capture: `explorer.spec.ts`, `flow-editor-settings.spec.ts`.

## E. Environments & Packages
- **Create venv (uv)** — `/environments` → +New (name, Python version).
  Edge: invalid Python version; 3.14 prerelease warning.
- **Package install/search** — popular + PyPI search; live progress.
  Edge: 0 results; index_url override; cancel; offline (bundled wheels).
- **Browser + heal provisioning** — install `robotframework-browser-batteries`
  → browsers provisioned (offline: from the bundled browser-pack, no network
  rfbrowser init); heal seeded from the bundled wheel.
- **Docker image build** — Docker dialog → build → live log. Edge: build
  failure log; rebuild stale; cancel mid-build. Capture: `environments.spec.ts`.

## F. Reports & Stats
- **Report list + upload** — `/reports`; upload ZIP. Edge: invalid ZIP; path
  traversal sanitized; 500 MB stream limit.
- **Report detail** — `/reports/:id`: output.xml parse, roboview HTML,
  keyword tree. Edge: 0 tests; all-fail; 1000+ tests; missing-libs banner.
- **Run diagnostic banner** — a Browser run missing chromium shows the
  "playwright browser missing → rfbrowser-init" actionable banner.
- **Stats overview + analysis** — `/stats`: KPI cards, charts; Analysis tab →
  +New Analysis. Edge: 0 runs; analysis in-progress/failed; WS live KPI.
  **Refresh** — toolbar "Aktualisieren" (always) + stale-banner "Jetzt
  aktualisieren" CTA (distinct labels — a11y fix). 
- **Test history / flakiness + quarantine** — `/test-history`; quarantine a
  flaky test → excluded from metrics + skipped at run via listener.
  Capture: `reports.spec.ts`, `report-detail.spec.ts`, `stats.spec.ts`,
  `stats-analysis.spec.ts`, `test-history.spec.ts`, `run-diagnostic-banner.spec.ts`.

## G. AI
- **Provider config** — Settings → AI: OpenAI/Anthropic/OpenRouter/Ollama +
  test connection. Edge: bad key; offline; secret encrypted at rest.
- **rf-mcp keyword discovery** — keyword picker / autocomplete (bundled MCP).
  Capture: `ai-rf-knowledge.spec.ts`, `settings.spec.ts`, `settings-rf-mcp.spec.ts`.

## H. Recorder (v2) — flagship
- **Launch** — `/recordings/new`: transport picker + capability probe. Edge:
  web-viable gating on a headless server (button hidden); 0 repos; reset
  stuck sessions.
- **Live session** — SSE stream, command capture, lifecycle. Edge: stream
  state flips on `open` (not first message); browser crash → restart;
  Stop&Save gated on `saving` only.
- **Capture + selectors** — click/type/scroll/nav; shadow DOM (composedPath
  `host >> inner`); cross-frame `>>>`; selector synthesis + quality scoring +
  parent-context CSS + uniqueness verify; inline SelectorPicker edit/add.
- **Emit** — `.robot` with `${HEADLESS}` var + `*** Variables ***` def, New
  Page `wait_until=domcontentloaded`. Capture: `recorder-lifecycle.spec.ts`
  (backend e2e: `test_v2_recorder_e2e.py`, `-m integration`).

## I. Self-Healing (Heal) — flagship
- **Opt-in `Heal *` keywords** — write `Heal Click` (plain `Click` untouched);
  per-step (HEAL-1) / suite (HEAL-2) toggle in Explorer/FlowEditor.
- **Heal on stale selector** — run with a broken selector → transposition /
  sidecar / fingerprint candidate retried (confidence-gated: mutating 0.7 /
  readonly 0.5; budget max_heals_per_test). Edge: `no-heal` tag disables.
- **Heal report + patch** — run heal report → diff → Copy-patch. Edge:
  suspect-heal (test ultimately failed) → no Copy-patch affordance.
  Capture: `heal-toggle.spec.ts`.

## J. Interactive Debugger — flagship
- **Re-run to error (DEBUG-2)** — Executions → a FAILED run → 🐞 Debug →
  pauses at the failing line; DebugPanel (paused-at, scopes, step/continue/stop).
  Edge: output.xml line extract + fallback; 424 prereq → install dialog;
  dedup 409.
- **Run up to selection (DEBUG-3)** — FlowEditor step → "Bis hier ausführen".
- **RobotCode prereq install (DEBUG-4)** — 424 → install in project venv → retry.
  Capture: `debug-session.spec.ts`.

## K. Cross-cutting & Ops
- **i18n EN/DE/FR/ES** — header language switch; persists. Edge: vue-i18n
  reserved-char escape (prod build gate); missing key fallback.
- **Audit + retention** — `/audit` log of all mutations; CSV export;
  `POST /audit/retention/run`.
- **Secrets encryption** — env var `is_secret` → encrypted at rest (Fernet);
  legacy plaintext still decrypts.
- **Health** — `GET /health` deep DB check (503 on outage).
- **Offline distribution** — offline ZIP boot invariant (no outbound calls);
  optional browser-pack lay-down (shared link across envs).
- **Responsive / a11y** — mobile sidebar; axe scan (Login/SsoError/FirstLogin).
- **Easter egg** — Konami code (opt-in). Capture: `notifications.spec.ts`,
  `responsive.spec.ts`, `phase4-accessibility.spec.ts`, `security-hardening.spec.ts`,
  `imprint.spec.ts`.
