.PHONY: install fmt lint test test-unit test-integration test-e2e dev migrate e2e-ai e2e-ui

install:
	uv sync --all-groups

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run mypy onto_platform

test:
	uv run pytest -m "not e2e and not live_llm"

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-e2e:
	uv run pytest tests/e2e -v -m e2e

test-all:
	uv run pytest

dev:
	uv run uvicorn onto_platform.app:create_app --factory --reload --port 8080

migrate:
	uv run alembic upgrade head

.PHONY: e2e-ai
e2e-ai:
	bash scripts/live-ai-setup.sh

.PHONY: e2e-ui
e2e-ui:
	bash scripts/e2e-ui.sh
