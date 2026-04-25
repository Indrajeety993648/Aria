"""End-to-end integration: gateway WS → orchestrator /turn → AriaEnv.

Proves that a single user-typed sentence flowing into the gateway's
WebSocket ends up as an `AriaAction` on a real `AriaEnv` instance and that
a reward event comes back to the client.

No network. No docker. Everything wires through ASGI in-process:
  - gateway's httpx clients swap to `httpx.ASGITransport(app=orchestrator_app)`
  - orchestrator's `EnvClient` swaps to an in-process fake backed by `AriaEnv`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

# Make sibling services importable without docker
_REPO = Path(__file__).resolve().parents[2]
for pkg in (
    _REPO / "services" / "env-service" / "src",
    _REPO / "services" / "orchestrator-service" / "src",
    _REPO / "services" / "gateway-service" / "src",
):
    p = str(pkg)
    if p not in sys.path:
        sys.path.insert(0, p)

from aria_contracts import AriaAction
from env_service.aria_env import AriaEnv  # type: ignore[import-not-found]
from gateway_service.clients import Clients, UpstreamClient  # type: ignore[import-not-found]
from gateway_service.main import build_app as build_gateway  # type: ignore[import-not-found]
from orchestrator_service.api import build_app as build_orchestrator  # type: ignore[import-not-found]


class InProcessEnvClient:
    """Stand-in for orchestrator's EnvClient — backed by a real AriaEnv.

    Same public surface the orchestrator relies on (`reset`, `step`,
    `close_all`, `last_observation`). Keeps one AriaEnv per session_id.
    """

    def __init__(self) -> None:
        self._envs: dict[str, AriaEnv] = {}
        self._last: dict[str, dict[str, Any]] = {}

    async def reset(
        self,
        session_id: str,
        seed: int | None = None,
        category: str | None = None,
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        env = AriaEnv()
        obs = env.reset(
            seed=seed,
            category=category or "calendar_conflict",
            difficulty=difficulty or "medium",
        )
        self._envs[session_id] = env
        self._last[session_id] = obs.model_dump()
        return self._last[session_id]

    async def step(self, session_id: str, action: AriaAction) -> dict[str, Any]:
        env = self._envs.get(session_id)
        if env is None:
            # First step without explicit reset — do one lazily.
            await self.reset(session_id)
            env = self._envs[session_id]
        obs = env.step(action)
        self._last[session_id] = obs.model_dump()
        return self._last[session_id]

    def last_observation(self, session_id: str) -> dict[str, Any]:
        return self._last.get(session_id, {})

    # Orchestrator uses this name when pulling the most recent obs.
    def get_last_observation(self, session_id: str) -> dict[str, Any]:
        return self._last.get(session_id, {})

    async def close(self, session_id: str) -> None:
        self._envs.pop(session_id, None)
        self._last.pop(session_id, None)

    async def close_all(self) -> None:
        self._envs.clear()
        self._last.clear()


def _asgi_upstream(name: str, app) -> UpstreamClient:
    """Build an UpstreamClient that routes over ASGI — no real sockets.

    We construct UpstreamClient with a dummy URL then hot-swap `_client`
    before any requests fire. The original httpx client is discarded; it
    holds no OS resources until first use, so skipping aclose() is safe.
    """
    c = UpstreamClient(name, "http://testserver")
    c._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
    )
    return c


@pytest.fixture
def pipeline():
    env_client = InProcessEnvClient()
    orch_app = build_orchestrator(env_client=env_client)  # type: ignore[arg-type]

    orch_upstream = _asgi_upstream("orchestrator", orch_app)
    # Voice + env upstreams are not reached in this test, but Clients
    # expects three. Point them at a throwaway dummy.
    dummy_app = build_orchestrator(env_client=env_client)  # type: ignore[arg-type]
    clients = Clients(
        orchestrator=orch_upstream,
        voice=_asgi_upstream("voice", dummy_app),
        env=_asgi_upstream("env", dummy_app),
    )

    gw_app = build_gateway(clients=clients)
    gw_client = TestClient(gw_app)
    yield gw_client
    gw_client.close()


def test_gateway_turn_proxies_to_orchestrator(pipeline: TestClient):
    """REST path: POST /turn through gateway → orchestrator → env."""
    r = pipeline.post(
        "/turn",
        json={
            "session_id": "sess-rest",
            "user_text": "resolve my 5pm conflict",
            "mode": "simulated",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"] == "sess-rest"
    assert isinstance(body.get("reply_text"), str) and body["reply_text"]
    # Simulated mode must carry a mapped env action.
    mapped = body.get("mapped_env_action")
    assert mapped is not None
    assert 0 <= int(mapped["action_id"]) <= 14


def test_ws_full_pipeline_emits_events(pipeline: TestClient):
    """WS path: client text → final_transcript + orchestrator fan-out."""
    with pipeline.websocket_connect("/ws/session/sess-ws") as ws:
        # Server emits session_start on open.
        first = json.loads(ws.receive_text())
        assert first["kind"] == "session_start"
        assert first["session_id"] == "sess-ws"

        # Send a text turn. Gateway accepts raw strings or {"user_text": ...}.
        ws.send_text(json.dumps({"user_text": "resolve my 5pm conflict"}))

        # Collect the full fan-out. Gateway emits in order: reply_text,
        # tool_calls*, env_step?, reward? — drain until we see env_step or timeout.
        kinds: list[str] = []
        for _ in range(30):
            try:
                ev = json.loads(ws.receive_text())
            except Exception:
                break
            kinds.append(ev["kind"])
            if ev["kind"] == "env_step":
                break

        assert "final_transcript" in kinds
        assert "reply_text" in kinds
        assert "env_step" in kinds, f"expected env_step among {kinds}"
