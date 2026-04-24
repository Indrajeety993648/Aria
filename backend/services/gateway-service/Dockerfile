FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared packages first — stable base for Docker layer caching.
# docker-compose sets context to the repo root so these paths resolve.
COPY backend/packages/aria-contracts /app/packages/aria-contracts

# gateway-service itself
COPY backend/services/gateway-service /app/services/gateway-service

# Install in dependency order
RUN pip install /app/packages/aria-contracts \
 && pip install /app/services/gateway-service

# Sanity: fail the build if anything is broken at import time.
RUN python -c "from gateway_service.server import app; print('gateway-service import OK')"

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=10s \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "gateway_service.server:app", "--host", "0.0.0.0", "--port", "8000"]
