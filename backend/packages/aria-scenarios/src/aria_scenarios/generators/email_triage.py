"""Email-triage scenarios.

Invariant: inbox has a clearly-urgent subset that must be addressed; the rest
is noise. Agent must prioritize correctly.
"""
from __future__ import annotations

from aria_contracts import Difficulty, InboxItem

from aria_scenarios.data import EMAIL_SUBJECTS
from aria_scenarios.generators._common import (
    build_calendar,
    build_inbox,
    build_relationships,
    build_tasks,
    fresh_prefs,
)
from aria_scenarios.rng import choice, integer, make_rng, uniform
from aria_scenarios.spec import Objective, ScenarioSpec


def generate(difficulty: Difficulty, seed: int) -> ScenarioSpec:
    rng = make_rng(seed)
    rels = build_relationships(rng, difficulty)
    contact_ids = [r.contact_id for r in rels]

    calendar = build_calendar(rng, difficulty, contact_ids, n_override=3)
    base_inbox = build_inbox(rng, difficulty, senders=contact_ids)

    # Inject a guaranteed-urgent subset
    n_urgent = {"easy": 2, "medium": 4, "hard": 7}[difficulty]
    urgent_items: list[InboxItem] = []
    boss_id = next((r.contact_id for r in rels if r.relationship_kind == "boss"), contact_ids[0])
    for i in range(n_urgent):
        urgent_items.append(
            InboxItem(
                email_id=f"urg_{i:03d}",
                sender_id=boss_id if i == 0 else choice(rng, contact_ids),
                subject=choice(rng, EMAIL_SUBJECTS),
                urgency=uniform(rng, 0.85, 0.99),
                age_hours=uniform(rng, 0.1, 4.0),
                requires_reply=True,
                sentiment=uniform(rng, -0.3, 0.3),
            )
        )
    inbox = urgent_items + base_inbox
    inbox.sort(key=lambda x: -x.urgency)

    tasks = build_tasks(rng, difficulty, n_override=2)

    objectives = [
        Objective(kind="reply_to_urgent", target_id=it.email_id)
        for it in urgent_items
    ]

    hidden = {
        "urgent_email_ids": [it.email_id for it in urgent_items],
        "budget_limit": 0.0,
    }

    return ScenarioSpec(
        category="email_triage",
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
