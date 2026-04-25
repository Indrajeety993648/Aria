"""HTTP + WebSocket surface tests against the FastAPI app from `build_app()`.

Uses `starlette.testclient.TestClient` against the in-process app — no real
server or network, and WebSocket sessions work via the same client. The
heavier "run a real server" check is gated on --run-http.

Contract note (see env-service/OPENENV_API_NOTES.md): HTTP /reset and /step
are **stateless** — each request spins a fresh env via the factory. Multi-step
episodes use the WebSocket session.
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from env_service.server import build_app

    app = build_app()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Stateless HTTP routes
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_200(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_metadata_endpoint_names_env(client: TestClient) -> None:
    r = client.get("/metadata")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "aria-personal-manager-v1"


def test_schema_endpoint_exposes_action_and_observation_fields(
    client: TestClient,
) -> None:
    r = client.get("/schema")
    assert r.status_code == 200
    dumped = str(r.json())
    assert "action_id" in dumped
    assert "calendar" in dumped
    assert "inbox" in dumped


def test_reset_endpoint_returns_observation_with_expected_shape(
    client: TestClient,
) -> None:
    r = client.post("/reset", json={"seed": 7})
    assert r.status_code == 200
    body = r.json()
    # OpenEnv shape: {observation, reward, done}
    assert set(body.keys()) >= {"observation", "done"}
    assert body["done"] is False
    obs = body["observation"]
    assert obs["step_count"] == 0
    assert "calendar" in obs and isinstance(obs["calendar"], list)
    assert "inbox" in obs and isinstance(obs["inbox"], list)


def test_reset_with_category_and_difficulty(client: TestClient) -> None:
    r = client.post(
        "/reset",
        json={"seed": 1, "category": "email_triage", "difficulty": "medium"},
    )
    assert r.status_code == 200
    obs = r.json()["observation"]
    assert obs["scenario_category"] == "email_triage"
    assert obs["difficulty"] == "medium"


# ---------------------------------------------------------------------------
# Stateful WebSocket session
# ---------------------------------------------------------------------------


def test_websocket_reset_then_step(client: TestClient) -> None:
    """Full loop: WS connects → reset → step → observation carries step_count=1."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "type": "reset",
                "data": {
                    "seed": 3,
                    "category": "email_triage",
                    "difficulty": "medium",
                },
            }
        )
        msg = ws.receive_json()
        assert msg["type"] == "observation"
        obs = msg["data"]["observation"]
        assert obs["step_count"] == 0

        # WS step payload is flat (action_id/target_id/payload directly under
        # `data`), unlike HTTP /step which wraps them under `action`.
        ws.send_json(
            {
                "type": "step",
                "data": {"action_id": 13, "target_id": None, "payload": {}},
            }
        )
        msg2 = ws.receive_json()
        assert msg2["type"] == "observation"
        obs2 = msg2["data"]["observation"]
        assert obs2["step_count"] == 1


def test_websocket_step_rejects_invalid_action_id(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "reset", "data": {"seed": 1}})
        _ = ws.receive_json()
        ws.send_json({"type": "step", "data": {"action_id": 99}})
        msg = ws.receive_json()
        assert msg["type"] == "error"


# ---------------------------------------------------------------------------
# Real server (opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.http
def test_real_http_server_starts_and_serves_health() -> None:
    """Spin a real uvicorn server in a subprocess and hit /health.

    Gated on --run-http because it binds a socket and takes ~1 s.
    """
    import socket
    import subprocess
    import sys
    import time
    import urllib.request

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "env_service.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
    )
    try:
        deadline = time.time() + 10.0
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1.0
                ) as resp:
                    assert resp.status == 200
                    return
            except Exception as e:  # noqa: BLE001 — expected during warm-up
                last_err = e
                time.sleep(0.2)
        raise AssertionError(f"server never came up: {last_err!r}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
