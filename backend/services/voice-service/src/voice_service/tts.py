"""Real-mode TTS wrapper around piper-tts.

piper-tts is imported LAZILY. The module must be importable (and the service
must start) even if piper is not installed, as long as `MOCK_VOICE=1` at
request time.
"""
from __future__ import annotations

import asyncio
import base64
import io
import os
import wave
from typing import Any, AsyncIterator

from aria_contracts.voice import TTSRequest, VoiceChunk


class TTS:
    """piper-tts wrapper. Voice loads lazily on first `synth`."""

    def __init__(self, voice: str | None = None, voice_path: str | None = None) -> None:
        self.voice: str = voice or os.getenv("PIPER_VOICE", "en_US-amy-medium")
        self.voice_path: str | None = voice_path or os.getenv("PIPER_VOICE_PATH")
        self._piper: Any | None = None

    # ------------------------------------------------------------------ internals

    def _ensure_voice(self) -> Any:
        if self._piper is not None:
            return self._piper
        try:
            from piper import PiperVoice  # type: ignore
        except Exception as exc:  # pragma: no cover — real-mode only
            raise RuntimeError(
                "piper-tts is not installed. Install the 'real' extra or set MOCK_VOICE=1."
            ) from exc
        if self.voice_path is None:
            raise RuntimeError(
                "PIPER_VOICE_PATH is not set — real TTS needs a local .onnx voice file."
            )
        if not os.path.exists(self.voice_path):
            raise RuntimeError(f"Piper voice file not found: {self.voice_path}")
        self._piper = PiperVoice.load(self.voice_path)
        return self._piper

    # ------------------------------------------------------------------ public

    async def synth(self, req: TTSRequest) -> AsyncIterator[VoiceChunk]:
        """Stream PCM chunks from piper. Each VoiceChunk is a 20 ms slice."""
        piper = await asyncio.to_thread(self._ensure_voice)
        sample_rate = getattr(getattr(piper, "config", None), "sample_rate", 16000) or 16000
        # 20 ms @ sample_rate, 16-bit mono
        chunk_bytes = int(sample_rate * 0.02) * 2

        def _render() -> bytes:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                piper.synthesize(req.text, w)
            buf.seek(0)
            with wave.open(buf, "rb") as r:
                return r.readframes(r.getnframes())

        pcm = await asyncio.to_thread(_render)

        async def _gen() -> AsyncIterator[VoiceChunk]:
            total = len(pcm)
            seq = 0
            for i in range(0, total, chunk_bytes):
                piece = pcm[i : i + chunk_bytes]
                is_last = (i + chunk_bytes) >= total
                yield VoiceChunk(
                    session_id=req.session_id,
                    seq=seq,
                    audio_b64=base64.b64encode(piece).decode("ascii"),
                    sample_rate=sample_rate,
                    is_last=is_last,
                )
                seq += 1

        return _gen()
