"""AgentLoop writes a per-turn episodic trace via MemoryClient.

The write is best-effort: if memory-service is down the turn must still
succeed. Both success and failure paths are exercised here.
"""
from __future__ import annotations

from typing import Any

from aria_contracts import AgentTurnRequest
from aria_contracts.memory import MemoryWrite
from orchestrator_service.agent import AgentLoop
from orchestrator_service.tools.memory_client import MemoryClient

from .test_agent import FakeEnvClient


class RecordingMemoryClient(MemoryClient):
    def __init__(self) -> None:
        self.writes: list[MemoryWrite] = []

    async def write(self, payload: MemoryWrite) -> bool:  # type: ignore[override]
        self.writes.append(payload)
        return True


class ExplodingMemoryClient(MemoryClient):
    def __init__(self) -> None:
        self.attempts = 0

    async def write(self, payload: MemoryWrite) -> bool:  # type: ignore[override]
        self.attempts += 1
        # Simulate a flaky write — real MemoryClient.write already swallows
        # exceptions, so the production contract is "never raises." We assert
        # the agent loop respects that by tolerating False returns too.
        return False


async def test_turn_emits_episodic_memory_write() -> None:
    env = FakeEnvClient()
    mem = RecordingMemoryClient()
    loop = AgentLoop(env_client=env, memory_client=mem)
    req = AgentTurnRequest(
        session_id="s-mem", user_text="reschedule my 3pm", mode="simulated"
    )
    resp = await loop.turn(req)
    assert resp.session_id == "s-mem"
    assert len(mem.writes) == 1
    write = mem.writes[0]
    assert write.namespace == "episodic"
    assert write.content == "reschedule my 3pm"
    assert write.metadata["session_id"] == "s-mem"
    assert write.metadata["action_id"] == int(resp.mapped_env_action.action_id)  # type: ignore[union-attr]


async def test_turn_succeeds_when_memory_write_fails() -> None:
    env = FakeEnvClient()
    mem = ExplodingMemoryClient()
    loop = AgentLoop(env_client=env, memory_client=mem)
    req = AgentTurnRequest(session_id="s-fail", user_text="schedule coffee")
    resp = await loop.turn(req)
    assert resp.session_id == "s-fail"
    assert mem.attempts == 1


def test_memory_client_default_url_is_env_overridable(monkeypatch: Any) -> None:
    from orchestrator_service.tools import memory_client as mc

    monkeypatch.setenv("MEMORY_SERVICE_URL", "http://elsewhere:9999")
    c = mc.MemoryClient()
    assert c.base_url == "http://elsewhere:9999"
