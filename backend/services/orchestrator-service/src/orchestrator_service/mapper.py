"""Deterministic rule-based intent parser: user text -> AriaAction.

This module must stay pure-function and dependency-light. It is the default
intent router when `MOCK_LLM=1` (the only mode shipped).

Design:
- Keyword bag per action, with priority weights when a phrase triggers multiple.
- A small precedence table breaks ties so, e.g., "reschedule" beats "schedule".
- Fallback is ActionId.WAIT for unrecognized text.
"""
from __future__ import annotations

import re
from typing import Iterable

from aria_contracts import ActionId, AriaAction


# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------
#
# Each entry maps an ActionId to a list of (pattern, weight) tuples. Patterns
# are simple substrings matched case-insensitively against the normalized
# user text. Higher weight = stronger match. Multi-word phrases are matched
# as whole substrings (spaces preserved) so "reply to" doesn't accidentally
# trigger "ply".
_KEYWORDS: dict[ActionId, list[tuple[str, int]]] = {
    # --- messaging / mail ---
    ActionId.SEND_MSG: [
        ("send message", 6),
        ("send a message", 6),
        ("send msg", 6),
        ("text ", 4),
        ("ping ", 4),
        ("message ", 3),
        ("email ", 3),
        ("send email", 5),
        ("send an email", 5),
        ("notify ", 3),
    ],
    ActionId.DRAFT_REPLY: [
        ("reply to", 8),
        ("draft reply", 8),
        ("draft a reply", 8),
        ("respond to", 7),
        ("write back to", 7),
        ("answer ", 3),
        ("reply ", 4),
    ],
    # --- calendar ---
    ActionId.SCHEDULE: [
        ("schedule ", 6),
        ("book ", 5),
        ("set up a meeting", 7),
        ("put on my calendar", 7),
        ("add to calendar", 7),
        ("create event", 6),
        ("create an event", 6),
        ("plan a ", 4),
    ],
    ActionId.RESCHEDULE: [
        ("reschedule", 9),
        ("move ", 4),
        ("push back", 6),
        ("push to", 5),
        ("shift ", 4),
        ("change the time", 6),
        ("move the meeting", 7),
    ],
    ActionId.CANCEL: [
        ("cancel", 9),
        ("drop the meeting", 7),
        ("call off", 6),
        ("skip the meeting", 6),
    ],
    ActionId.DECLINE_INVITE: [
        ("decline", 8),
        ("reject the invite", 8),
        ("turn down", 6),
        ("say no to the invite", 7),
        ("regret", 4),
        ("decline invite", 9),
    ],
    ActionId.PROPOSE_ALTERNATIVE: [
        ("propose alternative", 9),
        ("suggest another time", 8),
        ("propose another", 7),
        ("offer another time", 7),
        ("how about", 4),
        ("counter-propose", 8),
        ("counter propose", 8),
        ("propose a different", 7),
    ],
    # --- people / delegation ---
    ActionId.DELEGATE: [
        ("delegate to", 9),
        ("delegate ", 7),
        ("assign to", 7),
        ("hand off to", 7),
        ("have ", 2),
        ("ask ", 2),  # weak; beaten by "ask me"
        ("get someone else", 6),
    ],
    ActionId.ESCALATE: [
        ("escalate", 9),
        ("loop in my boss", 8),
        ("flag this to", 7),
        ("bump this up", 7),
        ("raise with", 6),
    ],
    # --- user interaction ---
    ActionId.ASK_USER: [
        ("ask me", 9),
        ("check with me", 8),
        ("confirm with me", 8),
        ("what do you want", 7),
        ("what should i", 6),
        ("clarify", 5),
        ("i'm not sure", 4),
        ("not sure", 3),
    ],
    # --- tasks / reminders ---
    ActionId.SET_REMINDER: [
        ("remind me", 9),
        ("set a reminder", 9),
        ("set reminder", 9),
        ("remind ", 5),
        ("don't let me forget", 8),
        ("nudge me", 6),
    ],
    ActionId.PURCHASE: [
        ("buy ", 8),
        ("purchase", 9),
        ("order ", 6),
        ("get me ", 4),
        ("pick up ", 4),
    ],
    # --- conflict & batching ---
    ActionId.RESOLVE_CONFLICT: [
        ("resolve conflict", 9),
        ("fix the conflict", 8),
        ("double booked", 7),
        ("double-booked", 7),
        ("overlapping", 6),
        ("clash", 5),
    ],
    ActionId.BATCH_ACTION: [
        ("batch ", 7),
        ("do all", 6),
        ("handle all", 6),
        ("take care of everything", 7),
        ("clear my inbox", 7),
        ("triage ", 6),
    ],
    ActionId.WAIT: [
        ("wait", 6),
        ("do nothing", 7),
        ("hold on", 6),
        ("hold off", 6),
        ("not yet", 5),
        ("later", 3),
    ],
}

