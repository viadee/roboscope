# mateoX — Claude Code Projektdokumentation

Webbasiertes Robot Framework Test-Management-Tool mit Git-Integration, GUI-Ausführung, Report-Analyse, Environment-Management und Container-Runtime.

## Aktueller Projektstatus (Stand: 2026-02-17)

### Was ist implementiert

**Backend (FastAPI) — VOLLSTÄNDIG implementiert (~5.300 Zeilen)**
- Auth/JWT mit RBAC (Viewer < Runner < Editor < Admin)
- Repository-Management mit GitPython (clone, sync, branches)
- Testfall-Explorer (Dateisystem-Browser + Robot-Parser)
- Testausführung: SubprocessRunner + DockerRunner + In-Process TaskExecutor
- Environment-Management (venv, Pakete, Variablen)
- Report-Parsing (output.xml → DB) + Vergleich
- KPI/Statistik-Service (Trends, Flaky Detection, Heatmaps)
- Settings (Key-Value, Admin-only)
- Plugin-System (Registry + Console-Logger Builtin)
- WebSocket Connection Manager (Live-Updates)
- Alembic Migrationen (SQLite + PostgreSQL)
- Bulk-Operationen: Cancel all runs (RUNNER+), Delete all reports (ADMIN)

**Frontend (Vue 3 + TypeScript) — VOLLSTÄNDIG implementiert (~4.900 Zeilen)**
- 10 Views: Login, Dashboard, Repos, Explorer, Execution, Environments, Reports, ReportDetail, Stats, Settings
- 8 Pinia Stores: auth, repos, explorer, execution, environments, reports, stats, ui
- 8 API-Clients: auth, repos, explorer, execution, environments, reports, stats, settings
- 5 Base UI-Komponenten: BaseButton, BaseBadge, BaseModal, BaseToast, BaseSpinner
- 2 Layout-Komponenten: AppHeader, AppSidebar
- 2 Layouts: DefaultLayout (Sidebar+Header), AuthLayout (Login)
- 2 Composables: useWebSocket, useToast
- Vue Router mit rollenbasierten Guards
- TypeScript Domain + API Types

**E2E Tests (Playwright) — VOLLSTÄNDIG implementiert (~1.000 Zeilen)**
- 8 Test-Specs: auth, dashboard, navigation, repos, execution, environments, reports, settings
- Page Objects: LoginPage, DashboardPage, SidebarNav
- Auth-Fixture mit JWT-Injection
- API-Mocking via page.route()

**Docker — VOLLSTÄNDIG konfiguriert**
- 4 Dockerfiles: backend, frontend, worker, playwright
- 3 Compose-Files: production (PostgreSQL+Redis+Nginx), dev (SQLite+Redis), test

### Wichtige Architekturentscheidung: Task-Ausführung

**Celery + Redis wurde komplett entfernt** und durch einen in-process `ThreadPoolExecutor(max_workers=1)` ersetzt.

Warum:
- Kein externer Redis/Celery-Worker nötig — einfachere Entwicklung und Deployment
- Alle Hintergrundaufgaben (Test-Runs, Git-Clone/Sync, Report-Parsing, Package-Ops) laufen über `dispatch_task()`
- `max_workers=1` stellt sicher, dass nur 1 Testlauf gleichzeitig läuft (Tasks werden in FIFO-Queue gereiht)
- Fehlerbehandlung: Wenn ein Task nicht gestartet werden kann, wird `TaskDispatchError` geworfen und der Run bekommt `status=ERROR` mit sichtbarer Fehlermeldung

Schlüsseldatei: `backend/src/celery_app.py` — enthält `dispatch_task()`, `TaskDispatchError`, `TaskResult`

**Wichtig**: Vor `dispatch_task()` muss immer `await db.commit()` aufgerufen werden, damit der Background-Thread die Daten in einer separaten DB-Session sehen kann.

### Aktuelle Arbeit / Nächste Schritte

**Fertiggestellt:**
- [x] Task-Executor (ThreadPoolExecutor statt Celery)
- [x] "Alle abbrechen" Button auf Execution-Seite (POST /runs/cancel-all, nur für RUNNER+)
- [x] "Alle löschen" Button auf Reports-Seite (DELETE /reports/all, nur für ADMIN, mit Bestätigungsdialog)
- [x] Error-Handling: Fehlgeschlagene Dispatches → Run-Status ERROR + sichtbare Fehlermeldung
- [x] E2E Tests für Execution (7/7 bestanden)

