.PHONY: dev test lint typecheck migrate deploy clean docker-build docker-up docker-down help

PYTHON   := python3
PIP      := pip3
BACKEND  := backend
ENV_FILE := .env

help:
	@echo "SangamMW development commands"
	@echo ""
	@echo "  make dev          Start backend + frontend in development mode"
	@echo "  make test         Run unit + integration tests"
	@echo "  make test-unit    Run unit tests only (no Postgres needed)"
	@echo "  make lint         ruff check + ruff format check"
	@echo "  make fmt          Auto-fix formatting with ruff"
	@echo "  make typecheck    mypy type check"
	@echo "  make migrate      Run Alembic migrations"
	@echo "  make migrate-new  Create new migration (MSG=description)"
	@echo "  make docker-build Build Docker images"
	@echo "  make docker-up    Start Docker Compose (dev)"
	@echo "  make docker-down  Stop Docker Compose"
	@echo "  make deploy       Deploy to staging (requires DEPLOY_ENV)"
	@echo "  make key          Generate a new FERNET_KEY"
	@echo "  make clean        Remove build artifacts"

dev:
	@echo "→ Starting SangamMW dev server..."
	cd $(BACKEND) && uvicorn sangam_mw.api.main:app --reload --port 8000 &
	@echo "→ API: http://localhost:8000/docs"

test:
	cd $(BACKEND) && pytest tests/ -v --tb=short

test-unit:
	cd $(BACKEND) && pytest tests/unit/ -v --tb=short

test-integration:
	cd $(BACKEND) && pytest tests/integration/ -v --tb=short

test-cov:
	cd $(BACKEND) && pytest tests/ --cov=sangam_mw --cov-report=html --cov-report=term-missing
	@echo "→ Coverage report: backend/htmlcov/index.html"

lint:
	ruff check $(BACKEND)/
	ruff format --check $(BACKEND)/

fmt:
	ruff check --fix $(BACKEND)/
	ruff format $(BACKEND)/

typecheck:
	mypy $(BACKEND)/sangam_mw/ --ignore-missing-imports --no-strict-optional

migrate:
	cd $(BACKEND) && alembic upgrade head

migrate-down:
	cd $(BACKEND) && alembic downgrade -1

migrate-new:
	@test -n "$(MSG)" || (echo "Usage: make migrate-new MSG='description'" && exit 1)
	cd $(BACKEND) && alembic revision --autogenerate -m "$(MSG)"

docker-build:
	docker compose build

docker-up:
	docker compose up -d
	@echo "→ API: http://localhost:8000/docs"
	@echo "→ Adminer: http://localhost:8080"

docker-down:
	docker compose down

docker-prod-up:
	docker compose -f docker-compose.prod.yml up -d

docker-prod-down:
	docker compose -f docker-compose.prod.yml down

deploy:
	@test -n "$(DEPLOY_ENV)" || (echo "Usage: make deploy DEPLOY_ENV=staging" && exit 1)
	cd $(BACKEND) && sangam deploy --env $(DEPLOY_ENV)

key:
	cd $(BACKEND) && sangam generate-key

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml
	@echo "→ Clean"
