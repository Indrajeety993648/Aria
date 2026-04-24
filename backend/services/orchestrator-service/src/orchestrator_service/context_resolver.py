"""Context resolver that combines observation and text into actionable hints."""
from __future__ import annotations

from typing import Any


class ContextResolver:
    """Builds a lightweight context object for decisioning.

    This does not call external services. It only uses the latest observation
    and the user text.
    """

    def resolve(self, user_text: str, observation: dict[str, Any] | None) -> dict[str, Any]:
        if observation is None:
            return {}

        text = user_text.lower()
        ctx: dict[str, Any] = {
            "top_inbox_id": _top_inbox_id(observation),
            "conflict_event_id": _conflict_event_id(observation),
            "high_priority_task_id": _high_priority_task_id(observation),
        }

        if "email" in text or "reply" in text:
            ctx["suggested_target_id"] = ctx.get("top_inbox_id")
        if "conflict" in text or "overlap" in text or "double booked" in text:
            ctx["suggested_target_id"] = ctx.get("conflict_event_id")
        if "delegate" in text or "assign" in text:
            ctx["suggested_target_id"] = ctx.get("high_priority_task_id")

        return {k: v for k, v in ctx.items() if v}


def _top_inbox_id(observation: dict[str, Any]) -> str | None:
    inbox = observation.get("inbox") or []
    if not inbox:
        return None
    return inbox[0].get("email_id")


def _conflict_event_id(observation: dict[str, Any]) -> str | None:
    calendar = observation.get("calendar") or []
    day0 = [e for e in calendar if e.get("day_offset", 0) == 0]
    for i, a in enumerate(day0):
        a_start = float(a.get("start_hour", 0.0))
        a_end = float(a.get("end_hour", 0.0))
        for b in day0[i + 1 :]:
            b_start = float(b.get("start_hour", 0.0))
            b_end = float(b.get("end_hour", 0.0))
            if a_start < b_end and b_start < a_end:
                return a.get("event_id") or b.get("event_id")
    return None


def _high_priority_task_id(observation: dict[str, Any]) -> str | None:
    tasks = observation.get("pending_tasks") or []
    tasks = sorted(tasks, key=lambda t: t.get("priority", 0.0), reverse=True)
    return tasks[0].get("task_id") if tasks else None


__all__ = ["ContextResolver"]
