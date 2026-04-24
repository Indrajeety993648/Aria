"""Real-mode STT wrapper around faster-whisper.

faster-whisper is imported LAZILY inside `_ensure_model()`. The module must be
importable (and the service must start) even if faster-whisper is not installed,
as long as `MOCK_VOICE=1` at request time.
"""
from __future__ import annotations

import asyncio
import io
import os
import wave
from typing import Any

from aria_contracts.voice import VoiceTranscript


class STT:
    """faster-whisper wrapper. Construct cheaply; model loads on first `transcribe`."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name: str = model_name or os.getenv("WHISPER_MODEL", "tiny.en")
        self._model: Any | None = None

    # ------------------------------------------------------------------ internals

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        # Lazy import — keeps the service importable without faster-whisper.
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # pragma: no cover — real-mode only
            raise RuntimeError(
                "faster-whisper is not installed. Install the 'real' extra or set MOCK_VOICE=1."
            ) from exc

        if os.getenv("ARIA_DOWNLOAD_MODELS", "0") != "1":
            raise RuntimeError(
                "Refusing to download Whisper weights. Set ARIA_DOWNLOAD_MODELS=1 to enable."
            )

        self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        return self._model

    @staticmethod
    def _pcm_to_wav(audio_bytes: bytes, sample_rate: int) -> bytes:
        """Wrap raw 16-bit mono PCM into a WAV container that Whisper can decode."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(audio_bytes)
        return buf.getvalue()

    # ------------------------------------------------------------------ public

    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        lang: str = "en",
        session_id: str = "session",
    ) -> VoiceTranscript:
        """Transcribe an audio buffer. Runs the blocking decode on a worker thread."""

        def _run() -> VoiceTranscript:
            model = self._ensure_model()
            # faster-whisper accepts file-like objects of a WAV stream.
            wav_io = io.BytesIO(self._pcm_to_wav(audio_bytes, sample_rate))
            segments, info = model.transcribe(wav_io, language=lang, beam_size=1)
            segments = list(segments)
            text = " ".join(s.text.strip() for s in segments).strip()
            end_ms = int(1000 * max((s.end for s in segments), default=0.0))
            confidence = 1.0
            if segments and getattr(segments[-1], "avg_logprob", None) is not None:
                # Rough logprob → probability clamp.
                import math

                confidence = max(0.0, min(1.0, math.exp(segments[-1].avg_logprob)))
            return VoiceTranscript(
                session_id=session_id,
                text=text,
                is_final=True,
                confidence=confidence,
                start_ms=0,
                end_ms=end_ms,
                lang=getattr(info, "language", lang) or lang,
            )

        return await asyncio.to_thread(_run)
