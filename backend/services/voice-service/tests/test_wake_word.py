"""Wake-word detector tests. Deterministic, no audio models needed."""
from __future__ import annotations

import struct

from voice_service.wake_word import (
    EnergyGate,
    PhraseMatcher,
    WakeWordDetector,
)


def _pcm_silence(n_samples: int = 320) -> bytes:
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def _pcm_loud(n_samples: int = 320, amp: int = 8000) -> bytes:
    # triangular-ish signal so RMS is meaningful
    vals = [(i % 32 - 16) * (amp // 16) for i in range(n_samples)]
    return struct.pack(f"<{n_samples}h", *vals)


# -----------------------------------------------------------------------------
# EnergyGate
# -----------------------------------------------------------------------------


def test_energy_gate_rejects_silence():
    g = EnergyGate(threshold=0.01, window_frames=2)
    for _ in range(3):
        assert g.accept(_pcm_silence()) is False


def test_energy_gate_accepts_loud():
    g = EnergyGate(threshold=0.01, window_frames=2)
    # First frame alone may be above or below; two loud frames must pass.
    g.accept(_pcm_loud())
    assert g.accept(_pcm_loud()) is True


def test_energy_gate_smoothing_needs_sustained_signal():
    g = EnergyGate(threshold=0.05, window_frames=4)
    # Single loud burst sandwiched in silence must NOT pass if window dominates
    g.accept(_pcm_silence())
    g.accept(_pcm_silence())
    g.accept(_pcm_silence())
    passed = g.accept(_pcm_loud(amp=4000))
    assert passed is False


# -----------------------------------------------------------------------------
# PhraseMatcher
# -----------------------------------------------------------------------------


def test_phrase_matcher_positives():
    m = PhraseMatcher()
    assert m.contains_wake("hey aria what's on my calendar")
    assert m.contains_wake("ARIA")
    assert m.contains_wake("ok aria, reschedule the 5pm")


def test_phrase_matcher_negatives():
    m = PhraseMatcher()
    assert m.contains_wake("") is False
    assert m.contains_wake("arial font renders nicely") is False  # word boundary
    assert m.contains_wake("tell marianne to wait") is False


# -----------------------------------------------------------------------------
# Composed detector
# -----------------------------------------------------------------------------


def test_detector_blocks_transcript_without_prior_audio_arm():
    det = WakeWordDetector()
    # No audio passed yet → even a perfect phrase must not wake.
    assert det.pass_transcript("hey aria") is False


def test_detector_wakes_after_audio_and_phrase():
    det = WakeWordDetector()
    det.pass_audio(_pcm_loud())
    det.pass_audio(_pcm_loud())
    assert det.pass_transcript("hey aria, clear my afternoon") is True


def test_detector_reset_disarms():
    det = WakeWordDetector()
    det.pass_audio(_pcm_loud())
    det.pass_audio(_pcm_loud())
    det.reset()
    assert det.pass_transcript("hey aria") is False
