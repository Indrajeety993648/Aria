"""Message-reply scenarios.

Invariant: one message from a high-closeness contact with loaded sentiment.
Agent must reply with the right tone. On hard, multiple such messages.
"""
from __future__ import annotations

from aria_contracts import Difficulty, InboxItem

from aria_scenarios.data import HINGLISH_EMAIL_SUBJECTS
from aria_scenarios.generators._common import (
    build_calendar,
    build_inbox,
    build_relationships,
    build_tasks,
    fresh_prefs,
)
from aria_scenarios.rng import choice, make_rng, uniform
from aria_scenarios.spec import Objective, ScenarioSpec


def generate(difficulty: Difficulty, seed: int) -> ScenarioSpec:
    rng = make_rng(seed)
    rels = build_relationships(rng, difficulty)
    contact_ids = [r.contact_id for r in rels]
    hinglish_senders = {r.contact_id for r in rels if r.language_preference == "hinglish"}

    calendar = build_calendar(rng, difficulty, contact_ids, n_override=4)
    base_inbox = build_inbox(
        rng, difficulty, senders=contact_ids, n_override=4,
        hinglish_senders=hinglish_senders,
    )

    # The "loaded" message(s)
    close_contacts = [r for r in rels if r.closeness >= 0.8]
    if not close_contacts:
        close_contacts = [rels[0]]

    n_loaded = {"easy": 1, "medium": 2, "hard": 3}[difficulty]
    loaded_items: list[InboxItem] = []
    loaded_ids: list[str] = []
    for i in range(n_loaded):
        contact = close_contacts[i % len(close_contacts)]
        # negative sentiment = upset
        sentiment = uniform(rng, -0.95, -0.4)
        # Subject must respect language preference so the agent's inference
        # task is consistent with the language gate.
        if contact.language_preference == "hinglish":
            subject = choice(rng, HINGLISH_EMAIL_SUBJECTS)
        else:
            subject = "Are you free to talk?"
        loaded_items.append(
            InboxItem(
                email_id=f"loaded_{i:03d}",
                sender_id=contact.contact_id,
                subject=subject,
                urgency=0.9,
                age_hours=uniform(rng, 0.5, 3.0),
                requires_reply=True,
                sentiment=sentiment,
            )
        )
        loaded_ids.append(loaded_items[-1].email_id)

    inbox = loaded_items + base_inbox
    inbox.sort(key=lambda x: -x.urgency)

    tasks = build_tasks(rng, difficulty, n_override=2)

    objectives = [
        Objective(kind="reply_with_correct_tone", target_id=eid, weight=1.5)
        for eid in loaded_ids
    ]

    hidden = {
        "loaded_email_ids": loaded_ids,
        "loaded_contact_tones": {
            it.email_id: next(
                r.tone_preference for r in rels if r.contact_id == it.sender_id
            )
            for it in loaded_items
        },
        "budget_limit": 0.0,
    }

    return ScenarioSpec(
        category="message_reply",
        difficulty=difficulty,
        seed=seed,
        calendar=calendar,
        inbox=inbox,
        relationships=rels,
        pending_tasks=tasks,
        preferences=fresh_prefs(rng),
        objectives=objectives,
        hidden=hidden,
    )
