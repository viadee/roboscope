# RoboScope — Claude Code Projektdokumentation

Webbasiertes Robot Framework Test-Management-Tool mit Git-Integration, GUI-Ausführung, Report-Analyse, Environment-Management und Container-Runtime.

## Aktueller Projektstatus (Stand: 2026-02-19)

### Was ist implementiert

**Backend (FastAPI) — VOLLSTÄNDIG implementiert (~5.800 Zeilen)**
- Auth/JWT mit RBAC (Viewer < Runner < Editor < Admin) + Admin-Passwort-Reset
- Repository-Management mit GitPython (clone, sync, branches), Projekt-Umgebungszuordnung
- Testfall-Explorer (Dateisystem-Browser + Robot-Parser + Library-Check + "In Dateibrowser öffnen")
- Testausführung: SubprocessRunner + DockerRunner + In-Process TaskExecutor + WebSocket-Live-Updates
- Environment-Management (venv, Pakete, Variablen)
- Report-Parsing (output.xml → DB) + Vergleich
- KPI/Statistik-Service (Trends, Flaky Detection, Heatmaps) + On-Demand Tiefenanalyse (8 KPIs) + Refresh/Staleness
- Settings (Key-Value, Admin-only)
- Plugin-System (Registry + Console-Logger Builtin)
- WebSocket Connection Manager (Live-Updates bei Run-Status-Änderungen)
- Alembic Migrationen (SQLite + PostgreSQL)
- Bulk-Operationen: Cancel all runs (RUNNER+), Delete all reports (ADMIN)
- Seed: Default-Admin + "Examples"-Projekt beim ersten Start
- AI-Modul: LLM-gestützte .roboscope ↔ .robot Generierung (OpenAI, Anthropic, OpenRouter, Ollama)

**Frontend (Vue 3 + TypeScript) — VOLLSTÄNDIG implementiert (~5.500 Zeilen)**
- 12 Views: Login, Dashboard, Repos, Explorer, Execution, Environments, Reports, ReportDetail, Stats, Settings, Docs, Imprint
- In-App-Dokumentation: DocsView mit TOC-Sidebar, Suche, Print/PDF, i18n (EN+DE), offline-fähig
- 9 Pinia Stores: auth, repos, explorer, execution, environments, reports, stats, ui, ai
- 9 API-Clients: auth, repos, explorer, execution, environments, reports, stats, settings, ai
- 5 Base UI-Komponenten: BaseButton, BaseBadge, BaseModal, BaseToast, BaseSpinner
- 2 Layout-Komponenten: AppHeader, AppSidebar
- 2 Layouts: DefaultLayout (Sidebar+Header+Footer), AuthLayout (Login)
- 2 Composables: useWebSocket, useToast
- i18n: vollständig in 4 Sprachen (EN, DE, FR, ES)
- Vue Router mit rollenbasierten Guards
- TypeScript Domain + API Types
- Footer: Copyright, mateo-automation.com Link, Impressum
- Execution-Tabelle: Environment-Spalte, Retry-Button, Explorer-Link, Spinner bei aktiven Runs

**E2E Tests (Playwright) — UMFASSEND (~1.400 Zeilen)**
- 12 Test-Specs: auth, dashboard, navigation, repos, execution, environments, reports, settings, stats, imprint, password-reset, repo-environment
- Page Objects: LoginPage, DashboardPage, SidebarNav
- Auth-Fixture mit JWT-Injection
- API-Mocking via page.route()

**Backend Tests (pytest) — ~160 Tests**
- Auth: Login, Registration, Password-Reset (5 Tests)
- Repos: CRUD, Service (20+ Tests)
- Explorer: File-Browser, Open-In-File-Browser (5 Tests)
- Execution: Runs, Scheduling (20+ Tests)
- Environments: CRUD, Packages (20+ Tests)
- Reports: Parsing, Comparison (20+ Tests)
- Stats: Overview, Aggregate, Data-Status (7 Tests)
- Settings: CRUD, Permissions (10+ Tests)

**Docker — VOLLSTÄNDIG konfiguriert**
- 3 Dockerfiles: backend, frontend, playwright
- 3 Compose-Files: production (PostgreSQL+Nginx), dev (SQLite), test

**Build/Distribution**
- `scripts/build-mac-and-linux.sh` — Erstellt standalone ZIP-Archiv für Offline-Deployment (Windows, Mac, Linux)
- Enthält: Frontend-Build, Backend-Source, Python-Wheels, Install/Start-Skripte

