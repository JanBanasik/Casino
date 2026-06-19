.PHONY: install lock test migrate revision dev docker-up docker-down lint frontend-install frontend-dev frontend-build prod-up prod-down

BACKEND := backend
FRONTEND := frontend

install:
	cd $(BACKEND) && uv sync --all-groups

frontend-install:
	cd $(FRONTEND) && npm install

frontend-dev:
	cd $(FRONTEND) && npm run dev

frontend-build:
	cd $(FRONTEND) && npm run build

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

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
