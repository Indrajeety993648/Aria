"""State encoder for policy inference."""
from __future__ import annotations

from typing import Any


class StateEncoder:
    """Encode an observation dict into a fixed-size feature vector."""

    def encode(self, observation: dict[str, Any] | None) -> list[float]:
        if not observation:
            return [0.0] * 8

        inbox = observation.get("inbox") or []
        urgent = sum(1 for m in inbox if m.get("urgency", 0.0) >= 0.8)
        calendar = observation.get("calendar") or []
        conflicts = _count_conflicts(calendar)

        tasks = observation.get("pending_tasks") or []
        open_tasks = sum(1 for t in tasks if t.get("status") == "open")
        high_prio = sum(1 for t in tasks if t.get("priority", 0.0) >= 0.7)

        time = float(observation.get("time", 0.0))
        step = float(observation.get("step_count", 0))

        return [
            float(len(inbox)),
            float(urgent),
            float(len(calendar)),
            float(conflicts),
            float(open_tasks),
            float(high_prio),
            time,
            step,
        ]


def _count_conflicts(calendar: list[dict[str, Any]]) -> int:
    day0 = [e for e in calendar if e.get("day_offset", 0) == 0]
    conflicts = 0
    for i, a in enumerate(day0):
        a_start = float(a.get("start_hour", 0.0))
        a_end = float(a.get("end_hour", 0.0))
        for b in day0[i + 1 :]:
            b_start = float(b.get("start_hour", 0.0))
            b_end = float(b.get("end_hour", 0.0))
            if a_start < b_end and b_start < a_end:
                conflicts += 1
    return conflicts


__all__ = ["StateEncoder"]
