"""ElevenLabs TTS backend.

Same public shape as `voice_service.tts.TTS`: exposes an async `synth(req)`
that returns an async iterator of `VoiceChunk`. Streams audio as the API
returns it so first-byte latency stays low.

Lazy-imported so the service starts even when the `elevenlabs` package is
absent. Activated by:

    TTS_BACKEND=elevenlabs
    ELEVENLABS_API_KEY=sk_...
    # optional:
    ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM   # Rachel (default)
    ELEVENLABS_MODEL=eleven_turbo_v2_5         # low-latency default

We ship a pure-httpx implementation so the `elevenlabs` Python SDK is NOT a
required dep — we only need an API key. Swap to the SDK if you need SDK-only
features (voice design, projects, etc).
"""
from __future__ import annotations

import asyncio
import base64
import io
import os
import wave
from typing import Any, AsyncIterator

from aria_contracts.voice import TTSRequest, VoiceChunk


_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"   # "Rachel"
_DEFAULT_MODEL = "eleven_turbo_v2_5"         # lowest-latency public model
_ELEVENLABS_BASE = "https://api.elevenlabs.io"
_CHUNK_MS = 20
_SAMPLE_RATE = 16000  # pcm_16000 output format


class ElevenLabsTTS:
    """Streaming ElevenLabs TTS backend.

    Config via env vars (see module docstring). Requests a PCM-16kHz stream
    directly so we can chop into 20 ms `VoiceChunk`s without resampling.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str | None = None,
    ) -> None:
        self.api_key: str = api_key or os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id: str = voice_id or os.getenv("ELEVENLABS_VOICE_ID", _DEFAULT_VOICE_ID)
        self.model_id: str = model_id or os.getenv("ELEVENLABS_MODEL", _DEFAULT_MODEL)
        if not self.api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not set. Set it or switch TTS_BACKEND back to piper/mock."
            )

    # ------------------------------------------------------------------ public

    async def synth(self, req: TTSRequest) -> AsyncIterator[VoiceChunk]:
        """Stream PCM 16 kHz audio from ElevenLabs, re-chunked to 20 ms slices."""
        # Lazy import so the module is importable without httpx (we require it
        # transitively via FastAPI, but we don't want a hard failure at import).
        import httpx

        url = (
            f"{_ELEVENLABS_BASE}/v1/text-to-speech/{self.voice_id}/stream"
            "?output_format=pcm_16000"
        )
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/pcm",
            "content-type": "application/json",
        }
        body = {
            "text": req.text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
            "optimize_streaming_latency": 3,
        }

        chunk_bytes = int(_SAMPLE_RATE * (_CHUNK_MS / 1000.0)) * 2  # 16-bit mono

        async def _gen() -> AsyncIterator[VoiceChunk]:
            seq = 0
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code != 200:
                        detail = (await resp.aread())[:400]
                        raise RuntimeError(
                            f"ElevenLabs stream error {resp.status_code}: {detail!r}"
                        )
                    buf = bytearray()
                    async for piece in resp.aiter_bytes():
                        buf.extend(piece)
                        while len(buf) >= chunk_bytes:
                            pcm = bytes(buf[:chunk_bytes])
                            del buf[:chunk_bytes]
                            yield VoiceChunk(
                                session_id=req.session_id,
                                seq=seq,
                                audio_b64=base64.b64encode(pcm).decode("ascii"),
                                sample_rate=_SAMPLE_RATE,
                                is_last=False,
                            )
                            seq += 1
                    # Flush any tail (pad to full chunk with silence so downstream
                    # decoders don't underrun on the last frame).
                    if buf:
                        tail = bytes(buf) + b"\x00" * max(0, chunk_bytes - len(buf))
                        yield VoiceChunk(
                            session_id=req.session_id,
                            seq=seq,
                            audio_b64=base64.b64encode(tail).decode("ascii"),
                            sample_rate=_SAMPLE_RATE,
                            is_last=True,
                        )
                    else:
                        # Emit a final is_last marker so consumers can close cleanly.
                        yield VoiceChunk(
                            session_id=req.session_id,
                            seq=seq,
                            audio_b64=base64.b64encode(b"\x00" * chunk_bytes).decode("ascii"),
                            sample_rate=_SAMPLE_RATE,
                            is_last=True,
                        )

        return _gen()
