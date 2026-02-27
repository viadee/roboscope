# RoboScope — Claude Code Projektdokumentation

Webbasiertes Robot Framework Test-Management-Tool mit Git-Integration, GUI-Ausführung, Report-Analyse, Environment-Management und Container-Runtime.

## Aktueller Projektstatus (Stand: 2026-02-24)

### Was ist implementiert

**Backend (FastAPI) — VOLLSTÄNDIG implementiert (~5.800 Zeilen)**
- Auth/JWT mit RBAC (Viewer < Runner < Editor < Admin) + Admin-Passwort-Reset
- Repository-Management mit GitPython (clone, sync, branches), Projekt-Umgebungszuordnung
- Testfall-Explorer (Dateisystem-Browser + Robot-Parser + Library-Check + "In Dateibrowser öffnen" + Binärdatei-Erkennung)
- Testausführung: SubprocessRunner + DockerRunner + In-Process TaskExecutor + WebSocket-Live-Updates
- Environment-Management (uv + venv, Pakete, Variablen)
- Report-Parsing (output.xml → DB) + Vergleich
- KPI/Statistik-Service (Trends, Flaky Detection, Heatmaps) + On-Demand Tiefenanalyse (15 KPIs in 5 Kategorien) + Refresh/Staleness
- Settings (Key-Value, Admin-only)
- Plugin-System (Registry + Console-Logger Builtin)
- WebSocket Connection Manager (Live-Updates bei Run-Status-Änderungen)
- Alembic Migrationen (SQLite + PostgreSQL)
- Bulk-Operationen: Cancel all runs (RUNNER+), Delete all reports (ADMIN)
- Seed: Default-Admin + "Examples"-Projekt beim ersten Start
- AI-Modul: LLM-gestützte .roboscope ↔ .robot Generierung + KI-Fehleranalyse für Reports (OpenAI, Anthropic, OpenRouter, Ollama)

**Frontend (Vue 3 + TypeScript) — VOLLSTÄNDIG implementiert (~5.500 Zeilen)**
- 12 Views: Login, Dashboard, Repos, Explorer, Execution, Environments, Reports, ReportDetail, Stats, Settings, Docs, Imprint
- In-App-Dokumentation: DocsView mit TOC-Sidebar, Suche, Print/PDF, i18n (EN, DE, FR, ES), offline-fähig
- 9 Pinia Stores: auth, repos, explorer, execution, environments, reports, stats, ui, ai
- 9 API-Clients: auth, repos, explorer, execution, environments, reports, stats, settings, ai
- 5 Base UI-Komponenten: BaseButton, BaseBadge, BaseModal, BaseToast, BaseSpinner
- 2 Layout-Komponenten: AppHeader, AppSidebar
- 2 Layouts: DefaultLayout (Sidebar+Header+Footer), AuthLayout (Login)
- 2 Composables: useWebSocket, useToast
- i18n: vollständig in 4 Sprachen (EN, DE, FR, ES)
- Vue Router mit rollenbasierten Guards
- TypeScript Domain + API Types
- Footer: Copyright, viadee.de Link, Impressum
- Execution-Tabelle: Environment-Spalte, Retry-Button, Explorer-Link, Spinner bei aktiven Runs

**E2E Tests (Playwright) — UMFASSEND (~1.400 Zeilen)**
- 13 Test-Specs: auth, dashboard, navigation, repos, execution, environments, reports, settings, stats, stats-analysis, imprint, password-reset, repo-environment
- Page Objects: LoginPage, DashboardPage, SidebarNav
- Auth-Fixture mit JWT-Injection
- API-Mocking via page.route()

**Backend Tests (pytest) — ~555 Tests**
- Auth: Login, Registration, Password-Reset (5 Tests)
- Repos: CRUD, Service (20+ Tests)
- Explorer: File-Browser, Open-In-File-Browser, Binary-Detection (11 Tests)
- Execution: Runs, Scheduling (20+ Tests)
- Environments: CRUD, Packages, venv_utils (14 Tests), Tasks (7 Tests) (40+ Tests)
- Reports: Parsing, Comparison (20+ Tests)
- Stats: Overview, Aggregate, Data-Status (7 Tests)
- Stats Analysis: Compute-Funktionen, KPI-Validation, Broadcast-Helper, Date-Filtering (26 Tests)
- Settings: CRUD, Permissions (10+ Tests)
- AI: rf-mcp Manager (31 Tests)

**Docker — VOLLSTÄNDIG konfiguriert**
- 3 Dockerfiles: backend, frontend, playwright
- 3 Compose-Files: production (PostgreSQL+Nginx), dev (SQLite), test

**Build/Distribution**
- `scripts/build-mac-and-linux.sh` — Erstellt standalone ZIP-Archiv für Offline-Deployment (Windows, Mac, Linux)
- Enthält: Frontend-Build, Backend-Source, Python-Wheels, uv-Binaries (alle Plattformen), Install/Start-Skripte

### Wichtige Architekturentscheidung: Task-Ausführung

**Celery + Redis wurde komplett entfernt** und durch einen in-process `ThreadPoolExecutor(max_workers=1)` ersetzt.

