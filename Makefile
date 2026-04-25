# ARIA — developer commands
# Targets are deliberately few. Prefer docker compose for anything serving.

.PHONY: help install build up down logs test test-env test-env-full \
        fmt lint typecheck clean frontend-dev grade

help:
	@echo "ARIA developer commands"
	@echo "  make install        Install local dev dependencies (venv in .venv/)"
	@echo "  make build          docker compose build all services"
	@echo "  make up             docker compose up -d all services"
	@echo "  make down           docker compose down -v"
	@echo "  make logs           tail -f all service logs"
	@echo "  make test           Fast unit tests (stubs, no containers)"
	@echo "  make test-env       Env grader tests (judge-facing, mocked deps)"
	@echo "  make test-env-full  Env tests including live HTTP (spins env-service)"
	@echo "  make grade          Run mock judge: random/expert/do-nothing baselines"
	@echo "  make fmt            ruff format"
	@echo "  make lint           ruff check"
	@echo "  make typecheck      mypy on packages + services"
	@echo "  make frontend-dev   Start Next.js dev server"
	@echo "  make clean          Remove caches, build artifacts"

# -----------------------------------------------------------------------------
install:
	python -m venv .venv
	. .venv/bin/activate && pip install -U pip
	. .venv/bin/activate && pip install -e backend/packages/aria-contracts
	. .venv/bin/activate && pip install -e backend/packages/aria-scenarios
	. .venv/bin/activate && pip install -e backend/packages/aria-rewards
	. .venv/bin/activate && pip install -e "backend/services/env-service[dev]"
	. .venv/bin/activate && pip install -e backend/services/orchestrator-service
	. .venv/bin/activate && pip install pytest pytest-asyncio httpx ruff mypy

build:
	docker compose -f backend/docker-compose.yml build

up:
	docker compose -f backend/docker-compose.yml up -d

down:
	docker compose -f backend/docker-compose.yml down -v

logs:
	docker compose -f backend/docker-compose.yml logs -f

# -----------------------------------------------------------------------------
test:
	. .venv/bin/activate && pytest backend/packages -q

test-env:
	. .venv/bin/activate && pytest backend/tests/env -q

test-env-full:
	. .venv/bin/activate && pytest backend/tests/env -q --run-http

grade:
	. .venv/bin/activate && python backend/baselines/run_grade.py

# -----------------------------------------------------------------------------
fmt:
	. .venv/bin/activate && ruff format backend/

lint:
	. .venv/bin/activate && ruff check backend/

typecheck:
	. .venv/bin/activate && mypy backend/packages backend/services

frontend-dev:
	cd frontend && npm install && npm run dev

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv-probe/
