"""Tiny energy-based Voice Activity Detection — no webrtc dep, offline-safe.

Operates on 16-bit signed little-endian PCM frames. The default threshold of
0.01 is RMS normalized to [0, 1] — adjust via `VAD_THRESHOLD` env.
"""
from __future__ import annotations

import math
import os
import struct
from dataclasses import dataclass

# 20 ms at 16 kHz mono, 16-bit = 640 bytes per frame.
FRAME_MS: int = 20
DEFAULT_SAMPLE_RATE: int = 16000


def frame_size_bytes(sample_rate: int = DEFAULT_SAMPLE_RATE, frame_ms: int = FRAME_MS) -> int:
    """Bytes per 16-bit mono frame at the given sample rate."""
    return int(sample_rate * frame_ms / 1000) * 2


def rms_int16(pcm: bytes) -> float:
    """Normalized RMS (0.0 – 1.0) of a 16-bit signed LE PCM buffer.

    Empty buffer → 0.0. Partial final sample is tolerated (rounded down).
    """
    n = len(pcm) // 2
    if n == 0:
        return 0.0
    # struct.unpack is faster than numpy for tiny 20 ms frames and avoids an import.
    samples = struct.unpack(f"<{n}h", pcm[: n * 2])
    sum_sq = 0.0
    for s in samples:
        sum_sq += float(s) * float(s)
    rms = math.sqrt(sum_sq / n)
    return min(1.0, rms / 32768.0)


@dataclass
class VADConfig:
    threshold: float = 0.01
    sample_rate: int = DEFAULT_SAMPLE_RATE
    frame_ms: int = FRAME_MS


class EnergyVAD:
    """Per-frame is_speech decision based on RMS > threshold.

    Stateless by design — the caller slices their buffer into frames.
    """

    def __init__(self, config: VADConfig | None = None) -> None:
        if config is None:
            config = VADConfig(threshold=float(os.getenv("VAD_THRESHOLD", "0.01")))
        self.config = config

    @property
    def frame_bytes(self) -> int:
        return frame_size_bytes(self.config.sample_rate, self.config.frame_ms)

    def is_speech(self, frame_pcm: bytes) -> bool:
        """True if the frame's normalized RMS exceeds the threshold."""
        return rms_int16(frame_pcm) > self.config.threshold

    def iter_frames(self, pcm: bytes) -> list[tuple[bytes, bool]]:
        """Split `pcm` into 20 ms frames and label each as speech / non-speech."""
        size = self.frame_bytes
        out: list[tuple[bytes, bool]] = []
        for i in range(0, len(pcm) - size + 1, size):
            frame = pcm[i : i + size]
            out.append((frame, self.is_speech(frame)))
        return out
