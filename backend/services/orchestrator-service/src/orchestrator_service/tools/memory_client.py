"""Thin async HTTP client for memory-service.

Used fire-and-forget from the agent loop to persist an episodic trace of
each turn. All failures are swallowed with a warning — memory is a nice-to-
have, not on the critical path.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from aria_contracts.memory import MemoryWrite

log = logging.getLogger(__name__)


def _default_url() -> str:
    return os.environ.get(
        "MEMORY_SERVICE_URL", "http://memory-service:8004"
    ).rstrip("/")


class MemoryClient:
    """Best-effort writer. Never raises to the caller."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_s: float = 1.0,
    ) -> None:
        self.base_url = (base_url or _default_url()).rstrip("/")
        self._timeout = timeout_s

    async def write(self, payload: MemoryWrite) -> bool:
        """POST /write. Returns True on success, False on any failure."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self.base_url}/write",
                    json=payload.model_dump(),
                )
                r.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001 — best-effort path
            log.debug("memory write failed (%s); continuing without it", exc)
            return False


__all__ = ["MemoryClient"]
