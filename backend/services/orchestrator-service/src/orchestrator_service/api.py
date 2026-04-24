"""FastAPI routes for the orchestrator-service."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from aria_contracts import AgentTurnRequest, AgentTurnResponse
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from orchestrator_service.agent import AgentLoop
from orchestrator_service.tools.env_client import EnvClient

log = logging.getLogger(__name__)


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int | None = None
    category: str | None = None
    difficulty: str | None = None


class SessionCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    observation: dict[str, Any] = Field(default_factory=dict)


def build_app(env_client: EnvClient | None = None) -> FastAPI:
    """Construct the FastAPI app.

    Accepts an optional pre-built `EnvClient` so tests can inject a fake WS
    client without patching globals.
    """
    app = FastAPI(
        title="aria-orchestrator",
        version="0.1.0",
        description="ARIA orchestrator (agent-loop) microservice.",
    )

    client = env_client or EnvClient()
    loop = AgentLoop(env_client=client)

    # Expose on app.state so tests / hooks can swap them if needed.
    app.state.env_client = client
    app.state.agent_loop = loop

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/session", response_model=SessionCreateResponse)
    async def create_session(
        req: SessionCreateRequest = Body(default_factory=SessionCreateRequest),
    ) -> SessionCreateResponse:
        session_id = uuid.uuid4().hex
        try:
            obs = await client.reset(
                session_id,
                seed=req.seed,
                category=req.category,
                difficulty=req.difficulty,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"env-service unavailable: {exc}"
            ) from exc
        return SessionCreateResponse(session_id=session_id, observation=obs)

    @app.delete("/session/{session_id}")
    async def close_session(session_id: str) -> dict[str, str]:
        await client.close(session_id)
        return {"status": "closed", "session_id": session_id}

    @app.post("/turn", response_model=AgentTurnResponse)
    async def turn(req: AgentTurnRequest) -> AgentTurnResponse:
        return await loop.turn(req)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await client.close_all()

    return app


__all__ = ["build_app", "SessionCreateRequest", "SessionCreateResponse"]
