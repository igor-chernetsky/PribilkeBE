FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary \
    redis celery httpx beautifulsoup4 pydantic-settings python-dateutil

COPY src/ src/
ENV PYTHONPATH=/app/src

EXPOSE 8000
