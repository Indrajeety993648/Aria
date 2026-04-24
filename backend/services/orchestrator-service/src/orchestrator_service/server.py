"""uvicorn entrypoint."""
from __future__ import annotations

from orchestrator_service.api import build_app

app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "orchestrator_service.server:app",
        host="0.0.0.0",
        port=8002,
        log_level="info",
    )
