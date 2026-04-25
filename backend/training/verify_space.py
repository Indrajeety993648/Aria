"""Smoke-test the live HF Space.

Hits /health, /schema, POST /reset (stateless), then opens the WS and runs
a single reset → step → state cycle. Prints a green "all checks pass" line
on success; exits non-zero on any failure.

Usage:
    python backend/training/verify_space.py
        [--url https://indra123-aria-personal-manager-v1.hf.space]
        [--wait-for-build]   # poll until status flips RUNNING
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request


DEFAULT_URL = "https://indra123-aria-personal-manager-v1.hf.space"
SPACE_ID = "indra123/aria-personal-manager-v1"


def _http_get(url: str, timeout: int = 30) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode()
        try:
            return r.status, json.loads(body)
        except json.JSONDecodeError:
            return r.status, body


def _http_post(url: str, body: dict, timeout: int = 30) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def _wait_for_build(max_minutes: int = 12) -> None:
    """Poll Hub API until Space runtime stage is RUNNING."""
    from huggingface_hub import space_info  # type: ignore[import-not-found]

    deadline = time.time() + max_minutes * 60
    last_stage = None
    while time.time() < deadline:
        info = space_info(SPACE_ID)
        stage = info.runtime.stage if info.runtime else "PENDING"
        if stage != last_stage:
            print(f"  [{int(time.time() - (deadline - max_minutes * 60))}s] stage: {stage}")
            last_stage = stage
        if stage == "RUNNING":
            return
        if stage in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            raise SystemExit(f"Space failed to build: {stage}")
        time.sleep(10)
    raise SystemExit(f"Space did not become RUNNING within {max_minutes} min")


async def _ws_cycle(base: str) -> dict:
    """Single reset → step → state cycle over WS, returns the state response."""
    import websockets  # type: ignore[import-not-found]

    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    async with websockets.connect(ws_url, max_size=2**22) as ws:
        await ws.send(json.dumps({
            "type": "reset",
            "data": {"seed": 42, "category": "calendar_conflict", "difficulty": "medium"},
        }))
        reset_resp = json.loads(await ws.recv())
        assert reset_resp.get("type") == "observation", reset_resp

        await ws.send(json.dumps({
            "type": "step",
            "data": {"action_id": 8, "target_id": "conflict_personal", "payload": {}, "metadata": {}},
        }))
        step_resp = json.loads(await ws.recv())
        assert step_resp.get("type") == "observation", step_resp

        await ws.send(json.dumps({"type": "state"}))
        state_resp = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "close"}))
        return state_resp


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--wait-for-build", action="store_true",
                   help="Poll Hub until status is RUNNING before testing.")
    p.add_argument("--max-build-minutes", type=int, default=12)
    args = p.parse_args()
    base = args.url.rstrip("/")

    if args.wait_for_build:
        print("Waiting for Space build to finish…")
        _wait_for_build(max_minutes=args.max_build_minutes)
        print("  build complete.\n")

    print(f"Verifying live Space: {base}")

    print("  1. GET /health …", end=" ", flush=True)
    code, body = _http_get(f"{base}/health")
    assert code == 200, f"status {code}: {body}"
    assert isinstance(body, dict) and body.get("status") in ("healthy", "ok"), body
    print("OK")

    print("  2. GET /schema …", end=" ", flush=True)
    code, body = _http_get(f"{base}/schema")
    assert code == 200
    assert isinstance(body, dict)
    for k in ("action", "observation", "state"):
        assert k in body, f"schema missing key: {k}"
    print("OK")

    print("  3. POST /reset …", end=" ", flush=True)
    code, body = _http_post(f"{base}/reset", {"seed": 42})
    assert code == 200
    assert "observation" in body and "calendar" in body["observation"]
    print(f"OK (calendar={len(body['observation']['calendar'])} events)")

    print("  4. WS reset → step → state …", end=" ", flush=True)
    state = asyncio.run(_ws_cycle(base))
    assert state.get("type") == "state"
    print("OK")

    print("\n✓ All checks pass. Space is live and OpenEnv-compliant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
