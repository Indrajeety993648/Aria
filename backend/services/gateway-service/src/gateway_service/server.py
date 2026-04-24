"""Uvicorn entrypoint: `python -m uvicorn gateway_service.server:app`."""
from __future__ import annotations

from gateway_service.main import build_app

app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "gateway_service.server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
