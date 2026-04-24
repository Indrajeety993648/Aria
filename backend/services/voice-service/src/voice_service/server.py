"""Uvicorn entrypoint for voice-service."""
from __future__ import annotations

from .api import build_app

app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "voice_service.server:app",
        host="0.0.0.0",
        port=8003,
        log_level="info",
    )
