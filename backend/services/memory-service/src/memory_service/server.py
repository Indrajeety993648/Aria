"""Uvicorn entrypoint for memory-service.

``app`` is the module-level FastAPI instance (so uvicorn can load it by string
reference ``memory_service.server:app``). Running this module directly starts
a local server on port 8004.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from .api import build_app

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

app = build_app()


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        "memory_service.server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8004")),
        reload=False,
    )
