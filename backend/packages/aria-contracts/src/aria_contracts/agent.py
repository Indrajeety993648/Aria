"""Orchestrator (agent loop) contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aria_contracts.env import AriaAction


class ToolCall(BaseModel):
    """A tool the orchestrator decided to invoke this turn.

    Real mode: the tool hits a real external service.
    Mock mode: the tool returns canned data.
    """

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None  # populated after execution


class AgentTurnRequest(BaseModel):
    """One user turn — text in, reasoning + action out."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    user_text: str
    mode: Literal["live", "simulated"] = "simulated"


class AgentTurnResponse(BaseModel):
    """Orchestrator's reply for one turn."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    reply_text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    mapped_env_action: AriaAction | None = Field(
        default=None,
        description="Populated when mode=='simulated'; the action the orchestrator "
        "would pass to the ARIA env on the user's behalf.",
    )
    latency_ms: dict[str, int] = Field(
        default_factory=dict, description="Per-stage latency (stt, llm, tts, ...)"
    )
