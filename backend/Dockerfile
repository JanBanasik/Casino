FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
# Include the optional "payments" group so the Stripe SDK is available for real
# Checkout. (The "ml" group stays out — bots fall back to BasicStrategy.)
RUN uv sync --frozen --no-dev --group payments

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

ENV PYTHONPATH=/app
EXPOSE 8000

# Shell form so $PORT (set by Render) is expanded and migrations run first.
# Local docker-compose overrides this with its own command.
CMD sh -c "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
