.PHONY: help dev backend frontend install test lint clean docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Development ---

install: ## Install all dependencies
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
	cd backend && uv pip install -e ".[dev]"
	cd frontend && npm ci
	cd e2e && npm ci

dev: ## Start development servers (backend + frontend)
	@echo "Starting backend on :8000 and frontend on :5173..."
	cd backend && uvicorn src.main:app --reload --port 8000 &
	cd frontend && npm run dev &
	wait

backend: ## Start backend only
	cd backend && uvicorn src.main:app --reload --port 8000

frontend: ## Start frontend only
	cd frontend && npm run dev

# --- Testing ---

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && pytest -v --tb=short

test-backend-cov: ## Run backend tests with coverage
	cd backend && pytest --cov=src --cov-report=html --cov-report=term

test-frontend: ## Run frontend unit tests
	cd frontend && npm run test:unit -- --run

test-frontend-cov: ## Run frontend tests with coverage
	cd frontend && npm run test:unit -- --run --coverage

test-e2e: ## Run E2E tests with Playwright
	cd e2e && npx playwright test

test-e2e-ui: ## Run E2E tests with Playwright UI
	cd e2e && npx playwright test --ui

test-e2e-headed: ## Run E2E tests in headed mode
	cd e2e && npx playwright test --headed

# --- Code Quality ---

lint: ## Run all linters
	cd backend && ruff check src/ tests/
	cd backend && ruff format --check src/ tests/
	cd frontend && npm run lint
	cd frontend && npm run type-check

format: ## Format all code
	cd backend && ruff format src/ tests/
	cd backend && ruff check --fix src/ tests/

typecheck: ## Run type checking
	cd backend && mypy src/
	cd frontend && npm run type-check

# --- Docker ---

docker-up: ## Start all services with Docker
	docker compose up -d --build

docker-down: ## Stop all Docker services
	docker compose down

docker-dev: ## Start dev environment with Docker
	docker compose -f docker-compose.dev.yml up -d --build

docker-test: ## Run tests in Docker
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

docker-logs: ## Show Docker logs
	docker compose logs -f

# --- Database ---

db-migrate: ## Create a new migration
	cd backend && alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply migrations
	cd backend && alembic upgrade head

db-downgrade: ## Rollback last migration
	cd backend && alembic downgrade -1

# --- Build / Distribution ---

build-dist: ## Build standalone distribution ZIP
	./scripts/build-mac-and-linux.sh

# --- Cleanup ---

clean: ## Clean build artifacts
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/htmlcov
	rm -rf frontend/dist frontend/node_modules/.vite
	rm -rf e2e/playwright-report e2e/test-results
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
