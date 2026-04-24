"""Stateful WebSocket client for env-service.

OpenEnv's HTTP endpoints are per-request stateless — only the `/ws` endpoint
holds a session. We keep one persistent connection per `session_id`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import websockets
from websockets.client import WebSocketClientProtocol

from aria_contracts import AriaAction

log = logging.getLogger(__name__)


def _default_ws_url() -> str:
    base = os.environ.get("ENV_SERVICE_URL", "http://env-service:8001").rstrip("/")
    # Swap scheme http -> ws, https -> wss.
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/ws"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/ws"
    return base + "/ws"


class EnvClient:
    """One client instance per orchestrator process; holds N WS sessions.

    Each `session_id` we hand out externally is backed by a single WebSocket
    connection to the env-service. We open it on first `reset()` and reuse it
    for every `step()` until explicitly closed.
    """

    def __init__(self, ws_url: str | None = None) -> None:
        self.ws_url: str = ws_url or _default_ws_url()
        self._sessions: dict[str, WebSocketClientProtocol] = {}
        self._last_observation: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #
    async def _open(self, session_id: str) -> WebSocketClientProtocol:
        """Open a new WS connection for this session (or return the live one)."""
        ws = self._sessions.get(session_id)
        if ws is not None and not ws.closed:
            return ws

        log.info("opening env-service WS for session %s -> %s", session_id, self.ws_url)
        ws = await websockets.connect(self.ws_url, max_size=2**22)
        self._sessions[session_id] = ws
        return ws

    async def _send_and_recv(
        self, ws: WebSocketClientProtocol, msg: dict[str, Any]
    ) -> dict[str, Any]:
        await ws.send(json.dumps(msg))
        raw = await ws.recv()
        resp = json.loads(raw)
        if resp.get("type") == "error":
            raise RuntimeError(f"env-service error: {resp.get('data')}")
        return resp.get("data", {})

    async def _ensure_live(self, session_id: str) -> WebSocketClientProtocol:
        """Open a fresh connection if the existing one was dropped."""
        async with self._lock:
            ws = self._sessions.get(session_id)
            if ws is None or ws.closed:
                return await self._open(session_id)
            return ws

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    async def reset(
        self,
        session_id: str,
        seed: int | None = None,
        category: str | None = None,
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        """Open a session (if needed) and send a reset. Returns observation dict."""
        ws = await self._ensure_live(session_id)
        data: dict[str, Any] = {}
        if seed is not None:
            data["seed"] = seed
        if category is not None:
            data["category"] = category
        if difficulty is not None:
            data["difficulty"] = difficulty
        obs = await self._send_and_recv(ws, {"type": "reset", "data": data})
        self._last_observation[session_id] = obs
        return obs

    async def step(self, session_id: str, action: AriaAction) -> dict[str, Any]:
        """Send a `step` and return the observation dict."""
        try:
            ws = await self._ensure_live(session_id)
            obs = await self._send_and_recv(
                ws, {"type": "step", "data": action.model_dump()}
            )
            self._last_observation[session_id] = obs
            return obs
        except (websockets.ConnectionClosed, ConnectionError) as exc:
            # Graceful reconnect: drop the dead socket and let the next call
            # re-open. The env session itself is gone, so we propagate.
            log.warning("WS dropped for session %s: %s", session_id, exc)
            self._sessions.pop(session_id, None)
            self._last_observation.pop(session_id, None)
            raise

    def get_last_observation(self, session_id: str) -> dict[str, Any] | None:
        """Return the last observation seen for this session, if any."""
        return self._last_observation.get(session_id)

    async def close(self, session_id: str) -> None:
        """Close a single session's WS."""
        ws = self._sessions.pop(session_id, None)
        self._last_observation.pop(session_id, None)
        if ws is None:
            return
        try:
            if not ws.closed:
                await ws.send(json.dumps({"type": "close"}))
                await ws.close()
        except Exception as exc:  # pragma: no cover — best-effort cleanup
            log.debug("ignoring WS close error for %s: %s", session_id, exc)

    async def close_all(self) -> None:
        """Close every outstanding session (used on app shutdown)."""
        for sid in list(self._sessions.keys()):
            await self.close(sid)


__all__ = ["EnvClient"]
