"""Gateway service tests.

We monkeypatch `Clients` so nothing reaches the network. These tests verify
the gateway behaves as a proxy/mux and never invents business logic.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway_service.clients import Clients, UpstreamClient
from gateway_service.main import build_app


class _FakeResponse:
    """Mimics the httpx.Response surface we touch in main/ws_mux."""

    def __init__(
        self, status_code: int = 200, json_body: Any | None = None, text: str = ""
    ) -> None:
        self.status_code = status_code
        self._json = json_body
        self.text = text or (json.dumps(json_body) if json_body is not None else "")

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeClient:
    """Drop-in for UpstreamClient. Records calls, returns scripted responses."""

    def __init__(self, name: str, healthy: bool = True) -> None:
        self.name = name
        self._healthy = healthy
        self.calls: list[tuple[str, str, Any]] = []
        self.post_response: _FakeResponse = _FakeResponse(200, {"ok": True})
        self.delete_response: _FakeResponse = _FakeResponse(200, {"deleted": True})

    async def aclose(self) -> None:
        pass

    async def healthy(self) -> bool:
        return self._healthy

    async def get(self, path: str, **_: Any) -> _FakeResponse:
        self.calls.append(("GET", path, None))
        return _FakeResponse(200, {"ok": True})

    async def post(self, path: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("POST", path, kwargs.get("json")))
        return self.post_response

    async def delete(self, path: str, **_: Any) -> _FakeResponse:
        self.calls.append(("DELETE", path, None))
        return self.delete_response


def _fake_clients(
    *,
    orch_healthy: bool = True,
    voice_healthy: bool = True,
    env_healthy: bool = True,
) -> Clients:
    orch = FakeClient("orchestrator", healthy=orch_healthy)
    voice = FakeClient("voice", healthy=voice_healthy)
    env = FakeClient("env", healthy=env_healthy)
    # Cast-by-duck: Clients only calls methods that FakeClient implements.
    return Clients(
        orchestrator=orch,  # type: ignore[arg-type]
        voice=voice,  # type: ignore[arg-type]
        env=env,  # type: ignore[arg-type]
    )


@pytest.fixture()
def clients() -> Clients:
    return _fake_clients()


@pytest.fixture()
def app(clients: Clients):
    return build_app(clients=clients)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def test_health_returns_upstream_dict(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert set(body["upstreams"].keys()) == {"orchestrator", "voice", "env"}
    assert all(v == "healthy" for v in body["upstreams"].values())


def test_health_degraded_when_upstream_down() -> None:
    clients = _fake_clients(orch_healthy=False)
    app = build_app(clients=clients)
    with TestClient(app) as c:
        body = c.get("/health").json()
    assert body["status"] == "degraded"
    assert body["upstreams"]["orchestrator"] == "degraded"
    assert body["upstreams"]["voice"] == "healthy"


def test_turn_proxies_to_orchestrator(app, client: TestClient) -> None:
    canned: dict[str, Any] = {
        "session_id": "s1",
        "reply_text": "ok, scheduled",
        "tool_calls": [],
        "mapped_env_action": {"action_id": "reply_to_email", "parameters": {}},
        "latency_ms": {"llm": 42},
    }
    orch: FakeClient = app.state.clients.orchestrator  # type: ignore[assignment]
    orch.post_response = _FakeResponse(200, canned)

    resp = client.post(
        "/turn",
        json={"session_id": "s1", "user_text": "hello", "mode": "simulated"},
    )
    assert resp.status_code == 200
    assert resp.json() == canned
    # Verify the proxy actually called orchestrator.
    assert any(
        call[0] == "POST" and call[1] == "/turn" for call in orch.calls
    )


def test_turn_502_on_upstream_error(app, client: TestClient) -> None:
    orch: FakeClient = app.state.clients.orchestrator  # type: ignore[assignment]

    async def boom(path: str, **kwargs: Any) -> _FakeResponse:  # noqa: ARG001
        raise httpx.ConnectError("connection refused")

    orch.post = boom  # type: ignore[assignment]

    resp = client.post("/turn", json={"session_id": "s1", "user_text": "x"})
    assert resp.status_code == 502


def test_delete_session_proxies(app, client: TestClient) -> None:
    orch: FakeClient = app.state.clients.orchestrator  # type: ignore[assignment]
    resp = client.delete("/session/abc")
    assert resp.status_code == 200
    assert any(
        call[0] == "DELETE" and call[1] == "/session/abc" for call in orch.calls
    )


def test_cors_preflight_on_turn(client: TestClient) -> None:
    resp = client.options(
        "/turn",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    # CORS middleware responds 200 for allowed origin.
    assert resp.status_code == 200
    assert (
        resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )
    assert "POST" in resp.headers.get("access-control-allow-methods", "")


def test_ws_emits_session_start_and_reply(app) -> None:
    orch: FakeClient = app.state.clients.orchestrator  # type: ignore[assignment]
    orch.post_response = _FakeResponse(
        200,
        {
            "session_id": "sess-42",
            "reply_text": "hi there",
            "tool_calls": [],
            "mapped_env_action": None,
            "latency_ms": {},
        },
    )

    with TestClient(app) as c, c.websocket_connect("/ws/session/sess-42") as ws:
        start = ws.receive_json()
        assert start["kind"] == "session_start"
        assert start["session_id"] == "sess-42"
        assert isinstance(start["ts_ms"], int) and start["ts_ms"] > 0

        ws.send_text("hello aria")

        transcript = ws.receive_json()
        assert transcript["kind"] == "final_transcript"
        assert transcript["payload"]["text"] == "hello aria"

        reply = ws.receive_json()
        assert reply["kind"] == "reply_text"
        assert reply["payload"]["text"] == "hi there"


def test_upstream_client_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCHESTRATOR_URL", raising=False)
    monkeypatch.delenv("VOICE_URL", raising=False)
    monkeypatch.delenv("ENV_URL", raising=False)
    c = Clients.from_env()
    assert isinstance(c.orchestrator, UpstreamClient)
    assert c.orchestrator.base_url.startswith("http://")
