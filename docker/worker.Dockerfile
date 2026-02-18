FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml .
RUN pip install --no-cache-dir .

COPY backend/ .

CMD ["celery", "-A", "src.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
