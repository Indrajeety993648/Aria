"""Mock STT/TTS backends — canned outputs, zero deps beyond stdlib + aria-contracts.

These classes satisfy the same `transcribe` / `synth` interfaces as the real
backends in `stt.py` / `tts.py`, so the API layer does not care which it holds.
"""
from __future__ import annotations

import base64
import io
import itertools
import wave
from typing import AsyncIterator

from aria_contracts.voice import TTSRequest, VoiceChunk, VoiceTranscript

from .streaming import split_text_segments

# Realistic canned utterances — cycled deterministically.
_CANNED_PHRASES: tuple[str, ...] = (
    "hey ARIA what's on my calendar",
    "reply to Priya that I'll be late",
    "remind me to call mom tonight",
    "draft an email to the team about the deploy",
    "block focus time tomorrow afternoon",
)

# 16 kHz, mono, 16-bit PCM — matches the default VoiceChunk.sample_rate.
MOCK_SAMPLE_RATE: int = 16000
MOCK_FRAME_MS: int = 100  # one 100 ms silent chunk per synth


def silent_wav_bytes(duration_ms: int = MOCK_FRAME_MS, sample_rate: int = MOCK_SAMPLE_RATE) -> bytes:
    """Return a valid WAV file (header + data) of silence, 16-bit mono PCM.

    Uses only stdlib `wave` — no numpy needed.
    """
    n_frames = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        # Each frame = 2 bytes of zeroes.
        w.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def silent_pcm_bytes(duration_ms: int = MOCK_FRAME_MS, sample_rate: int = MOCK_SAMPLE_RATE) -> bytes:
    """Raw 16-bit PCM silence (no WAV header) — used for VoiceChunk payloads."""
    n_frames = int(sample_rate * duration_ms / 1000)
    return b"\x00\x00" * n_frames


class MockSTT:
    """Canned transcript generator — cycles through realistic phrases deterministically."""

    def __init__(self) -> None:
        self._cycle = itertools.cycle(_CANNED_PHRASES)

    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        lang: str = "en",
        session_id: str = "mock-session",
    ) -> VoiceTranscript:
        text = next(self._cycle)
        # Estimate end_ms from bytes (16-bit PCM). Cheap, but realistic-enough.
        n_samples = max(1, len(audio_bytes) // 2)
        end_ms = int(1000 * n_samples / sample_rate)
        return VoiceTranscript(
            session_id=session_id,
            text=text,
            is_final=True,
            confidence=0.95,
            start_ms=0,
            end_ms=end_ms,
            lang=lang,
        )


class MockTTS:
    """Emit silent 100 ms PCM chunks per text segment."""

    async def synth(self, req: TTSRequest) -> AsyncIterator[VoiceChunk]:
        async def _gen() -> AsyncIterator[VoiceChunk]:
            segments = split_text_segments(req.text)
            if not segments:
                segments = [""]
            for seq, _segment in enumerate(segments):
                pcm = silent_pcm_bytes()
                yield VoiceChunk(
                    session_id=req.session_id,
                    seq=seq,
                    audio_b64=base64.b64encode(pcm).decode("ascii"),
                    sample_rate=MOCK_SAMPLE_RATE,
                    is_last=seq == len(segments) - 1,
                )

        return _gen()
