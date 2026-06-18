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

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
