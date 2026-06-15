# RoboScope Demo-Readiness — BMAD Workflow Tracker

**Goal:** Every RoboScope feature must be (1) inventoried, (2) verified working incl. edge cases (QA), (3) fixed at the source where broken (Dev/Architect), (4) demonstrable in isolation with reproducible demo data, and (5) regression-proven via the existing E2E pipeline.

**Method:** BMAD roles per phase — Analyst/PM (inventory), Architect (fit), Dev (fix), QA (verify + edge cases + regression). Work iteratively; status report each pass.

This folder is the persistent artifact. Detailed per-area inventories:
- [`function-inventory-backend.md`](function-inventory-backend.md) — FastAPI domain modules (auth/RBAC, repos/git, explorer, execution, environments, reports, stats, AI, recording, settings, plugins, websocket, audit, health).
- Frontend, Recorder/Heal/Debugger and Ops/Integrations detail captured in the matrix below (source agents run 2026-06-13).

---

## Canonical regression / E2E pipeline (the "existing pipeline" the goal refers to)

| Layer | Command | Approx |
|---|---|---|
| Backend unit | `cd backend && pytest -v --tb=short` (`-m 'not integration'` default) | ~few min – up to ~70 min full |
| Backend integration (real Chromium) | `cd backend && pytest -m integration` (needs `playwright install chromium`) | slow, opt-in |
| Frontend unit | `cd frontend && npm run test:unit -- --run` (vitest) | ~1–2 min |
| Frontend prod build (i18n escape gate) | `cd frontend && npm run build` | ~1 min |
| E2E (Playwright, needs backend :8000 + frontend :5173) | `cd e2e && npx playwright test` (CI=true skips screenshots/video) | ~20 min |
| Shorthand | `make test` (backend+frontend unit) · `make test-e2e` | |

CI mirrors: `.github/workflows/build.yml` (unit matrix 3.12+3.13 + dist builds), `e2e.yml` (full Playwright), `phase4-gates.yml` (5 PR gates incl. axe a11y + full regression).

**Baseline status:** see `baseline-<date>.md` (recorded each regression pass).

---

## Demo-Readiness Matrix

Status legend: ⬜ inventoried · 🔬 QA-verifying · 🐞 bug-found · 🔧 fixed · 🎬 demo-scenario-ready · ✅ done (verified + edge-cases + demo + regression green)

### A. Auth, RBAC & Phase-4 Identity
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Password login + JWT (access/refresh) | `/login` form | rate-limit 10/5min/IP; wrong creds; inactive user; refresh-token-type rejection | ⬜ |
| Token refresh / 401 interceptor / redirect-loop guard | auto on expiry | already-on-`/login` guard; missing `access_token` early-return | ⬜ |
| RBAC VIEWER<RUNNER<EDITOR<ADMIN + per-repo effective roles | gated UI/endpoints | role downgrade mid-session; API-token capped at scoped role | ⬜ |
| API tokens (`rbs_…`, SHA256) | Settings→Tokens | one-time reveal; expiry; revoke; webhook HMAC | ⬜ |
| OIDC/SSO (Azure/Google/GitHub/generic) + dry-run + test-login + handoff | Admin→Identity Providers | bad issuer; JWKS fail; stale dry-run cache; state expiry; IdP outage→`/sso-error` | ⬜ |
| Teams/Org model + group→team mapping + inherited roles | Admin→Teams | 0 teams first-login `/welcome`; import-from-IdP; multi-team switcher | ⬜ |
| Emergency SSO bypass | Admin→Emergency Bypass | activate/expire/deactivate; header banner | ⬜ |
| First-login welcome / SSO link consent | `/welcome`, `/sso-link-consent` | 0 teams; 0 repos; >1 team | ⬜ |
| Change password / forced change | Settings→Security | min-8; same-as-current reject; first-login forced | ⬜ |

### B. Repos & Git
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Add repo (git URL / local path) + clone/sync | `/repos`→+New | invalid URL; SSH key (encrypted); local path; sync conflict | ⬜ |
| Branch list/checkout/commit/publish (push) | repo detail | local-repo limited ops; missing git identity fallback | ⬜ |
| Inbound git webhooks (push/PR → sync+run) | `POST /webhooks/inbound/<token>` | HMAC verify; bad signature 403; token hashed | ⬜ |
| Auto-sync scheduler (APScheduler) | per-repo interval | skip in-flight sync; due-detection | ⬜ |
| Per-repo members + library check + docker image mgmt | repo row actions | missing Browser lib offer-install; bulk delete | ⬜ |

