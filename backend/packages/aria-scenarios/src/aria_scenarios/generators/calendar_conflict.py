"""Calendar-conflict scenarios.

Invariant: at least 2 overlapping events on day 0, at least one of them
tagged as a high-closeness personal commitment.
"""
from __future__ import annotations

from aria_contracts import CalendarEvent, Difficulty

from aria_scenarios.generators._common import (
    DIFFICULTY_KNOBS,
    build_calendar,
    build_inbox,
    build_relationships,
    build_tasks,
    fresh_prefs,
)
from aria_scenarios.rng import make_rng, uniform
from aria_scenarios.spec import Objective, ScenarioSpec


def generate(difficulty: Difficulty, seed: int) -> ScenarioSpec:
    rng = make_rng(seed)
    rels = build_relationships(rng, difficulty)
    contact_ids = [r.contact_id for r in rels]

    # Base calendar
    base = build_calendar(rng, difficulty, contact_ids)

    # Inject the conflict: two overlapping events on day 0
    boss_id = next((r.contact_id for r in rels if r.relationship_kind == "boss"), contact_ids[0])
    close_id = next(
        (r.contact_id for r in rels if r.relationship_kind in ("partner", "family")),
        contact_ids[1 % len(contact_ids)],
    )

    start_hr = uniform(rng, 16.0, 19.0)
    work_evt = CalendarEvent(
        event_id="conflict_work",
        day_offset=0,
        start_hour=start_hr,
        end_hour=start_hr + 1.0,
        title="Board review with Priya",
        priority=0.9,
        flexibility=0.3,
        participant_ids=[boss_id],
    )
    personal_evt = CalendarEvent(
        event_id="conflict_personal",
        day_offset=0,
        start_hour=start_hr + 0.25,  # overlap
        end_hour=start_hr + 1.25,
        title="Riya's school play",
        priority=0.85,
        flexibility=0.1,
        participant_ids=[close_id],
    )
    calendar = base + [work_evt, personal_evt]
    calendar.sort(key=lambda e: (e.day_offset, e.start_hour))

    # On hard, add a second conflict later in the week
    if difficulty == "hard":
        hr2 = uniform(rng, 17.0, 20.0)
        calendar.append(
            CalendarEvent(
                event_id="conflict_secondary",
                day_offset=2,
                start_hour=hr2,
                end_hour=hr2 + 1.0,
                title="Quarterly review",
                priority=0.9,
                flexibility=0.2,
                participant_ids=[boss_id],
            )
        )
        calendar.append(
            CalendarEvent(
                event_id="conflict_secondary_alt",
                day_offset=2,
                start_hour=hr2 + 0.5,
                end_hour=hr2 + 1.5,
                title="Anniversary dinner",
                priority=0.95,
                flexibility=0.0,
                participant_ids=[close_id],
            )
        )

    inbox = build_inbox(rng, difficulty, senders=contact_ids)
    tasks = build_tasks(rng, difficulty)

    objectives: list[Objective] = [
        Objective(kind="resolve_day0_conflict", target_id="conflict_personal", weight=2.0),
    ]
    if difficulty == "hard":
        objectives.append(Objective(kind="resolve_day2_conflict", weight=1.5))

    hidden = {
        "primary_conflict": {
            "events": ["conflict_work", "conflict_personal"],
            "high_closeness_contact": close_id,
        },
        "budget_limit": 5000.0,
        "budget_used": 0.0,
    }

    return ScenarioSpec(
        category="calendar_conflict",
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
