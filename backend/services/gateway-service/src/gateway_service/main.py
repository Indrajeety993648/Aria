"""FastAPI app factory for the gateway service.

Every endpoint here is a proxy or a mux. No decisions live in this file.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gateway_service.clients import Clients
from gateway_service.ws_mux import WebSocketMux

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def build_app(clients: Clients | None = None) -> FastAPI:
    """Build the FastAPI app.

    `clients` is injectable for tests; in prod we read from env vars.
    """
    resolved_clients = clients or Clients.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await app.state.clients.aclose()

    app = FastAPI(
        title="ARIA Gateway",
        version="0.1.0",
        description="Public REST + WebSocket door for ARIA. Proxy-only.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Inject clients as app state so tests can monkeypatch.
    app.state.clients = resolved_clients
    app.state.ws_mux = WebSocketMux(resolved_clients)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        upstreams = await app.state.clients.health_map()
        overall = "healthy" if all(v == "healthy" for v in upstreams.values()) else "degraded"
        return {"status": overall, "upstreams": upstreams}

    @app.post("/session")
    async def create_session(request: Request) -> JSONResponse:
        body = await _safe_json(request)
        return await _proxy_post(app.state.clients.orchestrator, "/session", body)

    @app.delete("/session/{session_id}")
    async def delete_session(session_id: str) -> JSONResponse:
        return await _proxy_delete(
            app.state.clients.orchestrator, f"/session/{session_id}"
        )

    @app.post("/turn")
    async def turn(request: Request) -> JSONResponse:
        body = await _safe_json(request)
        return await _proxy_post(app.state.clients.orchestrator, "/turn", body)

    @app.websocket("/ws/session/{session_id}")
    async def ws_session(websocket: WebSocket, session_id: str) -> None:
        mux: WebSocketMux = app.state.ws_mux
        await mux.serve(websocket, session_id)

    return app


async def _safe_json(request: Request) -> Any:
    try:
        return await request.json()
    except Exception:
        return {}


async def _proxy_post(client: Any, path: str, body: Any) -> JSONResponse:
    try:
        resp = await client.post(path, json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc
    return _forward(resp)


async def _proxy_delete(client: Any, path: str) -> JSONResponse:
    try:
        resp = await client.delete(path)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}") from exc
    return _forward(resp)


def _forward(resp: httpx.Response) -> JSONResponse:
    """Forward an upstream httpx.Response as a JSONResponse 1:1."""
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": resp.text}
    return JSONResponse(status_code=resp.status_code, content=payload)
