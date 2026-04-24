"""WebSocket multiplexer.

Accepts a frontend WS connection, opens a logical session, and emits a single
stream of `GwAgentEvent`s. In mock mode we just forward the client's text
message to the orchestrator and synthesize events from its response; the real
voice-service fan-in is pluggable later without touching the client shape.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from aria_contracts import GwAgentEvent, GwSessionStart
from fastapi import WebSocket, WebSocketDisconnect

from gateway_service.clients import Clients

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _event(session_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return GwAgentEvent(
        session_id=session_id,
        kind=kind,  # type: ignore[arg-type]
        payload=payload,
        ts_ms=_now_ms(),
    ).model_dump()


class WebSocketMux:
    """Owns one client WS connection for the lifetime of a session."""

    def __init__(self, clients: Clients) -> None:
        self.clients = clients

    async def serve(self, ws: WebSocket, session_id: str) -> None:
        await ws.accept()
        await self._emit_session_start(ws, session_id)

        try:
            while True:
                raw = await ws.receive_text()
                await self._handle_client_message(ws, session_id, raw)
        except WebSocketDisconnect:
            logger.info("ws client disconnected session=%s", session_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("ws error session=%s", session_id)
            await self._safe_send(
                ws, _event(session_id, "error", {"message": str(exc)})
            )

    async def _emit_session_start(self, ws: WebSocket, session_id: str) -> None:
        start = GwSessionStart(session_id=session_id)
        await ws.send_json(
            _event(session_id, "session_start", start.model_dump())
        )

    async def _handle_client_message(
        self, ws: WebSocket, session_id: str, raw: str
    ) -> None:
        """Treat each client text frame as a user turn.

        We accept either a plain string of user text, or a JSON object with a
        `user_text` field. We forward it to the orchestrator and emit the
        response as a sequence of typed events.
        """
        user_text = _extract_user_text(raw)

        # Echo the transcript back so the UI can render immediately.
        await ws.send_json(
            _event(session_id, "final_transcript", {"text": user_text})
        )

        try:
            resp = await self.clients.orchestrator.post(
                "/turn",
                json={
                    "session_id": session_id,
                    "user_text": user_text,
                    "mode": "simulated",
                },
            )
        except Exception as exc:
            await ws.send_json(
                _event(
                    session_id,
                    "error",
                    {"message": f"orchestrator unreachable: {exc}"},
                )
            )
            return

        if resp.status_code != 200:
            await ws.send_json(
                _event(
                    session_id,
                    "error",
                    {"status": resp.status_code, "body": resp.text[:500]},
                )
            )
            return

        data = resp.json()
        await self._fanout_turn_response(ws, session_id, data)

    async def _fanout_turn_response(
        self, ws: WebSocket, session_id: str, data: dict[str, Any]
    ) -> None:
        """Split an `AgentTurnResponse` into a stream of typed events."""
        reply = data.get("reply_text")
        if reply:
            await ws.send_json(
                _event(session_id, "reply_text", {"text": reply})
            )

        for call in data.get("tool_calls") or []:
            await ws.send_json(_event(session_id, "tool_call", call))

        mapped = data.get("mapped_env_action")
        if mapped:
            await ws.send_json(_event(session_id, "env_step", {"action": mapped}))

        reward = data.get("reward")
        if reward:
            await ws.send_json(_event(session_id, "reward", reward))

    @staticmethod
    async def _safe_send(ws: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await ws.send_json(payload)
        except Exception:  # pragma: no cover
            pass


def _extract_user_text(raw: str) -> str:
    """Accept either a raw string or a JSON envelope with `user_text`."""
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and isinstance(obj.get("user_text"), str):
                return obj["user_text"]
        except json.JSONDecodeError:
            pass
    return stripped
