.PHONY: install lock test migrate revision dev docker-up docker-down lint

BACKEND := backend

install:
	cd $(BACKEND) && uv sync --all-groups

lock:
	cd $(BACKEND) && uv lock

test:
	cd $(BACKEND) && uv run pytest

migrate:
	cd $(BACKEND) && uv run alembic upgrade head

revision:
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

dev:
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker compose up -d postgres redis

docker-down:
	docker compose down

lint:
	cd $(BACKEND) && uv run ruff check app tests
