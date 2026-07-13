FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gnupg \
    # Playwright browser system dependencies
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libdbus-1-3 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxcb1 \
    libxkbcommon0 \
    libasound2 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# pyproject's [tool.uv.sources] points robotframework-roboscopeheal at the
# vendored tree, so it must exist BEFORE the dependency-install layer — a
# pyproject-only COPY fails with "Distribution not found at
# file:///app/vendor/robotframework-roboscopeheal" (latent since the vendor
# flip; only surfaces when the install layer's cache is invalidated).
COPY backend/pyproject.toml .
COPY backend/vendor ./vendor
RUN uv pip install --system --no-cache-dir -e ".[dev]" 2>/dev/null || uv pip install --system --no-cache-dir .

COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
