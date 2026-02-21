# RoboScope

Web-based Robot Framework Test Management Tool with Git integration, GUI execution, report analysis, environment management, and container runtime.

## Features

- **Project Management** — Clone Git repos or link local folders, branch management, auto-sync
- **Test Explorer** — Browse test files, parse Robot Framework keywords/tests, library dependency check
- **Test Execution** — Run tests via subprocess or Docker, live WebSocket status updates, scheduling
- **Environment Management** — Create Python virtual environments, install/manage packages, set variables
- **Report Analysis** — Parse `output.xml`, compare runs, view embedded HTML reports
- **Statistics & KPIs** — Pass rate trends, flaky test detection, heatmaps, deep analysis (8 KPIs)
- **Role-Based Access** — Four roles: Viewer, Runner, Editor, Admin
- **Multi-Language UI** — English, German, French, Spanish
- **In-App Documentation** — Searchable docs with print/PDF export
- **Offline Deployment** — Standalone ZIP with bundled dependencies for air-gapped environments

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Python 3.12+ |
| Frontend | Vue 3, TypeScript, Pinia, Vue Router, Chart.js, Vite |
| Database | SQLite (default) or PostgreSQL |
| Tests | pytest, Vitest, Playwright |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+

### Development

```bash
# Install dependencies
make install

# Copy environment config
cp backend/.env.example backend/.env

# Start backend (port 8000) + frontend (port 5173)
make dev
```

### Docker

```bash
make docker-dev    # Development (SQLite)
make docker-up     # Production (PostgreSQL + Nginx)
```

### Standalone Deployment

Download the latest `roboscope.zip` from [GitHub Actions](../../actions/workflows/build.yml), then:

```bash
unzip roboscope.zip
cd roboscope
./install-mac-and-linux.sh       # Creates venv, installs dependencies offline
./start-mac-and-linux.sh         # Starts server at http://localhost:8000
```

On Windows, use `install-windows.bat` and `start-windows.bat` instead.

Default login: `admin@roboscope.local` / `admin123`

## Project Structure

```
RoboScope/
├── backend/          # FastAPI application
│   ├── src/          # Source code (domain-driven modules)
│   ├── tests/        # pytest-asyncio tests
│   ├── migrations/   # Alembic database migrations
│   └── examples/     # Example Robot Framework test files
├── frontend/         # Vue 3 + TypeScript SPA
│   └── src/
│       ├── views/    # 12 application views
│       ├── stores/   # Pinia state management
│       ├── api/      # Axios API clients
│       └── i18n/     # Translations (EN, DE, FR, ES)
├── e2e/              # Playwright end-to-end tests
├── docker/           # Dockerfiles and nginx config
├── scripts/          # Build and utility scripts
└── Makefile          # All common commands
```

## API

Swagger UI available at `http://localhost:8000/api/v1/docs`

| Endpoint | Description |
|----------|-------------|
| `/api/v1/auth` | Authentication & user management |
| `/api/v1/repos` | Project CRUD & Git sync |
| `/api/v1/explorer/{repo_id}` | File browser, test parser, library check |
| `/api/v1/runs` | Test execution & scheduling |
| `/api/v1/environments` | Virtual environments & packages |
| `/api/v1/reports` | Report parsing & comparison |
| `/api/v1/stats` | KPIs, trends, deep analysis |
| `/api/v1/settings` | Application settings (admin) |

## Testing

```bash
make test-backend       # Backend unit tests
make test-frontend      # Frontend unit tests
make test-e2e           # Playwright E2E tests
make test               # All tests
```

## Building

```bash
# Build standalone offline distribution
bash scripts/build-mac-and-linux.sh

# Output: dist/roboscope.zip (includes wheels for Linux, macOS, Windows)
```

## License

Proprietary — viadee Unternehmensberatung AG
