.PHONY: install lint format typecheck test test-cov run stdio compose-up compose-down

install:
	uv sync --all-groups

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy src

test:
	uv run pytest -q

test-cov:
	uv run pytest --cov --cov-report=term-missing --cov-fail-under=80

run:
	uv run uvicorn enterprise_mcp.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

stdio:
	uv run enterprise-mcp --transport stdio

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v
