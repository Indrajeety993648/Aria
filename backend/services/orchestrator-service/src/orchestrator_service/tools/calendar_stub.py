"""Canned Calendar tool — returns fake event IDs. No real Calendar API traffic."""
from __future__ import annotations

import uuid
from typing import Any


async def create_event(
    title: str,
    start_iso: str | None = None,
    end_iso: str | None = None,
    attendees: list[str] | None = None,
) -> dict[str, Any]:
    """Pretend to create a calendar event."""
    return {
        "status": "created",
        "event_id": f"stub_evt_{uuid.uuid4().hex[:10]}",
        "title": title,
        "start_iso": start_iso,
        "end_iso": end_iso,
        "attendees": attendees or [],
    }


async def reschedule_event(
    event_id: str,
    new_start_iso: str | None = None,
    new_end_iso: str | None = None,
) -> dict[str, Any]:
    """Pretend to move an existing event."""
    return {
        "status": "rescheduled",
        "event_id": event_id,
        "new_start_iso": new_start_iso,
        "new_end_iso": new_end_iso,
    }


async def cancel_event(event_id: str) -> dict[str, Any]:
    """Pretend to cancel an event."""
    return {"status": "cancelled", "event_id": event_id}


__all__ = ["create_event", "reschedule_event", "cancel_event"]
