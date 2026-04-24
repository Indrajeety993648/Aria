"""Thin async HTTP clients for upstream services.

Gateway owns none of the logic — these are just typed wrappers around httpx.
Timeouts are intentionally short so a dead upstream surfaces fast.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

# Reasonable defaults per brief: 2s connect, 10s read.
_TIMEOUT = httpx.Timeout(connect=2.0, read=10.0, write=10.0, pool=2.0)


def _env(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val else default


class UpstreamClient:
    """Async HTTP client for one upstream service."""

    def __init__(self, name: str, base_url: str) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._client.delete(path, **kwargs)

    async def healthy(self) -> bool:
        """Probe /health. Swallow any error — we report degraded, we don't crash."""
        try:
            resp = await self._client.get("/health", timeout=2.0)
        except Exception:
            return False
        return resp.status_code == 200


class Clients:
    """Container of upstream clients used by the gateway app."""

    def __init__(
        self,
        orchestrator: UpstreamClient,
        voice: UpstreamClient,
        env: UpstreamClient,
    ) -> None:
        self.orchestrator = orchestrator
        self.voice = voice
        self.env = env

    @classmethod
    def from_env(cls) -> "Clients":
        return cls(
            orchestrator=UpstreamClient(
                "orchestrator",
                _env("ORCHESTRATOR_URL", "http://orchestrator-service:8002"),
            ),
            voice=UpstreamClient(
                "voice", _env("VOICE_URL", "http://voice-service:8003")
            ),
            env=UpstreamClient("env", _env("ENV_URL", "http://env-service:8001")),
        )

    async def aclose(self) -> None:
        for c in (self.orchestrator, self.voice, self.env):
            await c.aclose()

    async def health_map(self) -> dict[str, str]:
        """Best-effort per-upstream health: 'healthy' | 'degraded'."""
        results: dict[str, str] = {}
        for client in (self.orchestrator, self.voice, self.env):
            ok = await client.healthy()
            results[client.name] = "healthy" if ok else "degraded"
        return results
