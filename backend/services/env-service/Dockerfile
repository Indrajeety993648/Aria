FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared packages first — they're the stable base for Docker layer caching.
# docker-compose sets context to the repo root so these paths resolve.
COPY backend/packages/aria-contracts /app/packages/aria-contracts
COPY backend/packages/aria-scenarios /app/packages/aria-scenarios
COPY backend/packages/aria-rewards   /app/packages/aria-rewards

# env-service itself
COPY backend/services/env-service /app/services/env-service

# Install in dependency order
RUN pip install /app/packages/aria-contracts \
 && pip install /app/packages/aria-scenarios \
 && pip install /app/packages/aria-rewards \
 && pip install /app/services/env-service

# Sanity: import everything at build time so a broken package fails the build,
# not the container start.
RUN python -c "from env_service.server import app; print('env-service import OK')"

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=10s \
    CMD curl -fsS http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "env_service.server:app", "--host", "0.0.0.0", "--port", "8001"]