### C. Explorer & Editors
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| File tree browse/search/create/rename/delete | `/explorer/:repoId` | empty repo; invalid name; binary file; large file 1000+ lines | ⬜ |
| RobotEditor (CodeMirror) | Code tab | undo/redo; autocomplete; paste malformed | ⬜ |
| FlowEditor (Vue Flow visual) | Visual tab | 0 nodes; 50+ nodes; node-edit isolation (cloneStep); read-only VIEWER; bool checkbox name= prefix | ⬜ |
| FlowEditor setting-meta side notes ([Documentation]/[Tags]/[Setup]) | side-note nodes | draft buffer (no v-model into form); section switch; 96px pitch clamp | ⬜ |
| SpecEditor → AI test generation | Spec tab | no provider configured; timeout; reject/accept diff | ⬜ |
| Pre-run gates (library check, docker staleness, save-before-run) | Run button | VIEWER disabled; no-env banner; dirty prompt | ⬜ |

### D. Execution & Scheduling
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Run test (subprocess runner) + live output (WS) | `/runs`→Run | long run; live stream reconnect; output 1000+ lines | ⬜ |
| Docker runner | runner_type=docker | daemon unavailable graceful; image pull; volume map; timeout | ⬜ |
| Cancel run | Cancel in panel | cancel reason recorded; mid-run teardown | ⬜ |
| Retry / rerun-failed | Retry CTA | — | ⬜ |
| Schedules (cron) + CronEditor | Schedules tab | invalid cron; timezone; enable/disable; next-run calc | ⬜ |
| Retention scheduler (24h) | `POST /audit/retention/run` | reports/runs older than N deleted | ⬜ |
| TaskExecutor (in-proc ThreadPool, single worker) | bg dispatch | db.commit-before-dispatch; FK model imports; dedup stuck tasks | ⬜ |

### E. Environments & Packages
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Create venv (uv) + Python version validate | `/environments`→+New | invalid py version; prerelease warning 3.14 | ⬜ |
| Package install/search (popular + PyPI) + progress | Packages dialog | 0 results; index_url/extra_index_url; cancel; offline | ⬜ |
| Browser-library + heal provisioning (incl. offline browser-pack) | install browser-batteries | rfbrowser init network; offline pack lay-down; batteries provisioning; heal seed from wheel | ⬜ (see `feat/offline-browser-pack`) |
| Docker image build + live log | Docker dialog | build fail log; rebuild stale; cancel mid-build | ⬜ |

### F. Reports & Stats
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Report list + upload ZIP + delete | `/reports` | invalid ZIP; path traversal; 500MB stream limit; large upload | ⬜ |
| Report detail (output.xml parse, roboview HTML, keyword tree) | `/reports/:id` | 0 tests; all-fail; 1000+ tests; missing libs banner | ⬜ |
| Report assets auth (HMAC `?at=` or JWT) | embedded assets | token expiry; unauth 403 | ⬜ |
| Run diagnostics (playwright-browser-missing → rfbrowser-init action) | report banner | subprocess+env_id gating | ⬜ |
| Stats overview (KPIs, charts) + analysis builder | `/stats` | 0 runs; analysis in-progress/failed; large date range; WS live KPI | ⬜ |
| Test history / flakiness + quarantine | `/test-history` | flaky highlight; quarantine hides from metrics | ⬜ |
| Export CSV/JSON/PDF | export actions | (Phase 5 — verify what exists: audit CSV, reportlab PDF) | ⬜ |

### G. AI
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| LLM provider config (OpenAI/Anthropic/OpenRouter/Ollama) + test connection | Settings→AI | bad key; offline; encrypted secret at rest | ⬜ |
| Spec → test generation + diff accept/reject | SpecEditor | timeout; malformed output; reject keeps file | ⬜ |
| rf-mcp keyword discovery (bundled) | keyword picker | bundled vs custom venv; library search order | ⬜ |

