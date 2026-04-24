"""Canned Gmail tool — never makes network calls.

In live mode the orchestrator pretends to send mail. Real SMTP is explicitly
out of scope for the hackathon build.
"""
from __future__ import annotations

import uuid
from typing import Any


async def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
    """Pretend to send an email. Returns a canned queued-ack payload."""
    return {
        "status": "queued",
        "message_id": f"stub_{uuid.uuid4().hex[:12]}",
        "to": to,
        "subject": subject,
        "body_preview": (body[:80] + "...") if len(body) > 80 else body,
    }


__all__ = ["send_email"]
