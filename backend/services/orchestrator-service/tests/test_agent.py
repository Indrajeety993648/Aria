"""Tests for the AgentLoop and the /turn endpoint.

The env-service WebSocket is never touched — we monkeypatch `EnvClient` with
an in-process fake that records the sequence of calls.
"""
from __future__ import annotations

from typing import Any

import pytest

from aria_contracts import ActionId, AgentTurnRequest, AriaAction
from orchestrator_service.agent import AgentLoop
from orchestrator_service.api import build_app
from orchestrator_service.tools.env_client import EnvClient


class FakeEnvClient(EnvClient):
    """Drop-in replacement that never opens a real WebSocket."""

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # Skip parent init — we don't want any real sockets.
        self.ws_url = "ws://fake/ws"
        self._sessions = {}
        self.reset_calls: list[dict[str, Any]] = []
        self.step_calls: list[tuple[str, AriaAction]] = []
        self.close_calls: list[str] = []

    async def reset(  # type: ignore[override]
        self,
        session_id: str,
        seed: int | None = None,
        category: str | None = None,
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        self.reset_calls.append(
            {
                "session_id": session_id,
                "seed": seed,
                "category": category,
                "difficulty": difficulty,
            }
        )
        return {"time": 0.0, "location": "home", "step_count": 0, "max_steps": 50}

    async def step(  # type: ignore[override]
        self, session_id: str, action: AriaAction
    ) -> dict[str, Any]:
        self.step_calls.append((session_id, action))
        return {
            "time": 0.1,
            "location": "home",
            "step_count": len(self.step_calls),
            "max_steps": 50,
            "done": False,
        }

    async def close(self, session_id: str) -> None:  # type: ignore[override]
        self.close_calls.append(session_id)

    async def close_all(self) -> None:  # type: ignore[override]
        for sid in list(self._sessions.keys()):
            await self.close(sid)


# --------------------------------------------------------------------------- #
# Direct AgentLoop tests                                                      #
# --------------------------------------------------------------------------- #


async def test_turn_returns_well_formed_response() -> None:
    fake = FakeEnvClient()
    loop = AgentLoop(env_client=fake)
    req = AgentTurnRequest(
        session_id="s1", user_text="reschedule my 3pm", mode="simulated"
    )

    resp = await loop.turn(req)

    assert resp.session_id == "s1"
    assert resp.reply_text
    assert resp.mapped_env_action is not None
    assert resp.mapped_env_action.action_id == int(ActionId.RESCHEDULE)
    # The step call should have fired exactly once.
    assert len(fake.step_calls) == 1
    assert fake.step_calls[0][0] == "s1"
    # Latency dict should be populated.
    assert "parse" in resp.latency_ms and "env_step" in resp.latency_ms
    # Simulated mode => no live tool calls.
    assert resp.tool_calls == []


async def test_live_mode_dispatches_tool_calls() -> None:
    fake = FakeEnvClient()
    loop = AgentLoop(env_client=fake)
    req = AgentTurnRequest(
        session_id="s2",
        user_text="reply to email_42 from Dana",
        mode="live",
    )
    resp = await loop.turn(req)

    assert resp.mapped_env_action is not None
    assert resp.mapped_env_action.action_id == int(ActionId.DRAFT_REPLY)
    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.tool_name == "gmail.send_email"
    assert tc.result is not None
    assert tc.result.get("status") == "queued"


async def test_env_failure_does_not_crash_turn() -> None:
    """If the env step raises, the turn still returns a response."""

    class BrokenClient(FakeEnvClient):
        async def step(self, session_id: str, action: AriaAction) -> dict[str, Any]:  # type: ignore[override]
            raise RuntimeError("simulated env outage")

    loop = AgentLoop(env_client=BrokenClient())
    req = AgentTurnRequest(session_id="s3", user_text="cancel the standup")
    resp = await loop.turn(req)

    assert resp.mapped_env_action is not None
    assert resp.mapped_env_action.action_id == int(ActionId.CANCEL)


async def test_wait_fallback_returns_wait_action() -> None:
    fake = FakeEnvClient()
    loop = AgentLoop(env_client=fake)
    req = AgentTurnRequest(session_id="s4", user_text="qwertyuiop nonsense")
    resp = await loop.turn(req)
    assert resp.mapped_env_action is not None
    assert resp.mapped_env_action.action_id == int(ActionId.WAIT)


# --------------------------------------------------------------------------- #
# FastAPI endpoint tests                                                      #
# --------------------------------------------------------------------------- #


def test_health_endpoint() -> None:
    from fastapi.testclient import TestClient

    fake = FakeEnvClient()
    app = build_app(env_client=fake)
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_turn_endpoint_roundtrip() -> None:
    from fastapi.testclient import TestClient

    fake = FakeEnvClient()
    app = build_app(env_client=fake)
    with TestClient(app) as client:
        body = {
            "session_id": "abc",
            "user_text": "schedule a coffee with Bob",
            "mode": "simulated",
        }
        r = client.post("/turn", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["session_id"] == "abc"
        assert data["mapped_env_action"]["action_id"] == int(ActionId.SCHEDULE)
        assert data["reply_text"]


def test_session_create_and_close() -> None:
    from fastapi.testclient import TestClient

    fake = FakeEnvClient()
    app = build_app(env_client=fake)
    with TestClient(app) as client:
        r = client.post("/session", json={"seed": 7, "difficulty": "medium"})
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        assert sid
        assert fake.reset_calls[-1]["seed"] == 7
        r2 = client.delete(f"/session/{sid}")
        assert r2.status_code == 200
        assert fake.close_calls[-1] == sid


def test_session_create_502_when_env_down() -> None:
    from fastapi.testclient import TestClient

    class DownClient(FakeEnvClient):
        async def reset(self, *a, **kw):  # type: ignore[override]
            raise ConnectionError("env-service down")

    app = build_app(env_client=DownClient())
    with TestClient(app) as client:
        r = client.post("/session", json={})
        assert r.status_code == 502