Warum:
- Kein externer Redis/Celery-Worker nötig — einfachere Entwicklung und Deployment
- Alle Hintergrundaufgaben (Test-Runs, Git-Clone/Sync, Report-Parsing, Package-Ops) laufen über `dispatch_task()`
- `max_workers=1` stellt sicher, dass nur 1 Testlauf gleichzeitig läuft (Tasks werden in FIFO-Queue gereiht)
- Fehlerbehandlung: Wenn ein Task nicht gestartet werden kann, wird `TaskDispatchError` geworfen und der Run bekommt `status=ERROR` mit sichtbarer Fehlermeldung

Schlüsseldatei: `backend/src/task_executor.py` — enthält `dispatch_task()`, `TaskDispatchError`, `TaskResult`

**Wichtig**: Vor `dispatch_task()` muss immer `db.commit()` aufgerufen werden, damit der Background-Thread die Daten in einer separaten DB-Session sehen kann.

### Aktuelle Arbeit / Nächste Schritte

**Fertiggestellt:**
- [x] Task-Executor (ThreadPoolExecutor statt Celery)
- [x] "Alle abbrechen" Button auf Execution-Seite (POST /runs/cancel-all, nur für RUNNER+)
- [x] "Alle löschen" Button auf Reports-Seite (DELETE /reports/all, nur für ADMIN, mit Bestätigungsdialog)
- [x] Error-Handling: Fehlgeschlagene Dispatches → Run-Status ERROR + sichtbare Fehlermeldung
- [x] E2E Tests für Execution (7/7 bestanden)
- [x] In-App-Dokumentation (DocsView, EN+DE+FR+ES, TOC, Suche, Print/PDF, offline-fähig)
- [x] Package Manager & Library Check (Nav umbenannt, Library-Scanner, Repo-Environment-Zuordnung, One-Click-Install)
- [x] On-Demand Tiefenanalyse-Modul (15 KPIs in 5 Kategorien: Keyword Analytics, Test Quality, Maintenance, Source Analysis, Execution)
- [x] i18n für gesamte Anwendung (DE, EN, FR, ES)
- [x] Stats: KPI-Aggregation Fix, Refresh-Button, Staleness-Banner, Chart-Achsen (Y: 0-100%, X: Datum)
- [x] Deep Analysis: Default all KPIs + 30-Tage-Zeitraum
- [x] Rename Repository → Projekt in UI
- [x] Projekt-Umgebungsauswahl: Inline-Dropdown auf Projektkarten, Default-Umgebung in Add-Dialog
- [x] "In Dateibrowser öffnen" Button (Explorer, localhost-only)
- [x] "Absoluter Pfad" Anzeige (Explorer, localhost-only)
- [x] Admin Passwort-Reset (Settings > Benutzer)
- [x] Footer + Impressum-Seite (viadee Unternehmensberatung AG)
- [x] Examples-Projekt: 5 Beispiel-Robot-Dateien, automatisches Seeding beim Start
- [x] WebSocket-Live-Updates für Run-Status-Änderungen (running → passed/failed)
- [x] Execution-Tabelle: Umgebungs-Spalte, Retry-Icon, Explorer-Link, Spinner bei aktiven Runs
- [x] Umfassende Backend-Tests (Auth-Passwort-Reset, Stats-Aggregate, Explorer-Open-In-Browser)
- [x] Umfassende E2E-Tests (Imprint, Passwort-Reset, Repo-Umgebung, Stats-Tabs)
- [x] In-App-Dokumentation aktualisiert (EN+DE+FR+ES: Passwort-Reset, Umgebungsauswahl, Stats-Refresh, Impressum, Detailed Report Tab)
- [x] Build-Skript aktualisiert (examples/ Verzeichnis, .env ohne Celery)
- [x] Explorer: Testanzahl-Fix (build_tree test_count) + E2E-Tests + "Projektordner öffnen" Button
- [x] Tiefenanalyse: Bibliotheksverteilung Fix (Keyword-zu-Library-Mapping für 500+ Keywords)
- [x] Tiefenanalyse: Quellcode-Analyse KPIs (source_test_stats, source_library_distribution)
- [x] greenlet>=3.1.0 als explizite Dependency (Windows/Python 3.13 Kompatibilität)
- [x] fix: HTML Report Fragment-Navigation 404 + iframe Toolbar (Back/Reload)
- [x] AI-Modul: .roboscope Spec ↔ .robot Generierung (LLM-Anbindung, Drift-Erkennung, Provider-Management)
- [x] SpecEditor: Visueller Editor für .roboscope Dateien (Dual-Tab: Visual Form + YAML, Collapsible Sections, Library-Autocomplete aus Environment-Paketen)
- [x] ProviderConfig: Modell-Dropdown mit kuratierten Modelllisten pro Anbieter, aktualisierte Default-Modelle
- [x] LLM-Client: API-Antwort-Body in Fehlermeldungen, Anthropic-Temperature-Clamping (0.0–1.0)
- [x] ExplorerView: v-if/v-else-Chain-Fix (kein doppeltes Rendering bei .roboscope Dateien)
- [x] Deep Analysis: 3 Bug-Fixes (WebSocket asyncio.run→run_coroutine_threadsafe, Date-Filtering str→datetime.combine, KPI-Validation 422)
- [x] Deep Analysis: 5 neue Execution-KPIs (test_pass_rate_trend, slowest_tests, flakiness_score, failure_heatmap, suite_duration_treemap)
- [x] Deep Analysis: Frontend-Visualisierungen (CSS Stacked Bars, Horizontal Bars, Dot Timeline, Heatmap Grid, Treemap)
- [x] Deep Analysis: Backend-Tests (26 Tests) + E2E-Tests (8 Tests)
- [x] Explorer: Binärdatei-Erkennung (Null-Byte-Check, `is_binary` Flag, `force` Query-Param, Placeholder + "Trotzdem öffnen" Button, i18n EN/DE/FR/ES, Backend+Router+E2E Tests)
- [x] AI-Fehleranalyse: LLM-gestützte Root-Cause-Analyse für fehlgeschlagene Tests (POST /ai/analyze, run_analyze Task, ReportDetailView-Integration, E2E-Tests)
- [x] Explorer: Fix falscher "Unsaved"-Badge beim Öffnen (ignoreContentUpdates Flag verhindert isDirty durch Editor-Roundtrip-Normalisierung bei RobotEditor/SpecEditor mount)
- [x] Explorer: Save-Before-Run Prompt (bei unsaved Changes wird der User gefragt ob speichern vor Ausführung, i18n EN/DE/FR/ES, 5 neue E2E-Tests)
- [x] Dependabot: minimatch ReDoS-Vulnerability behoben (npm override minimatch>=10.2.1, editorconfig>=2.0.0)
- [x] **uv-Migration**: pip/venv → uv für alle Package-Management-Operationen (venv_utils.py, cross-platform, 21 neue Tests, CI/Docker/Build-Skripte aktualisiert)
- [x] E2E-Fixes: Selector-Ambiguity in `notifications.spec.ts` (`.notification-btn:not(.tour-btn)`) und `scheduling.spec.ts` (`getByText` statt `.text-muted.text-center`) — alle 217 E2E-Tests grün