### H. Recorder (v2)
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Launcher + transport picker + capability probe | `/recordings/new` | web-viable gating (headless server); 0 repos; reset stuck sessions | ⬜ |
| Live session (SSE stream, command capture, lifecycle) | `/recordings/live/:id` | open-event state flip; browser crash→restart; stop-save abort; large list | ⬜ |
| Capture (click/type/scroll/nav/drag) + shadow DOM (composedPath) | interact w/ page | shadow host retarget; cross-frame `>>>`; Enter-only keypress; nav debounce | ⬜ |
| Selector synthesis + quality scoring + parent-context CSS + uniqueness verify | step picker | strict-mode multi-match; autogen-class detection; nth-match fallback; iframe inventory | ⬜ |
| SelectorPicker (inline edit/add custom) | step badge | legacy pw_locator hidden; draft buffer; effective_override | ⬜ |
| Emit `.robot` (`${HEADLESS}` var + def, New Page `wait_until=domcontentloaded`) | result view | missing var def → RF error; `load` timeout on ad-heavy pages | ⬜ |
| Save flow + sidecar `.rbs.json` (idmap `# rbs:<id>`) | Stop&Save | discard guard; path default `flows/`; reorder survival | ⬜ |

### I. Self-Healing (Heal)
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| Opt-in `Heal *` keywords (per-keyword consent) | write `Heal Click` | plain Click untouched; `no-heal` tag escape | ⬜ |
| Candidate strategies (transposition/sidecar/fingerprint) + confidence | run w/ stale selector | mutating 0.7 / readonly 0.5 threshold gate | ⬜ |
| Budgets (max_heals_per_test, per-call retry=1) | repeated heals | budget exhaustion re-raise | ⬜ |
| Heal report + diff + Copy-patch (suspect-heal gating) | run heal report | failed-test heal NOT copyable; patch to disk + audit | ⬜ |
| Heal toggle UI (per-step HEAL-1 / suite HEAL-2) | Explorer/FlowEditor | suite-on+step-off override; backward compat | ⬜ |
| Heal-rate KPI | `/stats/heal-rate` | patch-acceptance aggregation | ⬜ |

### J. Interactive Debugger
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| RobotCode DAP driver (spawn, handshake, events) | internal | ephemeral port; `-w` wait; process-per-session reap; no Chromium/Node leak | ⬜ |
| Re-run to terminating error (DEBUG-2) | 🐞 Debug on failed run | output.xml line extract; fallback first-exec line; 424 prereq; dedup 409 | ⬜ |
| Run-up-to-selection (DEBUG-3) | "Bis hier ausführen" | step line roundtrip; test-boundary reject; repo default env | ⬜ |
| DebugPanel (paused-at, scopes, step/continue/stop) | panel | scope expand; var truncate; terminated disables; minimize vs stop | ⬜ |
| RobotCode prereq install dialog (DEBUG-4) | 424 → install | install in project venv; retry after; dedup | ⬜ |
| Breakpoint resolution (DEBUG-5) | breakpoints | robot/sync auto-ack | ⬜ |

### K. Cross-cutting & Ops
| Feature | Demo entry | Key edge cases | Status |
|---|---|---|---|
| i18n EN/DE/FR/ES (incl. in-app docs) | language switch | vue-i18n reserved-char escape (prod build); missing key fallback | ⬜ |
| Audit middleware (all mutations logged) | `/audit` | user/IP/detail; CSV export; retention | ⬜ |
| Secrets encryption (Fernet) | env vars is_secret | legacy plaintext graceful decrypt | ⬜ |
| WebSocket broadcasts (run status, package, analysis) | live UI | bg-thread `run_coroutine_threadsafe`; no asyncio.run | ⬜ |
| Health (deep DB SELECT 1) | `GET /health` | 503 on DB outage | ⬜ |
| UTC datetime normalization | API datetimes | naive ISO → `Z`; `parseBackendDate` | ⬜ |
| Offline distribution (5 ZIPs + browser-pack) + online ZIP | build scripts | offline boot invariant (no outbound); browser-pack lay-down | ⬜ |
| Docker images (backend/frontend/playwright) + compose | `make docker-up` | daemon availability | ⬜ |
| Responsive / a11y (axe) | mobile + keyboard | sidebar toggle; focus trap; ARIA (known gaps) | ⬜ |
| Easter egg (Konami) | konami code | opt-in fun | ⬜ |

---

## Demo asset plan
Reproducible per-feature demo scenarios + seed data live under `_bmad-output/planning-artifacts/demo-readiness/scenarios/` (created per feature as QA progresses). The Playwright `take-demo-video.spec.ts` / `take-screenshots.spec.ts` specs are the media-capture harness (skipped in CI, run locally).

## Iteration log
Each pass appends: BMAD role · feature(s) touched · what was verified · bugs found/fixed · regression result. See `iteration-log.md`.
