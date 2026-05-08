# RoboScope

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Build Distribution](https://github.com/viadee/roboscope/actions/workflows/build.yml/badge.svg)](https://github.com/viadee/roboscope/actions/workflows/build.yml)
[![E2E Tests](https://github.com/viadee/roboscope/actions/workflows/e2e.yml/badge.svg)](https://github.com/viadee/roboscope/actions/workflows/e2e.yml)
[![Website](https://img.shields.io/badge/website-roboscope.eu-blue)](https://roboscope.eu)

Web-based Robot Framework Test Management Tool with Git integration, GUI execution, report analysis, environment management, and container runtime.

Built by [viadee Unternehmensberatung AG](https://www.viadee.de).

![RoboScope Screenshot](docs/screenshots/dashboard.png)

## Features

- **Project Management** — Clone Git repos or link local folders, branch management, auto-sync
- **Test Explorer** — Browse test files, parse Robot Framework keywords/tests, library dependency check
- **Visual Flow Editor** — Node-based graphical test editor with keyword palette, drag & drop, control structures (IF/FOR/WHILE/TRY)
- **Test Execution** — Run tests via subprocess or Docker, live WebSocket status updates, scheduling
- **Recorder v2** — Record browser flows into `.robot` files end-to-end. Launch from the sidebar (Recorder) or from the Explorer toolbar (the Explorer button pre-selects the current repository). Transport picker for Web (Playwright) and Desktop Windows; each captured action streams live over SSE with ranked selector candidates (test-id, ARIA, text, CSS, XPath, Playwright locator). Saves a sidecar `<name>.rbs.json` alongside the `.robot` carrying all candidates — consumed later by the self-healing library. The external Chrome Recorder extension remains available as a separate HTTP client.
- **Self-Healing Selectors** — Opt-in `RoboScopeHeal` Robot Framework library (Heal Click, Heal Fill Text, Heal Upload File, Heal Drag And Drop, ...). When a selector times out at runtime the library falls through three tiers: sidecar-stored alternatives → cross-strategy transposition (`id=X` → `[data-testid=X]` → `text=X` → ...) → DOM-walk fingerprint scoring (Healenium-style). Confirmed heals land as a "🩹 Apply patch" button on the run-detail panel; suspect heals (test still failed) never offer a patch. Per-test budget, confidence thresholds, and a `no-heal` tag keep the blast radius bounded.
- **Selector Diagnosis** — Every failed run is scanned for "Element not found" / Playwright timeout signatures; recognised selectors are cross-referenced with the recording sidecar and their ranked alternatives surface as copy-chips on the run detail.
- **Flaky-Test Quarantine** — Mark any flaky test from the Stats page as quarantined. A Robot Framework listener then skips those tests at runtime (SKIP, not FAIL) so CI pipelines stop drowning in known-flaky noise. Per-repository, audit-logged, reversible.
- **AI Failure Analysis + Patch Suggestions** — The AI analyse pipeline emits prose root-cause analysis plus optional unified-diff patches for concrete fixes. Patches render as copy-to-clipboard diffs on the report page — no auto-commit.
- **Heal-Rate KPI** — Stats overview shows a 30-day heal-rate card + sparkline as a leading indicator of test drift against the app.
- **Environment Management** — Create Python virtual environments, install/manage packages, set variables, secrets encryption
- **Report Analysis** — Parse `output.xml`, compare runs, view embedded HTML reports
- **AI-Powered Analysis** — LLM-based failure root-cause analysis with fix suggestions (OpenAI, Anthropic, OpenRouter, Ollama)
- **Statistics & KPIs** — Pass rate trends, flaky test detection, heatmaps, deep analysis (15 KPIs in 5 categories)
- **AI Code Generation** — Generate `.robot` files from `.roboscope` YAML specs, reverse-engineer specs from `.robot` files
- **CI/CD Integration** — API tokens for service accounts, outbound webhooks (6 events), git webhook triggers for automatic test runs
- **Single Sign-On (SSO)** — OpenID Connect identity providers (Azure AD / Microsoft Entra ID, Google Workspace, GitHub, generic OIDC) with dry-run probe, group-to-team mapping and per-provider PDF/Markdown handoff document
- **Audit & Compliance** — Full audit log with CSV export, retention enforcement, secrets encryption at rest
- **rf-mcp Integration** — Optional Robot Framework keyword knowledge server for enhanced AI suggestions
- **Role-Based Access** — Four roles: Viewer, Runner, Editor, Admin
- **Multi-Language UI** — English, German, French, Spanish
- **In-App Documentation** — Searchable docs with print/PDF export
- **Offline Deployment** — Standalone ZIP with bundled dependencies for air-gapped environments

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2, Python 3.12+ |
| Frontend | Vue 3, TypeScript, Pinia, Vue Router, Chart.js, CodeMirror 6, Vite |
| Database | SQLite (default) or PostgreSQL |
| Tests | pytest (~885 tests), Vitest (113 tests), Playwright (~249 E2E tests) |
| AI | OpenAI, Anthropic, OpenRouter, Ollama (configurable) |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- No Redis or external services required

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

Download the latest `roboscope.zip` from [Releases](../../releases), then:

```bash
unzip roboscope.zip
cd roboscope
./install-mac-and-linux.sh       # Creates venv, installs dependencies offline
./start-mac-and-linux.sh         # Starts server at http://localhost:8000
```

On Windows, use `install-windows.bat` and `start-windows.bat` instead.

Default login: `admin@roboscope.local` / `admin123`

## Screenshots

| Dashboard | Test Explorer | Statistics |
|-----------|--------------|------------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Explorer](docs/screenshots/explorer.png) | ![Statistics](docs/screenshots/stats.png) |

## Project Structure

```
RoboScope/
├── backend/          # FastAPI application
│   ├── src/          # Source code (domain-driven modules)
│   │   ├── auth/     # JWT auth + RBAC
│   │   ├── repos/    # Git repository management
│   │   ├── explorer/ # File browser + Robot parser
│   │   ├── execution/# Test runs + scheduling
│   │   ├── environments/ # venv + packages
│   │   ├── reports/  # output.xml parser + comparison
│   │   ├── stats/    # KPIs + deep analysis
│   │   ├── ai/       # LLM integration (generate, reverse, analyze)
│   │   ├── settings/ # App settings
│   │   ├── webhooks/ # API tokens + webhooks
│   │   └── audit/    # Audit log + retention
│   ├── tests/        # pytest tests
│   ├── migrations/   # Alembic (SQLite + PostgreSQL)
│   └── examples/     # Example Robot Framework test files
├── frontend/         # Vue 3 + TypeScript SPA
│   └── src/
│       ├── views/    # 12 application views
│       ├── stores/   # 9 Pinia stores
│       ├── api/      # 9 Axios API clients
│       ├── docs/     # In-app documentation (EN, DE, FR, ES)
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
| `/api/v1/ai` | AI providers, code generation, failure analysis |
| `/api/v1/webhooks` | API tokens, outbound webhooks, git triggers |
| `/api/v1/audit` | Audit log, retention enforcement |
| `/api/v1/settings` | Application settings (admin) |

## Testing

```bash
make test-backend       # Backend unit tests (pytest)
make test-frontend      # Frontend unit tests (Vitest)
make test-e2e           # Playwright E2E tests
make test               # All tests
make lint               # Ruff + ESLint + vue-tsc
```

## Building

```bash
# Build standalone offline distribution
bash scripts/build-mac-and-linux.sh

# Output: dist/roboscope.zip (includes wheels for Linux, macOS, Windows)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./roboscope.db` | Database connection |
| `SECRET_KEY` | `dev-key` | JWT secret (change in production!) |
| `RUNNER_TYPE` | `auto` | `subprocess`, `docker`, or `auto` |
| `DEFAULT_TIMEOUT_SECONDS` | `3600` | Timeout per test run |
| `WORKSPACE_DIR` | `~/.roboscope/workspace` | Git repos directory |
| `REPORTS_DIR` | `~/.roboscope/reports` | Report files directory |
| `VENVS_DIR` | `~/.roboscope/venvs` | Virtual environments directory |

### Single Sign-On (SSO)

RoboScope supports OIDC identity providers for **Azure AD / Microsoft Entra ID**, **Google Workspace**, **GitHub** and any standards-compliant OIDC issuer (Okta, Keycloak, Auth0, Authentik, …). High-level setup:

1. Register a new web application at your IdP and note the **Client ID** + **Client Secret**.
2. Set the **Redirect URI** to `https://<your-roboscope-host>/auth/sso/callback`.
3. In RoboScope, log in as admin and open **Admin → Identity Providers → Add Provider**.
4. Fill in name, type, **Issuer URL**, Client ID/Secret, scopes (default `openid profile email`) and the **Group claim name** (default `groups`).
5. Click **Run Dry-Run** — only a passing probe unlocks **Save**.
6. Optional: download the **Hand-off PDF/Markdown** (per language) for the IdP admin team, and map IdP groups to RoboScope teams under **Admin → Teams**.

A local-password emergency bypass (`admin@roboscope.local` by default) remains available even if the IdP is unreachable. Full step-by-step guidance, including IdP-specific Issuer URL examples and group-mapping details, is in the **in-app documentation** under *Settings → Identity Providers (SSO)*.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'feat: add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Please follow the existing code style (Ruff for Python, ESLint for TypeScript) and include tests for new features.

## Security

Found a security issue? Please **don't** open a public issue. See [SECURITY.md](SECURITY.md) for the disclosure process and our supported-versions / known-advisories list.

## License

Licensed under the [Apache License 2.0](LICENSE).

Copyright 2026 [viadee Unternehmensberatung AG](https://www.viadee.de).

## Acknowledgments

- [Robot Framework](https://robotframework.org/) — The test automation framework
- [rf-mcp](https://github.com/manykarim/rf-mcp) by Many Kasiriha — Robot Framework keyword knowledge server
- Built with [FastAPI](https://fastapi.tiangolo.com/), [Vue.js](https://vuejs.org/), and [Playwright](https://playwright.dev/)
