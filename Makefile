.PHONY: help test test-live lint fmt build up down logs clean

help:
	@echo "test   - run the suite with coverage"
	@echo "test-live - run the live suite against a running stack"
	@echo "lint   - ruff check"
	@echo "fmt    - ruff format"
	@echo "build  - build container images"
	@echo "up     - start the stack (api + qdrant)"
	@echo "down   - stop the stack"
	@echo "logs   - follow api logs"
	@echo "clean  - stop the stack and delete its volumes"

test:
	poetry run pytest tests/ --cov=lumora --cov-report=term-missing

# Requires the stack to be up. Override the port if API_PORT is not 8000:
#   make test-live LUMORA_TEST_BASE_URL=http://127.0.0.1:8010
LUMORA_TEST_BASE_URL ?= http://127.0.0.1:8000
test-live:
	LUMORA_TEST_BASE_URL=$(LUMORA_TEST_BASE_URL) poetry run pytest tests/test_week4_manual.py

lint:
	poetry run ruff check .

fmt:
	poetry run ruff format .

build:
	docker compose build

up:
	docker compose up

down:
	docker compose down

logs:
	docker compose logs -f api

# Drops indexed vectors and cloned repositories along with the containers.
clean:
	docker compose down -v
