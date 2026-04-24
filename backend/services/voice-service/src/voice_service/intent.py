"""Lightweight streaming intent hints for voice transcripts.

The voice service does not own the full orchestrator policy stack. This helper
provides a low-latency intent hint so partial STT results can be routed earlier
without waiting for the full backend decision engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from aria_contracts import ActionId


@dataclass(slots=True)
class IntentHint:
    """Small structured summary of the best-effort intent guess."""

    intent_id: int
    confidence: float
    source: str = "heuristic"


_KEYWORDS: dict[ActionId, tuple[str, ...]] = {
    ActionId.SEND_MSG: ("send", "message", "text", "email", "notify"),
    ActionId.SCHEDULE: ("schedule", "book", "set up", "add to calendar"),
    ActionId.RESCHEDULE: ("reschedule", "move", "push back", "change the time"),
    ActionId.CANCEL: ("cancel", "call off", "drop the meeting"),
    ActionId.DELEGATE: ("delegate", "assign", "hand off"),
    ActionId.DRAFT_REPLY: ("reply", "draft reply", "respond", "write back"),
    ActionId.SET_REMINDER: ("remind", "set a reminder"),
    ActionId.PURCHASE: ("buy", "purchase", "order"),
    ActionId.RESOLVE_CONFLICT: ("conflict", "double booked", "overlapping"),
    ActionId.ASK_USER: ("ask me", "check with me", "clarify"),
    ActionId.DECLINE_INVITE: ("decline", "reject", "turn down"),
    ActionId.PROPOSE_ALTERNATIVE: ("propose", "suggest another", "offer another time"),
    ActionId.BATCH_ACTION: ("batch", "clear my inbox", "handle all"),
    ActionId.WAIT: ("wait", "hold off", "do nothing"),
    ActionId.ESCALATE: ("escalate", "raise", "loop in"),
}


def classify_partial_intent(text: str) -> IntentHint:
    """Return a cheap keyword-based intent hint for a partial transcript."""

    norm = " ".join(text.lower().split())
    if not norm:
        return IntentHint(intent_id=int(ActionId.WAIT), confidence=0.0)

    if "reply" in norm or "draft reply" in norm or "respond" in norm:
        return IntentHint(intent_id=int(ActionId.DRAFT_REPLY), confidence=0.8)
    if "reschedule" in norm:
        return IntentHint(intent_id=int(ActionId.RESCHEDULE), confidence=0.8)

    best_action = ActionId.WAIT
    best_score = 0
    for action, patterns in _KEYWORDS.items():
        score = sum(1 for pattern in patterns if pattern in norm)
        if score > best_score:
            best_action = action
            best_score = score

    confidence = 0.5 if best_score > 0 else 0.2
    return IntentHint(intent_id=int(best_action), confidence=confidence)


__all__ = ["IntentHint", "classify_partial_intent"]