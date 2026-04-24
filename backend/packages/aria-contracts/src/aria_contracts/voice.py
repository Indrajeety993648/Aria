"""Voice pipeline contracts. Voice service speaks these to the gateway."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VoiceTranscript(BaseModel):
    """One transcript emission — may be partial or final."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    text: str
    is_final: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    start_ms: int = Field(ge=0, default=0)
    end_ms: int = Field(ge=0, default=0)
    lang: str = "en"


class TTSRequest(BaseModel):
    """Ask the voice service to synthesize speech for this text."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    text: str
    voice: str = Field(default="en_US-amy-medium", description="Piper voice ID")
    stream: bool = True


class VoiceChunk(BaseModel):
    """One PCM/audio chunk streamed from TTS (base64-encoded for JSON transport)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    seq: int = Field(ge=0)
    audio_b64: str
    sample_rate: int = 16000
    is_last: bool = False
