"""Shared helpers used by every generator.

Keeps the per-category generators short and focused on what makes them distinct.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from aria_contracts import (
    CalendarEvent,
    Difficulty,
    InboxItem,
    PendingTask,
    RelationshipNode,
)

from aria_scenarios.data import (
    CONTACTS,
    EMAIL_SUBJECTS,
    EVENT_TITLES,
    HINGLISH_EMAIL_SUBJECTS,
    TASK_TITLES,
)
from aria_scenarios.rng import choice, integer, pref_vector, sample, uniform


DIFFICULTY_KNOBS: dict[str, dict[str, int]] = {
    "easy":   {"n_events": 3,  "n_inbox": 6,  "n_tasks": 3},
    "medium": {"n_events": 8,  "n_inbox": 15, "n_tasks": 6},
    "hard":   {"n_events": 15, "n_inbox": 30, "n_tasks": 10},
}


# -----------------------------------------------------------------------------
# Relationships
# -----------------------------------------------------------------------------


def build_relationships(
    rng: np.random.Generator,
    difficulty: Difficulty,
) -> list[RelationshipNode]:
    """Produce the full roster with stable IDs and difficulty-appropriate variance."""
    nodes: list[RelationshipNode] = []
    for cid, name, kind in CONTACTS:
        # Closeness varies by kind
        if kind in ("partner", "family"):
            closeness = uniform(rng, 0.85, 0.98)
        elif kind in ("boss", "report"):
            closeness = uniform(rng, 0.5, 0.8)
        elif kind == "friend":
            closeness = uniform(rng, 0.6, 0.9)
        else:
            closeness = uniform(rng, 0.2, 0.6)

        # Harder scenarios → more dormant relationships (larger last_contact)
        base_age = {"easy": (0.5, 24.0), "medium": (2.0, 96.0), "hard": (12.0, 240.0)}[
            difficulty
        ]
        age = uniform(rng, *base_age)

        tone = {
            "boss": "formal", "report": "direct", "partner": "warm",
            "family": "warm", "friend": "casual", "colleague": "direct",
            "vendor": "formal", "other": "casual",
        }[kind]

        # HIDDEN: per-contact mood. Drives the partial-observability mechanic
        # (see env_service.actions.send_msg / draft_reply). Mood is NEVER
        # exposed in AriaObservation — agents must INFER it from inbox
        # sentiment + last_contact_hours. Wider variance on harder scenarios
        # to make the inference problem harder.
        mood_range = {
            "easy":   (-0.20, 0.40),
            "medium": (-0.50, 0.40),
            "hard":   (-0.85, 0.50),
        }[difficulty]
        current_mood = uniform(rng, *mood_range)

        # Code-mix Hindi-English mechanic. Family + close friends + partner
        # default to hinglish at higher difficulty (cultural realism for the
        # Indian-market target user). Mismatching the language costs reward.
        hinglish_prob = {"easy": 0.0, "medium": 0.25, "hard": 0.45}[difficulty]
        if kind in ("partner", "family", "friend") and rng.random() < hinglish_prob:
            language_pref: str = "hinglish"
        else:
            language_pref = "en"

        nodes.append(
            RelationshipNode(
                contact_id=cid,
                name=name,
                relationship_kind=kind,  # type: ignore[arg-type]
                closeness=closeness,
                trust=uniform(rng, 0.5, 0.95),
                last_contact_hours=age,
                tone_preference=tone,  # type: ignore[arg-type]
                current_mood=current_mood,
                language_preference=language_pref,  # type: ignore[arg-type]
            )
        )
    return nodes


# -----------------------------------------------------------------------------
# Calendar
# -----------------------------------------------------------------------------


def build_calendar(
    rng: np.random.Generator,
    difficulty: Difficulty,
    contact_ids: list[str],
    n_override: int | None = None,
) -> list[CalendarEvent]:
    n = n_override if n_override is not None else DIFFICULTY_KNOBS[difficulty]["n_events"]
    events: list[CalendarEvent] = []
    for i in range(n):
        day = integer(rng, 0, 14)  # first two weeks
        start = uniform(rng, 8.0, 18.0)
        duration = uniform(rng, 0.5, 2.0)
        participants: list[str] = []
        if rng.random() < 0.7 and contact_ids:
            k = min(len(contact_ids), integer(rng, 1, 3))
            participants = sample(rng, contact_ids, k)
        events.append(
            CalendarEvent(
                event_id=f"evt_{i:03d}",
                day_offset=day,
                start_hour=start,
                end_hour=min(23.9, start + duration),
                title=choice(rng, EVENT_TITLES),
                priority=uniform(rng, 0.3, 0.9),
                flexibility=uniform(rng, 0.1, 0.9),
                participant_ids=participants,
            )
        )
    events.sort(key=lambda e: (e.day_offset, e.start_hour))
    return events


# -----------------------------------------------------------------------------
# Inbox
# -----------------------------------------------------------------------------


def build_inbox(
    rng: np.random.Generator,
    difficulty: Difficulty,
    senders: list[str],
    n_override: int | None = None,
    *,
    hinglish_senders: set[str] | None = None,
) -> list[InboxItem]:
    """Generate the inbox.

    If `hinglish_senders` is provided, messages from those contacts use the
    Hindi/Hinglish subject pool — agent must reply in matching language.
    """
    n = n_override if n_override is not None else DIFFICULTY_KNOBS[difficulty]["n_inbox"]
    items: list[InboxItem] = []
    hinglish_senders = hinglish_senders or set()
    for i in range(n):
        sender_id = choice(rng, senders) if senders else "c_other"
        subject = (
            choice(rng, HINGLISH_EMAIL_SUBJECTS)
            if sender_id in hinglish_senders
            else choice(rng, EMAIL_SUBJECTS)
        )
        items.append(
            InboxItem(
                email_id=f"em_{i:04d}",
                sender_id=sender_id,
                subject=subject,
                urgency=uniform(rng, 0.05, 0.7),  # bulk = low/mid urgency
                age_hours=uniform(rng, 0.5, 48.0),
                requires_reply=bool(rng.random() < 0.6),
                sentiment=uniform(rng, -0.2, 0.2),
            )
        )
    items.sort(key=lambda x: -x.urgency)
    return items


# -----------------------------------------------------------------------------
# Tasks
# -----------------------------------------------------------------------------


def build_tasks(
    rng: np.random.Generator,
    difficulty: Difficulty,
    n_override: int | None = None,
) -> list[PendingTask]:
    n = n_override if n_override is not None else DIFFICULTY_KNOBS[difficulty]["n_tasks"]
    tasks: list[PendingTask] = []
    for i in range(n):
        tasks.append(
            PendingTask(
                task_id=f"t_{i:03d}",
                title=choice(rng, TASK_TITLES),
                priority=uniform(rng, 0.2, 0.9),
                deadline_hours=uniform(rng, 1.0, 72.0),
                estimated_minutes=integer(rng, 10, 180),
                delegatable=bool(rng.random() < 0.4),
            )
        )
    return tasks


# -----------------------------------------------------------------------------
# Preferences
# -----------------------------------------------------------------------------


def fresh_prefs(rng: np.random.Generator) -> list[float]:
    return pref_vector(rng, length=64)