# Precedence: if two actions tie in score, higher-priority wins.
# Intuitive tie-breakers: more specific intents beat generic ones.
_PRIORITY: dict[ActionId, int] = {
    ActionId.ASK_USER: 100,
    ActionId.RESCHEDULE: 95,       # "reschedule the meeting" must not fall to SCHEDULE
    ActionId.RESOLVE_CONFLICT: 92,
    ActionId.DRAFT_REPLY: 90,
    ActionId.DECLINE_INVITE: 88,
    ActionId.PROPOSE_ALTERNATIVE: 86,
    ActionId.ESCALATE: 84,
    ActionId.DELEGATE: 82,
    ActionId.CANCEL: 80,
    ActionId.SET_REMINDER: 78,
    ActionId.PURCHASE: 76,
    ActionId.BATCH_ACTION: 74,
    ActionId.SCHEDULE: 60,
    ActionId.SEND_MSG: 55,
    ActionId.WAIT: 10,
}


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace; preserve word boundaries."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _score_action(norm: str, patterns: Iterable[tuple[str, int]]) -> int:
    return sum(weight for phrase, weight in patterns if phrase in norm)


def _extract_target_id(norm: str) -> str | None:
    """Best-effort target id extraction.

    Looks for patterns like `event_123`, `email_5`, `contact_abc` — the kind of
    IDs our env scenarios emit. Returns the first match or None.
    """
    m = re.search(
        r"\b((?:event|email|contact|task|msg|msg_id)_[a-z0-9_-]+)\b", norm
    )
    return m.group(1) if m else None


def text_to_action(
    user_text: str,
    session_observation: dict | None = None,
) -> AriaAction:
    """Map a free-form user utterance to a concrete `AriaAction`.

    Parameters
    ----------
    user_text:
        Natural-language instruction from the user, e.g. "reschedule my 3pm to Thursday".
    session_observation:
        Optional current env observation (dict form). Reserved for future use —
        e.g. disambiguating "reply to that email" using the top inbox item.

    Returns
    -------
    AriaAction
        With `action_id` chosen by weighted keyword match, `target_id` extracted
        from the text when possible, and the raw `user_text` stashed in
        `payload.user_text` so downstream code can inspect it.
    """
    norm = _normalize(user_text)

    scores: dict[ActionId, int] = {}
    for action, patterns in _KEYWORDS.items():
        s = _score_action(norm, patterns)
        if s > 0:
            scores[action] = s

    if not scores:
        chosen = ActionId.WAIT
    else:
        # Rank by (score DESC, priority DESC).
        chosen = max(
            scores.items(),
            key=lambda kv: (kv[1], _PRIORITY.get(kv[0], 0)),
        )[0]

    target_id = _extract_target_id(norm)

    payload: dict = {"user_text": user_text}

    # Attach a lightweight observation hint when we have it — downstream
    # handlers (e.g. PURCHASE) might want the current inbox/calendar context.
    if session_observation is not None:
        payload["has_observation"] = True

    return AriaAction(
        action_id=int(chosen),
        target_id=target_id,
        payload=payload,
    )


__all__ = ["text_to_action"]