**Offen:**
- [ ] i18n für gesamte Anwendung (DE, EN, FR, ES)
- [ ] "In Editor öffnen" Button (Explorer)
- [ ] Offline-Archiv-Analyse
- [ ] Reports Embedding: RF HTML Report, Assets, ZIP-Download, XML-basierte Ansicht
- [ ] App-Painpoints adressieren
- [ ] Vergleich mit www.mateo-automation.com für Feintuning
- [ ] Fehlende UI-Komponenten: BaseInput, BaseTable, BaseCard, BaseDropdown
- [ ] Chart-Integration (Chart.js) in StatsView
- [ ] Responsive Optimierung

## Architektur

```
mateoX/
├── backend/          # FastAPI (Python 3.12+)
│   ├── src/          # Applikations-Code (Domain-Driven)
│   │   ├── auth/     # JWT-Auth + RBAC (Viewer < Runner < Editor < Admin)
│   │   ├── repos/    # Git-Repository-Verwaltung (GitPython)
│   │   ├── explorer/ # Dateisystem-Browser + Robot-Parser
│   │   ├── execution/# Test-Runs + Scheduling (Subprocess + Docker Runner)
│   │   ├── environments/ # venv + Pakete + Variablen
│   │   ├── reports/  # output.xml Parser + Vergleich
│   │   ├── stats/    # KPI Dashboard, Flaky Detection, Heatmap
│   │   ├── settings/ # Key-Value App-Settings (Admin)
│   │   ├── plugins/  # Plugin-System (Analyzer, Runner, Integration, KPI)
│   │   ├── websocket/# WebSocket Connection Manager
│   │   ├── api/v1/   # Router-Aggregation
│   │   ├── config.py # Pydantic Settings (.env)
│   │   ├── database.py # SQLAlchemy async + TimestampMixin
│   │   ├── celery_app.py # In-Process TaskExecutor (ThreadPoolExecutor, NICHT Celery!)
│   │   └── main.py   # FastAPI App Factory + Lifespan
│   ├── tests/        # pytest-asyncio Tests
│   ├── migrations/   # Alembic (SQLite + PostgreSQL)
│   └── pyproject.toml
├── frontend/         # Vue 3 + TypeScript + Vite
│   └── src/
│       ├── api/      # Axios API-Client mit JWT-Interceptor
│       ├── stores/   # Pinia Stores (auth, repos, explorer, execution, ...)
│       ├── views/    # 10 Views (Login, Dashboard, Repos, Explorer, ...)
│       ├── components/ # UI-Basiskomponenten + Layout
│       ├── composables/ # useWebSocket, useToast
│       ├── router/   # Vue Router mit rollenbasierten Guards
│       └── types/    # TypeScript Domain + API Types
├── e2e/              # Playwright E2E-Tests
│   ├── page-objects/ # LoginPage, DashboardPage, SidebarNav
│   ├── fixtures/     # Auth-Fixture mit Token-Injection
│   └── tests/        # auth, navigation, repos, execution, environments, reports, settings
├── docker/           # Dockerfiles (backend, frontend, worker, playwright)
├── docker-compose.yml      # Production (PostgreSQL + Redis + Nginx)
├── docker-compose.dev.yml  # Development (SQLite + Redis)
├── docker-compose.test.yml # Test-Umgebung
└── Makefile          # Alle Befehle
```

## Design-System (mateo-automation.com Branding)