**Offen / Roadmap (priorisiert):**
- [x] **Responsive Design** — Sidebar, Tabellen, iframe-Layout für kleinere Bildschirme optimieren
- [x] **Test-Ergebnis-Historie pro Testfall** — Klick auf einzelnen Test zeigt Pass/Fail-Verlauf über Zeit (hilfreich für Flaky-Debugging)
- [x] **Benachrichtigungen** — Browser-Notifications bei Testlauf-Abschluss; optional Slack/Email-Integration bei Fehlschlägen
- [x] **Scheduling UX** — Cron-artiges Scheduling mit visuellem Editor im Frontend prominenter machen
- [x] **Benutzer-/Projekt-Scoping** — Projekt-Level-Berechtigungen / Multi-Tenancy für wachsende Teams
- [ ] **Visueller Editor für .robot/.resource Dateien** — Strukturierter Form-Editor (Settings, Variables, Test Cases, Keywords) analog zum .roboscope SpecEditor
- [ ] **Offline-Archiv-Analyse** — Upload alter Report-ZIPs zur Analyse ohne Git-Repo/Environment
- [ ] **UI-Verfeinerungen** — Allgemeine Polish-Runde (Ladeanimationen, Error-States, leere Zustände)

## Architektur

```
RoboScope/
├── backend/          # FastAPI (Python 3.12+)
│   ├── src/          # Applikations-Code (Domain-Driven)
│   │   ├── auth/     # JWT-Auth + RBAC (Viewer < Runner < Editor < Admin)
│   │   ├── repos/    # Git-Repository-Verwaltung (GitPython)
│   │   ├── explorer/ # Dateisystem-Browser + Robot-Parser
│   │   ├── execution/# Test-Runs + Scheduling (Subprocess + Docker Runner)
│   │   ├── environments/ # uv + venv + Pakete + Variablen (venv_utils.py)
│   │   ├── reports/  # output.xml Parser + Vergleich
│   │   ├── stats/    # KPI Dashboard, Flaky Detection, Heatmap, On-Demand Tiefenanalyse
│   │   ├── ai/       # LLM-gestützte .roboscope ↔ .robot Generierung + Fehleranalyse
│   │   ├── settings/ # Key-Value App-Settings (Admin)
│   │   ├── plugins/  # Plugin-System (Analyzer, Runner, Integration, KPI)
│   │   ├── websocket/# WebSocket Connection Manager
│   │   ├── api/v1/   # Router-Aggregation
│   │   ├── config.py # Pydantic Settings (.env)
│   │   ├── database.py # SQLAlchemy sync + TimestampMixin
│   │   ├── task_executor.py # In-Process TaskExecutor (ThreadPoolExecutor)
│   │   └── main.py   # FastAPI App Factory + Lifespan
│   ├── tests/        # pytest Tests
│   ├── migrations/   # Alembic (SQLite + PostgreSQL)
│   └── pyproject.toml
├── frontend/         # Vue 3 + TypeScript + Vite
│   └── src/
│       ├── api/      # Axios API-Client mit JWT-Interceptor
│       ├── docs/     # In-App-Dokumentation (types, content/en, content/de, content/fr, content/es)
│       ├── stores/   # Pinia Stores (auth, repos, explorer, execution, ...)
│       ├── views/    # 12 Views (Login, Dashboard, Repos, Explorer, ...)
│       ├── components/ # UI-Basiskomponenten + Layout
│       ├── composables/ # useWebSocket, useToast
│       ├── router/   # Vue Router mit rollenbasierten Guards
│       └── types/    # TypeScript Domain + API Types
├── e2e/              # Playwright E2E-Tests
│   ├── page-objects/ # LoginPage, DashboardPage, SidebarNav
│   ├── fixtures/     # Auth-Fixture mit Token-Injection
│   └── tests/        # auth, navigation, repos, execution, environments, reports, settings, stats, stats-analysis, imprint, password-reset, repo-environment
├── docker/           # Dockerfiles (backend, frontend, playwright)
├── docker-compose.yml      # Production (PostgreSQL + Nginx)
├── docker-compose.dev.yml  # Development (SQLite)
├── docker-compose.test.yml # Test-Umgebung
└── Makefile          # Alle Befehle
```