### Wichtige Architekturentscheidung: Task-Ausführung

**Celery + Redis wurde komplett entfernt** und durch einen in-process `ThreadPoolExecutor(max_workers=1)` ersetzt.

Warum:
- Kein externer Redis/Celery-Worker nötig — einfachere Entwicklung und Deployment
- Alle Hintergrundaufgaben (Test-Runs, Git-Clone/Sync, Report-Parsing, Package-Ops) laufen über `dispatch_task()`
- `max_workers=1` stellt sicher, dass nur 1 Testlauf gleichzeitig läuft (Tasks werden in FIFO-Queue gereiht)
- Fehlerbehandlung: Wenn ein Task nicht gestartet werden kann, wird `TaskDispatchError` geworfen und der Run bekommt `status=ERROR` mit sichtbarer Fehlermeldung

Schlüsseldatei: `backend/src/celery_app.py` — enthält `dispatch_task()`, `TaskDispatchError`, `TaskResult`

**Wichtig**: Vor `dispatch_task()` muss immer `db.commit()` aufgerufen werden, damit der Background-Thread die Daten in einer separaten DB-Session sehen kann.

### Aktuelle Arbeit / Nächste Schritte

**Fertiggestellt:**
- [x] Task-Executor (ThreadPoolExecutor statt Celery)
- [x] "Alle abbrechen" Button auf Execution-Seite (POST /runs/cancel-all, nur für RUNNER+)
- [x] "Alle löschen" Button auf Reports-Seite (DELETE /reports/all, nur für ADMIN, mit Bestätigungsdialog)
- [x] Error-Handling: Fehlgeschlagene Dispatches → Run-Status ERROR + sichtbare Fehlermeldung
- [x] E2E Tests für Execution (7/7 bestanden)
- [x] In-App-Dokumentation (DocsView, EN+DE, TOC, Suche, Print/PDF, offline-fähig)
- [x] Package Manager & Library Check (Nav umbenannt, Library-Scanner, Repo-Environment-Zuordnung, One-Click-Install)
- [x] On-Demand Tiefenanalyse-Modul (8 KPIs in 3 Kategorien: Keyword Analytics, Test Quality, Maintenance)
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
- [x] In-App-Dokumentation aktualisiert (EN+DE: Passwort-Reset, Umgebungsauswahl, Stats-Refresh, Impressum)
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
│   │   ├── environments/ # venv + Pakete + Variablen
│   │   ├── reports/  # output.xml Parser + Vergleich
│   │   ├── stats/    # KPI Dashboard, Flaky Detection, Heatmap, On-Demand Tiefenanalyse
│   │   ├── ai/       # LLM-gestützte .roboscope ↔ .robot Generierung
│   │   ├── settings/ # Key-Value App-Settings (Admin)
│   │   ├── plugins/  # Plugin-System (Analyzer, Runner, Integration, KPI)
│   │   ├── websocket/# WebSocket Connection Manager
│   │   ├── api/v1/   # Router-Aggregation
│   │   ├── config.py # Pydantic Settings (.env)
│   │   ├── database.py # SQLAlchemy sync + TimestampMixin
│   │   ├── celery_app.py # In-Process TaskExecutor (ThreadPoolExecutor, NICHT Celery!)
│   │   └── main.py   # FastAPI App Factory + Lifespan
│   ├── tests/        # pytest Tests
│   ├── migrations/   # Alembic (SQLite + PostgreSQL)
│   └── pyproject.toml
├── frontend/         # Vue 3 + TypeScript + Vite
│   └── src/
│       ├── api/      # Axios API-Client mit JWT-Interceptor
│       ├── docs/     # In-App-Dokumentation (types, content/en, content/de)
│       ├── stores/   # Pinia Stores (auth, repos, explorer, execution, ...)
│       ├── views/    # 12 Views (Login, Dashboard, Repos, Explorer, ...)
│       ├── components/ # UI-Basiskomponenten + Layout
│       ├── composables/ # useWebSocket, useToast
│       ├── router/   # Vue Router mit rollenbasierten Guards
│       └── types/    # TypeScript Domain + API Types
├── e2e/              # Playwright E2E-Tests
│   ├── page-objects/ # LoginPage, DashboardPage, SidebarNav
│   ├── fixtures/     # Auth-Fixture mit Token-Injection
│   └── tests/        # auth, navigation, repos, execution, environments, reports, settings, stats, imprint, password-reset, repo-environment
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
| `/ai` | LLM-Provider CRUD, Spec→Robot Generierung, Robot→Spec Reverse, Drift-Erkennung | EDITOR+ |