### Farben (CSS Custom Properties in main.css)
```css
--color-primary: #3CB5A1      /* Teal — mateo Hauptfarbe */
--color-accent: #DFAA40       /* Gold — Akzentfarbe */
--color-navy: #203166         /* Navy — Sidebar/Dark Areas */
--color-navy-dark: #101933    /* Dunkleres Navy */
--color-bg: #F4F7FA           /* Seiten-Hintergrund */
--color-bg-card: #ffffff      /* Karten-Hintergrund */
--color-text: #1A1D2E         /* Haupttext */
--color-text-muted: #5C688C   /* Sekundärtext */
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

- **Backend**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2, ThreadPoolExecutor (Background Tasks), GitPython, Docker SDK
- **Frontend**: Vue 3.5, Pinia, Vue Router 4, Axios, Chart.js, TypeScript, Vite
- **Datenbank**: SQLite (Standard/Dev) oder PostgreSQL (Production), konfigurierbar via `DATABASE_URL`
- **Tests**: pytest + pytest-asyncio, Vitest + @vue/test-utils, Playwright
- **Kein Redis/Celery nötig** — alle Background-Tasks laufen in-process via ThreadPoolExecutor

## API-Endpunkte

Alle unter `/api/v1/`:

| Prefix | Modul | Auth |
|--------|-------|------|
| `/auth` | Login, Refresh, User-CRUD | Teilweise |
| `/repos` | Repository CRUD + Git Sync | EDITOR+ für Schreibops |
| `/explorer/{repo_id}` | Dateibaum, Suche, Testcases | Authentifiziert |
| `/runs` + `/schedules` | Ausführung + Scheduling | RUNNER+ / EDITOR+ |
| `/runs/cancel-all` | Alle laufenden Runs abbrechen | RUNNER+ |
| `/environments` | Umgebungen, Pakete, Variablen | EDITOR+ für Schreibops |
| `/reports` | Reports, Vergleich, HTML-Export | Authentifiziert |
| `/reports/all` (DELETE) | Alle Reports löschen | ADMIN |
| `/stats` | KPIs, Trends, Flaky, Heatmap | Authentifiziert |
| `/settings` | App-Settings | ADMIN only |

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
cd mateoX/backend && .venv/bin/python -m uvicorn src.main:app --reload --port 8000
```

Frontend manuell starten:
```bash
cd mateoX/frontend && npm run dev
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
cd mateoX/e2e && npx playwright test
cd mateoX/e2e && npx playwright test tests/execution-run.spec.ts  # einzelner Spec
```

- **Backend**: pytest-asyncio, asyncio_mode=auto, In-Memory SQLite, transaktionaler Rollback
- **Fixtures**: `db_session`, `client` (HTTPX), `admin_user`, `runner_user`, `viewer_user`, `auth_header(user)`
- **Frontend**: Vitest, `describe/it/expect`, Pinia mit `createPinia`/`setActivePinia`
- **E2E**: Playwright, Page Objects, Auth-Fixture mit JWT-Injection, API-Mocking via `page.route()`

## Datenbank-Migrationen

```bash
make db-migrate msg="Add new column"
make db-upgrade
make db-downgrade
```

## Wichtige Konfiguration

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./mateox.db` | DB-Connection |
| `SECRET_KEY` | dev-key | JWT-Secret |
| `RUNNER_TYPE` | `auto` | `subprocess`, `docker`, `auto` |
| `DOCKER_AVAILABLE` | `false` | Docker-Runner aktivieren |
| `DEFAULT_TIMEOUT_SECONDS` | `3600` | Timeout pro Run |
| `LOG_LEVEL` | `INFO` | Logging-Level |
| `WORKSPACE_DIR` | `~/.mateox/workspace` | Git-Repos Arbeitsverzeichnis |
| `REPORTS_DIR` | `~/.mateox/reports` | Report-Dateien Verzeichnis |
| `VENVS_DIR` | `~/.mateox/venvs` | Virtuelle Environments |

## Bekannte Patterns und Gotchas

### DB Commit vor dispatch_task()
Background-Tasks laufen in separaten Threads mit eigener sync DB-Session. Die async SQLAlchemy-Session im FastAPI-Request committed erst nach dem Handler-Return. Deshalb **muss immer `await db.commit()` VOR `dispatch_task()` aufgerufen werden**, damit der Background-Thread die Daten sieht.

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

### Default Admin User
Beim ersten Start wird automatisch ein Admin-User erstellt:
- Email: `admin@mateox.local`
- Passwort: `admin123`

## Coding-Konventionen

- **Backend**: Python 3.12+, Ruff (line-length=100), mypy strict, async/await
- **Frontend**: TypeScript strict, Vue 3 Composition API + `<script setup>`, Pinia Stores
- **Tests**: Async ohne `@pytest.mark.asyncio`, Klassen-Gruppierung, `_make_*` Helper
- **CSS**: Alle Variablen in `frontend/src/assets/styles/main.css`, keine separaten Variable/Transition-Dateien
- **Git**: Konventionelle Commits, Feature-Branches, PR-basierter Workflow
- **Sprache**: UI-Texte aktuell auf Deutsch (i18n noch offen)
