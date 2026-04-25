"""FastAPI surface for voice-service: /health, /stt, /tts, /ws/stt, /ws/tts.

The STT/TTS backends are lazy-loaded on first request and cached at module
level. `MOCK_VOICE` decides real vs mock at the moment of first access — so
toggling the env var between requests is allowed but rare.
"""
from __future__ import annotations

import base64
import io
import os
import wave
from typing import Any

from aria_contracts.voice import TTSRequest, VoiceChunk, VoiceTranscript
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from .mock import MockSTT, MockTTS, silent_wav_bytes
from .ws import router as ws_router

# Module-level singletons. `None` means "not yet instantiated".
_stt: Any | None = None
_tts: Any | None = None


def _is_mock() -> bool:
    """Default ON. Only `"0"` / `"false"` disables mock mode."""
    val = os.getenv("MOCK_VOICE", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


def get_stt() -> Any:
    """Return a cached STT backend; instantiate on first call."""
    global _stt
    if _stt is not None:
        return _stt
    if _is_mock():
        _stt = MockSTT()
    else:
        # Lazy import so the service can start without faster-whisper installed.
        from .stt import STT

        _stt = STT()
    return _stt


def _tts_backend_name() -> str:
    """Resolve the configured TTS backend.

    Priority:
      1. MOCK_VOICE=1 (default) → 'mock'
      2. TTS_BACKEND env var    → 'elevenlabs' | 'piper' | 'mock'
      3. fallback to 'piper'
    """
    if _is_mock():
        return "mock"
    return os.getenv("TTS_BACKEND", "piper").strip().lower()


def get_tts() -> Any:
    global _tts
    if _tts is not None:
        return _tts
    name = _tts_backend_name()
    if name == "elevenlabs":
        from .elevenlabs_tts import ElevenLabsTTS

        _tts = ElevenLabsTTS()
    elif name == "mock":
        _tts = MockTTS()
    else:  # piper / default
        from .tts import TTS

        _tts = TTS()
    return _tts


def reset_backends() -> None:
    """Test helper — force re-instantiation on next request (e.g. after MOCK_VOICE flip)."""
    global _stt, _tts
    _stt = None
    _tts = None


# ---------------------------------------------------------------------------- app


def build_app() -> FastAPI:
    app = FastAPI(title="ARIA voice-service", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "voice-service",
            "mock": _is_mock(),
            "tts_backend": _tts_backend_name(),
        }

    @app.post("/stt", response_model=VoiceTranscript)
    async def stt_endpoint(
        audio: UploadFile = File(..., description="WAV file (16 kHz mono preferred)"),
        session_id: str = Form("http-stt"),
        lang: str = Form("en"),
    ) -> VoiceTranscript:
        raw = await audio.read()
        if not raw:
            raise HTTPException(status_code=400, detail="empty audio upload")
        # If it's a WAV, extract PCM + sample rate. Otherwise assume raw 16 kHz PCM.
        try:
            with wave.open(io.BytesIO(raw), "rb") as w:
                sample_rate = w.getframerate()
                pcm = w.readframes(w.getnframes())
        except (wave.Error, EOFError):
            sample_rate = 16000
            pcm = raw

        backend = get_stt()
        return await backend.transcribe(
            pcm, sample_rate=sample_rate, lang=lang, session_id=session_id
        )

    @app.post("/tts")
    async def tts_endpoint(req: TTSRequest) -> Response:
        """Return an audio/wav body assembled from the streamed VoiceChunks."""
        backend = get_tts()
        stream = await backend.synth(req)
        chunks: list[VoiceChunk] = []
        async for c in stream:
            chunks.append(c)

        if not chunks:
            # Degenerate path — emit a known-good silent WAV so callers never choke.
            return Response(content=silent_wav_bytes(), media_type="audio/wav")

        sample_rate = chunks[0].sample_rate
        pcm = b"".join(base64.b64decode(c.audio_b64) for c in chunks)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm)
        return Response(content=buf.getvalue(), media_type="audio/wav")

    @app.post("/tts/stream")
    async def tts_stream_json(req: TTSRequest) -> JSONResponse:
        """Non-streaming JSON alternative: returns a list of VoiceChunk dicts."""
        backend = get_tts()
        stream = await backend.synth(req)
        out: list[dict[str, Any]] = []
        async for c in stream:
            out.append(c.model_dump())
        return JSONResponse(content={"chunks": out})

    app.include_router(ws_router)

    return app