Swagger UI: `http://localhost:8000/api/v1/docs`

## Rollen-Hierarchie

`VIEWER (0) < RUNNER (1) < EDITOR (2) < ADMIN (3)` — definiert in `backend/src/auth/constants.py`

## Entwicklung starten

### Voraussetzungen

- Python 3.12+, Node.js 20+
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

## Bekannte Patterns und Gotchas

### DB Commit vor dispatch_task()
Background-Tasks laufen in separaten Threads mit eigener sync DB-Session. Die SQLAlchemy-Session im FastAPI-Request committed erst nach dem Handler-Return. Deshalb **muss immer `db.commit()` VOR `dispatch_task()` aufgerufen werden**, damit der Background-Thread die Daten sieht.

### SQLAlchemy Model Imports für Foreign Keys
Wenn ein Task-Modul Models mit Foreign Keys importiert (z.B. `ExecutionRun.triggered_by → users.id`), müssen ALLE referenzierten Models vorher importiert sein. In jedem `tasks.py`:
```python
import src.auth.models    # noqa: F401 — FK resolution
import src.repos.models   # noqa: F401 — FK resolution
```

### Task-Ausführung (celery_app.py — Achtung: Name ist Legacy!)
Die Datei heißt noch `celery_app.py`, enthält aber **kein Celery mehr**. Sie stellt bereit:
- `dispatch_task(func, *args, **kwargs) -> TaskResult` — Queued Task-Submission
- `TaskDispatchError` — Exception wenn Submit fehlschlägt
- `TaskResult` — Objekt mit `.id` (UUID)
- `_executor` — ThreadPoolExecutor(max_workers=1)

### Library Check (Package Manager)
Der Explorer-Router bietet einen `GET /explorer/{repo_id}/library-check?environment_id={id}` Endpoint:
- Scannt alle `.robot`/`.resource`-Dateien nach `Library`-Imports in `*** Settings ***`
- Vergleicht mit installierten Paketen via `pip list` aus der gewählten Umgebung
- Mapping: `backend/src/explorer/library_mapping.py` (Built-in-Erkennung + PyPI-Mapping + Heuristik)
- Repos haben ein optionales `environment_id` FK-Feld (Standard-Umgebung für Library-Checks)
- Nav-Label "Environments" wurde zu "Package Manager" umbenannt (i18n: EN/DE/FR/ES)

### On-Demand Tiefenanalyse (Stats-Modul)
Das Stats-Modul wurde um eine asynchrone Tiefenanalyse erweitert. Benutzer wählen KPIs aus, starten eine Analyse, und Ergebnisse werden als JSON-Blob gespeichert.

**Dateien:**
- `backend/src/stats/models.py` — `AnalysisReport` Model (status, selected_kpis, results JSON, progress)
- `backend/src/stats/schemas.py` — `AnalysisCreate`, `AnalysisResponse`, `AnalysisListResponse`, `AVAILABLE_KPIS`
- `backend/src/stats/analysis.py` — Kernmodul: 8 Compute-Funktionen + `run_analysis()` Orchestrator (sync, für Background-Thread)
- `backend/src/stats/service.py` — CRUD: `create_analysis()`, `get_analysis()`, `list_analyses()`
- `backend/src/stats/router.py` — 4 neue Endpoints: `POST /analysis`, `GET /analysis`, `GET /analysis/{id}`, `GET /analysis/kpis`

**10 KPIs in 4 Kategorien:**
- **Keyword Analytics**: keyword_frequency, keyword_duration_impact, library_distribution
- **Test Quality**: test_complexity, assertion_density, tag_coverage
- **Maintenance**: error_patterns, redundancy_detection
- **Source Analysis**: source_test_stats, source_library_distribution (analysiert .robot-Quelldateien direkt)

**Ablauf:**
1. Frontend sendet `POST /stats/analysis` mit `selected_kpis[]`
2. Backend erstellt `AnalysisReport` (status=pending), `db.commit()`, `dispatch_task(run_analysis, id)`
3. `run_analysis()` läuft im Background-Thread: XML-Parsing → Flatten → Keyword-Library-Enrichment → Compute → JSON-Ergebnisse speichern
4. Frontend pollt alle 3s oder empfängt WebSocket `analysis_status_changed`
5. Ergebnisse werden als KPI-spezifische Karten im StatsView (Tab "Deep Analysis") gerendert

