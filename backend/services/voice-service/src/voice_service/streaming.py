"""Helpers for sentence-level voice streaming."""
from __future__ import annotations

import re

_SEGMENT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def split_text_segments(text: str) -> list[str]:
    """Split text into short synthesis segments for early audio start."""

    segments = [segment.strip() for segment in _SEGMENT_RE.split(text) if segment.strip()]
    if segments:
        return segments
    stripped = text.strip()
    return [stripped] if stripped else []


__all__ = ["split_text_segments"]