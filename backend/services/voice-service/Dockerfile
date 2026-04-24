FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MOCK_VOICE=1 \
    ARIA_DOWNLOAD_MODELS=0

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared packages first — stable base for Docker layer caching.
# docker-compose sets context to the repo root so these paths resolve.
COPY backend/packages/aria-contracts /app/packages/aria-contracts

# voice-service itself
COPY backend/services/voice-service /app/services/voice-service

# Install in dependency order. Only `.` (no [real] extras) — default image is mock-only,
# no model weights, no faster-whisper, no piper. Opt-in via a downstream image.
RUN pip install /app/packages/aria-contracts \
 && pip install /app/services/voice-service

# Sanity: import the app at build time so a broken package fails the build,
# not the container start. Must not require model files.
RUN python -c "from voice_service.server import app; print('voice-service import OK')"

EXPOSE 8003

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=10s \
    CMD curl -fsS http://localhost:8003/health || exit 1

CMD ["python", "-m", "uvicorn", "voice_service.server:app", "--host", "0.0.0.0", "--port", "8003"]
