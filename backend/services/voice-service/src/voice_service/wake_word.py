"""Wake-word detection.

Demo-grade, dependency-free. Two cascaded checks:

  1. Energy gate — a short RMS envelope must pass a threshold so we don't
     wake on silence or room tone.
  2. Phrase match — once a transcript is available (partial or final),
     the substring "aria" (case-insensitive, word-boundary loose) triggers wake.

In production you'd swap the phrase match for a real on-device KWS model
(Porcupine, OpenWakeWord, etc). This module is designed so that swap is
trivial: replace `PhraseMatcher` with your detector behind the `WakeWordDetector`
interface.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Sequence


# -----------------------------------------------------------------------------
# Energy gate
# -----------------------------------------------------------------------------


def _rms_int16(pcm: bytes) -> float:
    """RMS of int16 little-endian PCM, normalized to 0..1."""
    n = len(pcm) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", pcm[: n * 2])
    # int16 range is -32768..32767; normalize by 32768.
    acc = 0
    for s in samples:
        acc += s * s
    return (acc / n) ** 0.5 / 32768.0


@dataclass
class EnergyGate:
    """Gate that only passes if windowed RMS exceeds a threshold."""

    threshold: float = 0.015  # ~ -36 dBFS; tuned empirically for clean-room mics
    window_frames: int = 3    # ~60ms at 20ms frames

    def __post_init__(self) -> None:
        self._history: list[float] = []

    def accept(self, pcm_frame: bytes) -> bool:
        rms = _rms_int16(pcm_frame)
        self._history.append(rms)
        if len(self._history) > self.window_frames:
            self._history.pop(0)
        avg = sum(self._history) / max(1, len(self._history))
        return avg >= self.threshold


# -----------------------------------------------------------------------------
# Phrase matcher
# -----------------------------------------------------------------------------


_WAKE_WORDS = ("aria", "hey aria", "ok aria")


class PhraseMatcher:
    """Case-insensitive substring match with word-boundary preference."""

    def __init__(self, phrases: Sequence[str] = _WAKE_WORDS) -> None:
        self._patterns = [
            re.compile(rf"\b{re.escape(p)}\b", re.IGNORECASE) for p in phrases
        ]

    def contains_wake(self, text: str) -> bool:
        if not text:
            return False
        return any(p.search(text) for p in self._patterns)


# -----------------------------------------------------------------------------
# Composed detector
# -----------------------------------------------------------------------------


class WakeWordDetector:
    """Compose energy gate + phrase matcher.

    Typical flow from the voice service:
        det = WakeWordDetector()
        on audio frame: if det.pass_audio(frame): start_streaming_to_stt()
        on partial transcript: if det.pass_transcript(partial): raise wake()
    """

    def __init__(
        self,
        gate: EnergyGate | None = None,
        matcher: PhraseMatcher | None = None,
    ) -> None:
        self._gate = gate or EnergyGate()
        self._matcher = matcher or PhraseMatcher()
        self._armed = False

    # True if the energy gate opened on this frame (stream STT now).
    def pass_audio(self, pcm_frame: bytes) -> bool:
        ok = self._gate.accept(pcm_frame)
        self._armed = self._armed or ok
        return ok

    # True if the transcript so far contains a wake phrase.
    def pass_transcript(self, text: str) -> bool:
        if not self._armed:
            return False
        return self._matcher.contains_wake(text)

    def reset(self) -> None:
        self._armed = False


__all__ = ["EnergyGate", "PhraseMatcher", "WakeWordDetector"]
