"""Lightweight entity extractor for ARIA user text."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any


_ID_RE = re.compile(r"\b((?:event|email|contact|task|msg|msg_id)_[a-z0-9_-]+)\b")
_TIME_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)


class EntityExtractor:
    """Extracts basic entities from text (ids, time hints, participants)."""

    def extract(self, text: str) -> dict[str, Any]:
        entities: dict[str, Any] = {}
        norm = text.lower()

        target_id = self._extract_target_id(norm)
        if target_id:
            entities["target_id"] = target_id

        time_hint = self._extract_time(norm)
        if time_hint:
            entities.update(time_hint)

        participants = self._extract_participants(text)
        if participants:
            entities["participants"] = participants

        return entities

    def _extract_target_id(self, text: str) -> str | None:
        m = _ID_RE.search(text)
        return m.group(1) if m else None

    def _extract_time(self, text: str) -> dict[str, Any] | None:
        # Simple relative keywords
        now = datetime.utcnow()
        if "tomorrow" in text:
            return {"date_hint": (now + timedelta(days=1)).date().isoformat()}
        if "today" in text:
            return {"date_hint": now.date().isoformat()}
        if "next week" in text:
            return {"date_hint": (now + timedelta(days=7)).date().isoformat()}

        # Simple time-of-day pattern
        m = _TIME_RE.search(text)
        if not m:
            return None
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        meridian = (m.group(3) or "").lower()
        if meridian == "pm" and hour < 12:
            hour += 12
        if meridian == "am" and hour == 12:
            hour = 0
        return {"time_hint": f"{hour:02d}:{minute:02d}"}

    def _extract_participants(self, text: str) -> list[str]:
        # Naive: capture words after "with" or "to"
        participants: list[str] = []
        for match in re.finditer(r"\b(?:with|to)\s+([A-Z][a-zA-Z]+)", text):
            participants.append(match.group(1))
        return participants


__all__ = ["EntityExtractor"]
