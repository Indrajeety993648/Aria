"""Gateway (public WS + REST) contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GwEventKind = Literal[
    "session_start",
    "partial_transcript",
    "final_transcript",
    "tool_call",
    "reply_text",
    "tts_chunk",
    "env_step",
    "reward",
    "error",
]


class GwSessionStart(BaseModel):
    """Start a session over WS (first message the client sends)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    mode: Literal["live", "simulated"] = "simulated"


class GwAgentEvent(BaseModel):
    """One event emitted by the gateway to the frontend.

    This is the *only* server→client message shape. Clients discriminate on
    `kind` and read `payload` accordingly.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    kind: GwEventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    ts_ms: int = Field(ge=0)
