.PHONY: help install install-dev test run status doctor config tools dashboard lint format clean docker-build docker-run docker-ask docker-dashboard docker-down

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest

help:
	@echo "GraphOS — Developer Command Reference"
	@echo "====================================="
	@echo "  make run                  Launch interactive GraphOS terminal agent"
	@echo "  make ask Q='<question>'   Execute a one-shot investigation query"
	@echo "  make doctor               Run system health & connectivity diagnostic check"
	@echo "  make status               Display live status of model, graph & tools"
	@echo "  make tools                List discovered read-only MCP tools"
	@echo "  make test                 Run full test suite (42 tests)"
	@echo "  make dashboard            Launch Streamlit graph visualization dashboard"
	@echo "  make docker-build         Build graphos:latest Docker image"
	@echo "  make docker-run           Run interactive agent container"
	@echo "  make docker-ask Q='...'   Run one-shot investigation inside Docker"
	@echo "  make docker-dashboard     Run Streamlit dashboard container on http://localhost:8501"
	@echo "  make docker-down          Stop all Docker Compose services"
	@echo "  make clean                Clean Python cache and temporary session files"

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install -e .

run:
	$(PYTHON) -m agent

ask:
	$(PYTHON) -m agent ask "$(Q)"

status:
	$(PYTHON) -m agent status

doctor:
	$(PYTHON) -m agent doctor

config:
	$(PYTHON) -m agent config

tools:
	$(PYTHON) -m agent tools

test:
	$(PYTEST) tests

dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py

docker-build:
	docker build -t graphos:latest .

docker-run:
	docker compose run --rm agent

docker-ask:
	docker compose run --rm agent ask "$(Q)"

docker-dashboard:
	docker compose up -d dashboard
	@echo "GraphOS Dashboard running at http://localhost:8501"

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	rm -rf .pytest_cache/ htmlcov/ .coverage
