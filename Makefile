.PHONY: help dev test db-up db-down db-init mobile clean

PYTHON ?= ./.venv/Scripts/python.exe
ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
    .SHELLFLAGS := -NoProfile -Command
else
    PYTHON ?= ./.venv/bin/python
endif

help:
	@echo "=================================================================="
	@echo "  Hyperlocal Marketplace - Makefile Developer Commands            "
	@echo "=================================================================="
	@echo "  make dev       - Orchestrate full stack (Docker DB + Backend + Web)"
	@echo "  make test      - Run comprehensive pytest integration test suite"
	@echo "  make db-up     - Start PostgreSQL container with PostGIS & pgvector"
	@echo "  make db-down   - Stop PostgreSQL container"
	@echo "  make db-init   - Re-initialize database schema and seed fixtures"
	@echo "  make mobile    - Start Expo React Native mobile interface"
	@echo "  make clean     - Remove python caches and temporary test artifacts"
	@echo "=================================================================="

dev:
ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File .\run_dev.ps1
else
	./run_dev.sh
endif

test:
	$(PYTHON) -m pytest backend/tests -v

db-up:
	docker compose up -d

db-down:
	docker compose down

db-init:
	$(PYTHON) -m backend.init_db --seed

mobile:
	cd frontend-mobile && npx expo start

clean:
	rm -rf .pytest_cache backend/__pycache__ backend/routers/__pycache__ backend/tests/__pycache__