## Design-System (RoboScope Branding)

### Farben (CSS Custom Properties in main.css)
```css
--color-primary: #3B7DD8      /* Steel Blue — RoboScope Hauptfarbe */
--color-accent: #D4883E       /* Amber — Akzentfarbe */
--color-navy: #1A2D50         /* Navy — Sidebar/Dark Areas (Logo-Farbe) */
--color-navy-dark: #0F1A30    /* Dunkleres Navy */
--color-bg: #F4F7FA           /* Seiten-Hintergrund */
--color-bg-card: #ffffff      /* Karten-Hintergrund */
--color-text: #1A1D2E         /* Haupttext */
--color-text-muted: #5A6380   /* Sekundärtext */
```

### Komponenten-Styling
- **Buttons**: 4 Varianten (primary/secondary/danger/ghost), 3 Größen (sm/md/lg)
- **Badges**: Status-Badges (passed/failed/running/pending/error/cancelled/timeout/skip)
- **Cards**: Weiß, 1px Border, Radius 10px, Shadow, Hover-Effekt
- **Tables**: .data-table mit uppercase Headers und Hover-Zeilen
- **Forms**: .form-input mit Teal Focus-Ring
- **Modal**: Teleport to body, Backdrop-Blur, Escape/Click-Outside close
- **Toast**: 4 Typen (success/error/warning/info), farbige Left-Border

### Layout-Maße
- Sidebar: 250px (collapsed: 60px)
- Header: 56px
- Border-Radius: 6px (sm), 10px (md), 14px (lg)
- Shadows: 3 Stufen (sm/md/lg)