**Frontend:**
- `StatsView.vue` hat jetzt 2 Tabs: "Overview" (bestehend) + "Deep Analysis" (neu)
- Analyse-Modal mit KPI-Checkboxen gruppiert nach Kategorie
- Ergebnis-Karten: Tabellen, Balkendiagramme, Tag-Cloud, Fehler-Cluster
- i18n: `stats.analysis.*` Keys in EN/DE/FR/ES

### WebSocket-Broadcast aus Background-Threads
Background-Tasks (execute_test_run, run_analysis) laufen in sync Threads und können keine `await` Aufrufe machen. Um WebSocket-Nachrichten zu senden:
```python
# In backend/src/execution/tasks.py:
from src.main import _event_loop
asyncio.run_coroutine_threadsafe(ws_manager.broadcast_run_status(run_id, status), _event_loop)
```
Der Event-Loop wird in `main.py` Lifespan als `_event_loop` gespeichert. Die Helper-Funktion `_broadcast_run_status()` in `tasks.py` kapselt dieses Pattern.

### AI-Modul (.roboscope ↔ .robot Generierung)
LLM-gestütztes Modul zur bidirektionalen Synchronisation zwischen `.roboscope` YAML-Spezifikationen und `.robot` Testdateien.

**Dateien:**
- `backend/src/ai/models.py` — `AiProvider` (LLM-Konfiguration), `AiJob` (Generierungs-Jobs)
- `backend/src/ai/schemas.py` — Pydantic Request/Response Schemas
- `backend/src/ai/service.py` — CRUD, Spec-Parsing, Drift-Erkennung (SHA256)
- `backend/src/ai/router.py` — 10 API-Endpoints (Provider CRUD, Generate, Reverse, Accept, Validate, Drift)
- `backend/src/ai/llm_client.py` — Einheitlicher LLM-Client (OpenAI/Anthropic/OpenRouter/Ollama via httpx)
- `backend/src/ai/prompts.py` — System/User Prompt Templates für Generierung und Reverse
- `backend/src/ai/tasks.py` — Background-Tasks: `run_generate()`, `run_reverse()`
- `backend/src/ai/encryption.py` — Fernet-Verschlüsselung für API-Keys (abgeleitet von SECRET_KEY)
- `backend/src/ai/rf_knowledge.py` — Stub für optionale rf-mcp Integration
- `frontend/src/api/ai.api.ts` — API-Client
- `frontend/src/stores/ai.store.ts` — Pinia Store (Provider-Management, Job-Polling, Drift)
- `frontend/src/components/ai/ProviderConfig.vue` — LLM-Provider Verwaltung (Settings-Tab)
- `frontend/src/components/ai/GenerateModal.vue` — Generierungs-Modal mit Fortschritt + DiffPreview
- `frontend/src/components/ai/DiffPreview.vue` — Raw/Unified Diff-Ansicht
- `frontend/src/components/ai/SpecEditor.vue` — Dual-Tab-Editor für .roboscope Dateien (Visual Form + YAML mit CodeMirror, Library-Autocomplete, Environment-Auswahl)

**Ablauf:**
1. User erstellt/editiert `.roboscope` YAML-Datei im Explorer
2. Klickt "Generate" → Backend dispatcht LLM-Aufruf als Background-Task
3. Frontend pollt Job-Status alle 2s
4. Bei Abschluss: DiffPreview zeigt generiertes `.robot` vs. bestehendes
5. User akzeptiert → Datei wird geschrieben, `generation_hash` aktualisiert
6. Drift-Erkennung: SHA256-Vergleich zwischen `.roboscope` Hash und aktuellem `.robot` Inhalt

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

## Coding-Konventionen

- **Backend**: Python 3.12+, Ruff (line-length=100), mypy strict, sync SQLAlchemy
- **Frontend**: TypeScript strict, Vue 3 Composition API + `<script setup>`, Pinia Stores
- **Tests**: Sync Tests, Klassen-Gruppierung, `_make_*` Helper
- **CSS**: Alle Variablen in `frontend/src/assets/styles/main.css`, keine separaten Variable/Transition-Dateien
- **Git**: Konventionelle Commits, Feature-Branches, PR-basierter Workflow
- **Sprache**: 4 Sprachen vollständig (EN, DE, FR, ES), In-App-Docs in EN+DE
