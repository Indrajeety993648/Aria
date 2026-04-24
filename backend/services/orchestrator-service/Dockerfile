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

# orchestrator-service itself
COPY backend/services/orchestrator-service /app/services/orchestrator-service

# Install in dependency order
RUN pip install /app/packages/aria-contracts \
 && pip install /app/services/orchestrator-service

# Sanity: import everything at build time so a broken package fails the build,
# not the container start.
RUN python -c "from orchestrator_service.server import app; print('orchestrator-service import OK')"

EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=10s \
    CMD curl -fsS http://localhost:8002/health || exit 1

CMD ["python", "-m", "uvicorn", "orchestrator_service.server:app", "--host", "0.0.0.0", "--port", "8002"]