## Tech-Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, ThreadPoolExecutor (Background Tasks), GitPython, Docker SDK
- **Package Management**: [uv](https://docs.astral.sh/uv/) (ersetzt pip/venv — schneller, cross-platform, kein `venv`-Modul nötig)
- **Frontend**: Vue 3.5, Pinia, Vue Router 4, Axios, Chart.js, CodeMirror 6, js-yaml, TypeScript, Vite
- **Datenbank**: SQLite (Standard/Dev) oder PostgreSQL (Production), konfigurierbar via `DATABASE_URL`
- **Tests**: pytest, Vitest + @vue/test-utils, Playwright
- **Kein Redis/Celery nötig** — alle Background-Tasks laufen in-process via ThreadPoolExecutor

## API-Endpunkte

Alle unter `/api/v1/`:

| Prefix | Modul | Auth |
|--------|-------|------|
| `/auth` | Login, Refresh, User-CRUD | Teilweise |
| `/repos` | Repository CRUD + Git Sync | EDITOR+ für Schreibops |
| `/explorer/{repo_id}` | Dateibaum, Suche, Testcases, Library-Check | Authentifiziert |
| `/runs` + `/schedules` | Ausführung + Scheduling | RUNNER+ / EDITOR+ |
| `/runs/cancel-all` | Alle laufenden Runs abbrechen | RUNNER+ |
| `/environments` | Umgebungen, Pakete, Variablen | EDITOR+ für Schreibops |
| `/reports` | Reports, Vergleich, HTML-Export | Authentifiziert |
| `/reports/all` (DELETE) | Alle Reports löschen | ADMIN |
| `/stats` | KPIs, Trends, Flaky, Heatmap | Authentifiziert |
| `/stats/analysis` | On-Demand Tiefenanalyse (CRUD + KPI-Metadaten) | RUNNER+ für POST, sonst Auth |
| `/settings` | App-Settings | ADMIN only |
| `/ai` | LLM-Provider CRUD, Spec→Robot Generierung, Robot→Spec Reverse, Drift-Erkennung, Fehleranalyse | EDITOR+ (Analyze: Auth) |

Swagger UI: `http://localhost:8000/api/v1/docs`

## Rollen-Hierarchie

`VIEWER (0) < RUNNER (1) < EDITOR (2) < ADMIN (3)` — definiert in `backend/src/auth/constants.py`

## Entwicklung starten

### Voraussetzungen

- Python 3.12+, Node.js 20+, [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Kein Redis nötig (Background-Tasks laufen in-process)

### Lokale Entwicklung

```bash
make install            # Dependencies installieren
cp backend/.env.example backend/.env
make dev                # Backend :8000 + Frontend :5173
make backend            # nur Backend
make frontend           # nur Frontend
```

Backend manuell starten:
```bash
cd RoboScope/backend && .venv/bin/python -m uvicorn src.main:app --reload --port 8000
```

Frontend manuell starten:
```bash
cd RoboScope/frontend && npm run dev
```

### Mit Docker

```bash
make docker-dev         # SQLite (dev)
make docker-up          # PostgreSQL + Nginx (prod)
make docker-down        # Stoppen
make docker-logs        # Logs anzeigen
```

## Testen

```bash
make test-backend       # Backend-Tests (pytest)
make test-backend-cov   # Mit Coverage
make test-frontend      # Frontend-Tests (Vitest)
make test-frontend-cov  # Mit Coverage
make test-e2e           # Playwright E2E
make test               # Backend + Frontend
make lint               # Ruff + ESLint + vue-tsc
make format             # Auto-Format
make typecheck          # mypy + vue-tsc
```

E2E Tests manuell starten:
```bash
cd RoboScope/e2e && npx playwright test
cd RoboScope/e2e && npx playwright test tests/execution-run.spec.ts  # einzelner Spec
```

- **Backend**: pytest, In-Memory SQLite, transaktionaler Rollback
- **Fixtures**: `db_session`, `client` (TestClient), `admin_user`, `runner_user`, `viewer_user`, `auth_header(user)`
- **Frontend**: Vitest, `describe/it/expect`, Pinia mit `createPinia`/`setActivePinia`
- **E2E**: Playwright, Page Objects, Auth-Fixture mit JWT-Injection, API-Mocking via `page.route()`
- **E2E CI-Ausschluss**: `take-screenshots.spec.ts` wird in GitHub Actions automatisch übersprungen (`testIgnore` in `playwright.config.ts` wenn `CI=true`). Lokal werden alle Specs inklusive Screenshots ausgeführt.

## Datenbank-Migrationen

```bash
make db-migrate msg="Add new column"
make db-upgrade
make db-downgrade
```

## Wichtige Konfiguration

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `DATABASE_URL` | `sqlite:///./roboscope.db` | DB-Connection |
| `SECRET_KEY` | dev-key | JWT-Secret |
| `RUNNER_TYPE` | `auto` | `subprocess`, `docker`, `auto` |
| `DOCKER_AVAILABLE` | `false` | Docker-Runner aktivieren |
| `DEFAULT_TIMEOUT_SECONDS` | `3600` | Timeout pro Run |
| `LOG_LEVEL` | `INFO` | Logging-Level |
| `WORKSPACE_DIR` | `~/.roboscope/workspace` | Git-Repos Arbeitsverzeichnis |
| `REPORTS_DIR` | `~/.roboscope/reports` | Report-Dateien Verzeichnis |
| `VENVS_DIR` | `~/.roboscope/venvs` | Virtuelle Environments |
| `UV_PATH` | `""` (auto-detect) | Expliziter Pfad zur uv-Binary |

## Bekannte Patterns und Gotchas

### DB Commit vor dispatch_task()
Background-Tasks laufen in separaten Threads mit eigener sync DB-Session. Die SQLAlchemy-Session im FastAPI-Request committed erst nach dem Handler-Return. Deshalb **muss immer `db.commit()` VOR `dispatch_task()` aufgerufen werden**, damit der Background-Thread die Daten sieht.

### SQLAlchemy Model Imports für Foreign Keys
Wenn ein Task-Modul Models mit Foreign Keys importiert (z.B. `ExecutionRun.triggered_by → users.id`), müssen ALLE referenzierten Models vorher importiert sein. In jedem `tasks.py`:
```python
import src.auth.models    # noqa: F401 — FK resolution
import src.repos.models   # noqa: F401 — FK resolution
```

### Task-Ausführung (task_executor.py)
`backend/src/task_executor.py` stellt bereit:
- `dispatch_task(func, *args, **kwargs) -> TaskResult` — Queued Task-Submission
- `TaskDispatchError` — Exception wenn Submit fehlschlägt
- `TaskResult` — Objekt mit `.id` (UUID)
- `_executor` — ThreadPoolExecutor(max_workers=1)

### Package Management mit uv (venv_utils.py)
Alle pip/venv-Operationen laufen über `uv` statt nativem `pip`/`python -m venv`. Dies löst Probleme mit portablen/embedded Python-Installationen (Windows), die kein `venv`-Modul haben.

**Zentrales Modul:** `backend/src/environments/venv_utils.py` — konsolidiert alle venv-Pfad-Utilities und uv-Kommando-Builder:
- `get_uv_path()` — Findet uv-Binary (Settings → PATH → Fehler)
- `get_python_path(venv_path)` — Cross-platform: `bin/python` (Unix) vs `Scripts/python.exe` (Windows)
- `get_venv_bin_dir(venv_path)` — Cross-platform: `bin/` vs `Scripts/`
- `create_venv_cmd()` → `[uv, venv, path, --python, version]`
- `pip_install_cmd()` → `[uv, pip, install, --python, python_path, packages...]`
- `pip_uninstall_cmd()`, `pip_show_cmd()`, `pip_list_cmd()` — analog

**Wichtig:** uv ist eine externe CLI-Binary, **kein** Python-Paket. Es wird via `subprocess.run()` aufgerufen. Die Konfiguration `UV_PATH` in `config.py` erlaubt einen expliziten Pfad; bei leerem String wird `shutil.which("uv")` verwendet.

**Betroffene Module (alle importieren aus `venv_utils`):**
- `environments/tasks.py` — venv-Erstellung, Package install/upgrade/uninstall
- `environments/service.py` — `pip_list_installed()`, `generate_dockerfile()`, `docker_pip_list()`
- `execution/runners/subprocess_runner.py` — venv-Erstellung, Package-Installation, PATH-Setup
- `ai/rf_mcp_manager.py` — rf-mcp Installation, Server-Start mit korrektem PATH

**Docker:** Dockerfiles verwenden `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv` und `uv pip install --system`.

**CI:** GitHub Actions verwenden `astral-sh/setup-uv@v5` und `uv pip install --system -e ".[dev]"`.

**Build-Skripte:** Offline-Build bündelt uv-Binaries für Linux/Mac/Windows; Online-Build installiert uv automatisch via `curl`.

### Library Check (Package Manager)
Der Explorer-Router bietet einen `GET /explorer/{repo_id}/library-check?environment_id={id}` Endpoint:
- Scannt alle `.robot`/`.resource`-Dateien nach `Library`-Imports in `*** Settings ***`
- Vergleicht mit installierten Paketen via `uv pip list` aus der gewählten Umgebung
- Mapping: `backend/src/explorer/library_mapping.py` (Built-in-Erkennung + PyPI-Mapping + Heuristik)
- Repos haben ein optionales `environment_id` FK-Feld (Standard-Umgebung für Library-Checks)
- Nav-Label "Environments" wurde zu "Package Manager" umbenannt (i18n: EN/DE/FR/ES)

### On-Demand Tiefenanalyse (Stats-Modul)
Das Stats-Modul wurde um eine asynchrone Tiefenanalyse erweitert. Benutzer wählen KPIs aus, starten eine Analyse, und Ergebnisse werden als JSON-Blob gespeichert.

**Dateien:**
- `backend/src/stats/models.py` — `AnalysisReport` Model (status, selected_kpis, results JSON, progress)
- `backend/src/stats/schemas.py` — `AnalysisCreate`, `AnalysisResponse`, `AnalysisListResponse`, `AVAILABLE_KPIS`
- `backend/src/stats/analysis.py` — Kernmodul: 13 Compute-Funktionen + `run_analysis()` Orchestrator (sync, für Background-Thread)
- `backend/src/stats/service.py` — CRUD: `create_analysis()`, `get_analysis()`, `list_analyses()`
- `backend/src/stats/router.py` — 4 neue Endpoints: `POST /analysis`, `GET /analysis`, `GET /analysis/{id}`, `GET /analysis/kpis`

**15 KPIs in 5 Kategorien:**
- **Keyword Analytics**: keyword_frequency, keyword_duration_impact, library_distribution
- **Test Quality**: test_complexity, assertion_density, tag_coverage
- **Maintenance**: error_patterns, redundancy_detection
- **Source Analysis**: source_test_stats, source_library_distribution (analysiert .robot-Quelldateien direkt)
- **Execution**: test_pass_rate_trend, slowest_tests, flakiness_score, failure_heatmap, suite_duration_treemap (DB-basiert, queries TestResult/ExecutionRun direkt)

**Ablauf:**
1. Frontend sendet `POST /stats/analysis` mit `selected_kpis[]`
2. Backend erstellt `AnalysisReport` (status=pending), `db.commit()`, `dispatch_task(run_analysis, id)`
3. `run_analysis()` läuft im Background-Thread: XML-Parsing → Flatten → Keyword-Library-Enrichment → Compute → JSON-Ergebnisse speichern (Execution-KPIs querien die DB direkt statt XML)
4. Frontend pollt alle 3s oder empfängt WebSocket `analysis_status_changed`
5. Ergebnisse werden als KPI-spezifische Karten im StatsView (Tab "Deep Analysis") gerendert

**Frontend:**
- `StatsView.vue` hat jetzt 2 Tabs: "Overview" (bestehend) + "Deep Analysis" (neu)
- Analyse-Modal mit KPI-Checkboxen gruppiert nach Kategorie
- Ergebnis-Karten: Tabellen, Balkendiagramme, Tag-Cloud, Fehler-Cluster, CSS Stacked Bars, Dot Timeline, Heatmap Grid, Treemap
- i18n: `stats.analysis.*` Keys in EN/DE/FR/ES

### WebSocket-Broadcast aus Background-Threads
Background-Tasks (execute_test_run, run_analysis) laufen in sync Threads und können keine `await` Aufrufe machen. Um WebSocket-Nachrichten zu senden:
```python
# In backend/src/execution/tasks.py:
from src.main import _event_loop
asyncio.run_coroutine_threadsafe(ws_manager.broadcast_run_status(run_id, status), _event_loop)
```
Der Event-Loop wird in `main.py` Lifespan als `_event_loop` gespeichert. Zwei Helper-Funktionen kapseln dieses Pattern:
- `_broadcast_run_status()` in `execution/tasks.py` — für Run-Status-Updates
- `_broadcast_analysis_status()` in `stats/analysis.py` — für Analyse-Status-Updates

**Wichtig:** Niemals `asyncio.run()` aus einem Background-Thread aufrufen — das erstellt einen neuen Event-Loop und schlägt fehl. Immer `asyncio.run_coroutine_threadsafe(coro, _event_loop)` verwenden.

### KPI-Validation (Stats-Router)
`POST /stats/analysis` validiert `selected_kpis` gegen `AVAILABLE_KPIS.keys()`. Unbekannte KPI-IDs werden mit HTTP 422 abgelehnt (Detail-Nachricht enthält die ungültigen IDs).

### AI-Modul (.roboscope ↔ .robot Generierung + Fehleranalyse)
LLM-gestütztes Modul zur bidirektionalen Synchronisation zwischen `.roboscope` YAML-Spezifikationen und `.robot` Testdateien, sowie KI-gestützte Fehleranalyse für Reports.

**Dateien:**
- `backend/src/ai/models.py` — `AiProvider` (LLM-Konfiguration), `AiJob` (Jobs: generate, reverse, analyze)
- `backend/src/ai/schemas.py` — Pydantic Request/Response Schemas (inkl. `AnalyzeRequest`)
- `backend/src/ai/service.py` — CRUD, Spec-Parsing, Drift-Erkennung (SHA256)
- `backend/src/ai/router.py` — 11 API-Endpoints (Provider CRUD, Generate, Reverse, **Analyze**, Accept, Validate, Drift)
- `backend/src/ai/llm_client.py` — Einheitlicher LLM-Client (OpenAI/Anthropic/OpenRouter/Ollama via httpx)
- `backend/src/ai/prompts.py` — System/User Prompt Templates für Generierung, Reverse und **Fehleranalyse**
- `backend/src/ai/tasks.py` — Background-Tasks: `run_generate()`, `run_reverse()`, **`run_analyze()`**
- `backend/src/ai/encryption.py` — Fernet-Verschlüsselung für API-Keys (abgeleitet von SECRET_KEY)
- `backend/src/ai/rf_knowledge.py` — Stub für optionale rf-mcp Integration
- `frontend/src/api/ai.api.ts` — API-Client (inkl. `analyzeFailures()`)
- `frontend/src/stores/ai.store.ts` — Pinia Store (Provider-Management, Job-Polling, Drift, **analysisJob**)
- `frontend/src/components/ai/ProviderConfig.vue` — LLM-Provider Verwaltung (Settings-Tab)
- `frontend/src/components/ai/GenerateModal.vue` — Generierungs-Modal mit Fortschritt + DiffPreview
- `frontend/src/components/ai/DiffPreview.vue` — Raw/Unified Diff-Ansicht
- `frontend/src/components/ai/SpecEditor.vue` — Dual-Tab-Editor für .roboscope Dateien (Visual Form + YAML mit CodeMirror, Library-Autocomplete, Environment-Auswahl)
- `frontend/src/views/ReportDetailView.vue` — **AI Failure Analysis Card** im Summary-Tab

**Ablauf Generierung:**
1. User erstellt/editiert `.roboscope` YAML-Datei im Explorer
2. Klickt "Generate" → Backend dispatcht LLM-Aufruf als Background-Task
3. Frontend pollt Job-Status alle 2s
4. Bei Abschluss: DiffPreview zeigt generiertes `.robot` vs. bestehendes
5. User akzeptiert → Datei wird geschrieben, `generation_hash` aktualisiert
6. Drift-Erkennung: SHA256-Vergleich zwischen `.roboscope` Hash und aktuellem `.robot` Inhalt

**Ablauf Fehleranalyse:**
1. User öffnet Report-Detailansicht eines Reports mit fehlgeschlagenen Tests
2. Klickt "Fehler analysieren" → `POST /ai/analyze` erstellt `AiJob(type="analyze", report_id=X)`
3. `run_analyze()` im Background-Thread: lädt Report + fehlgeschlagene TestResults, baut Prompt, ruft LLM auf
4. Frontend pollt `analysisJob` alle 2s via `GET /ai/status/{job_id}`
5. Bei Abschluss: Markdown-Analyse wird gerendert (Root-Cause, Pattern-Erkennung, Fix-Vorschläge, Prioritäten)
6. Fehlerbehandlung: Error-State mit Retry-Button, "No Provider"-Hinweis wenn kein LLM konfiguriert
7. `AiJob.report_id` FK verknüpft den Analyse-Job mit dem Report

**Unterstützte LLM-Anbieter:**
- OpenAI (GPT-4.1, GPT-4o, o3, o4-mini), Anthropic (Claude Sonnet/Opus 4.6, Haiku 4.5), OpenRouter (beliebige Modelle), Ollama (lokale Modelle)
- API-Keys werden mit Fernet verschlüsselt in der DB gespeichert
- ProviderConfig bietet kuratierte Modell-Dropdowns pro Anbieter (statt freier Texteingabe)

### Default Admin User + Examples-Projekt
Beim ersten Start wird automatisch erstellt:
- Admin-User: `admin@roboscope.local` / `admin123`
- "Examples"-Projekt: Zeigt auf `backend/examples/tests/` mit 5 Beispiel-Robot-Dateien

### vue-i18n: Sonderzeichen in Übersetzungen escapen
vue-i18n v10 verwendet eine strikte Message-Syntax. Folgende Zeichen sind **reserviert** und müssen in Übersetzungstexten escaped werden:
- `@` → `{'@'}` (Linked-Message-Syntax, z.B. `admin{'@'}roboscope.local`)
- `|` → `{'|'}` (Plural-Trennzeichen)
- `{` / `}` → `{'{}'}` (Placeholder-Syntax)
- `#` → kann in Plural-Kontexten problematisch sein

**Wichtig:** Im Dev-Modus (Vite) ist der Message-Compiler toleranter; im Production-Build (dist) führen unescapte Sonderzeichen zu `SyntaxError` und die betroffene Komponente rendert nicht (blanker Bildschirm). Immer im Production-Build testen!

## Bekannte Probleme / Technical Debt (Stand: 2026-02-24)

### Erledigt (2026-02-24)

- [x] python-jose → PyJWT migriert (auth/service.py)
- [x] passlib → bcrypt direkt migriert (auth/service.py)
- [x] bcrypt Pin `<4.1` entfernt → `>=4.2.0` (bcrypt 5.0.0 installiert)
- [x] Zip Slip Vulnerability behoben (reports/router.py: Pfad-Validierung vor extractall)
- [x] Rate Limiting auf Login (10 Versuche / 5 Minuten pro IP)
- [x] SECRET_KEY Startup-Guard (Warning bei Default-Key)
- [x] WebSocket JWT Auth (Token via Query-Parameter, 4401 bei ungültigem Token)
- [x] XSS in KeywordNode.vue behoben (nur `<img>` Tags mit sicheren Attributen erlaubt)
- [x] Vue Error Handler hinzugefügt (main.ts: `app.config.errorHandler`)
- [x] 7 separate DB-Engines → 1 zentralisierte `get_sync_session()` in `database.py`
- [x] Memory Leak EnvironmentsView behoben (onUnmounted cleanup für Docker-Build-Polling)
- [x] `_get_sync_session()` 7x dedupliziert, `renderMarkdown()` in `utils/renderMarkdown.ts` extrahiert
- [x] `datetime.utcnow()` → `datetime.now(timezone.utc)` in stats/analysis.py
- [x] `lang="de"` → `lang="en"` in index.html
- [x] Graceful Shutdown für TaskExecutor (shutdown_executor in Lifespan)
- [x] Explorer: Falscher "Unsaved"-Badge beim Dateiöffnen behoben (ignoreContentUpdates Flag in ExplorerView.vue)
- [x] Explorer: Save-Before-Run Prompt bei ungespeicherten Änderungen (Modal + saveAndRun/runWithoutSaving Handler)
- [x] Dependabot: minimatch ReDoS-Vulnerability behoben (npm override minimatch>=10.2.1, editorconfig>=2.0.0 in package.json)
- [x] pip/venv → uv migriert (venv_utils.py, cross-platform Windows/Mac/Linux, `_get_pip_path()` 3x dedupliziert, `os.pathsep` statt hardcoded `:`)

### OFFEN — Noch zu erledigen

1. **Unauthentifizierte Report-Assets** — `reports/router.py`: Kein Auth auf `/reports/{id}/assets/`
2. **JWT-Token in URL** — `frontend/src/api/reports.api.ts:20-27`: Token im Query-Parameter (Browser-History, Logs, Referer)
3. **Request Size Limits** — Report-Upload ohne Größenbeschränkung (Zip-Bombs)
4. **Default-Credentials-Probe** — `LoginView.vue:21-35`: Login-Seite testet automatisch `admin123`
5. **270KB Docs eagerly gebundelt** — Alle 4 Sprachen im Bundle, nur 1 wird gebraucht → dynamic import
6. **55+ `as any` Casts** — TypeScript-Sicherheit wird an vielen Stellen umgangen
7. **Accessibility** — Nur 1 `aria-label` in gesamter App, keine Label-Verknüpfung bei Forms
8. **Structured Logging** — Nur plaintext `basicConfig`, kein JSON, kein Request-ID-Tracking
9. **Health Check** — Gibt immer "healthy" zurück, auch wenn DB down
10. **Docker-Client deduplizieren** — 3x kopiert in verschiedenen Modulen

### Veraltete Dependencies (noch offen)

| Paket | Aktuell | Verfügbar | Priorität |
|-------|---------|-----------|-----------|
| vue-i18n | ^10 | v11 | MITTEL |
| pinia | ^2 | v3 | MITTEL |
| vue-router | ^4 | v5 | MITTEL |
| typescript | ~5.5 | 5.9 | NIEDRIG |

### Test-Lücken (Höchstes Risiko)

- **SubprocessRunner / DockerRunner** — 0 Tests (Kern-Ausführungslogik)
- **execute_test_run()** — 0 Tests (Run-Lifecycle-Orchestrierung)
- **AI LLM Client** — 0 Tests (4 Provider-APIs, Key-Handling)
- **AI Encryption** — 0 Tests (Fernet für API-Keys)
- **WebSocket Manager** — 0 Tests (Connect/Disconnect/Broadcast)
- **task_executor.py (TaskExecutor)** — 0 Tests (alle Background-Tasks)
- **AI Router**: 8 von 18 Endpoints ungetestet (generate, reverse, analyze, status, accept, drift)
- **Report Router**: 5 Endpoints ungetestet (upload, html, assets, zip, delete-all)
- ~~**Environment Tasks** — 0 Tests~~ → Behoben: 7 Tests (create_venv, install/upgrade/uninstall_package)
- ~~**venv_utils** — nicht existent~~ → Behoben: 14 Tests (cross-platform Pfade, uv-Kommandos)

## Coding-Konventionen

- **Backend**: Python 3.12+, Ruff (line-length=100), mypy strict, sync SQLAlchemy
- **Frontend**: TypeScript strict, Vue 3 Composition API + `<script setup>`, Pinia Stores
- **Tests**: Sync Tests, Klassen-Gruppierung, `_make_*` Helper
- **CSS**: Alle Variablen in `frontend/src/assets/styles/main.css`, keine separaten Variable/Transition-Dateien
- **Git**: Konventionelle Commits, Feature-Branches, PR-basierter Workflow
- **Sprache**: 4 Sprachen vollständig (EN, DE, FR, ES), In-App-Docs in EN+DE+FR+ES
