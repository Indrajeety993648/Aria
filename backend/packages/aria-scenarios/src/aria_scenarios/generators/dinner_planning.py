"""Dinner-planning scenarios.

Multi-constraint coordination: participants, dietary restrictions,
time windows, budget.
"""
from __future__ import annotations

from aria_contracts import CalendarEvent, Difficulty, PendingTask

from aria_scenarios.generators._common import (
    build_calendar,
    build_inbox,
    build_relationships,
    fresh_prefs,
)
from aria_scenarios.rng import integer, make_rng, sample, uniform
from aria_scenarios.spec import Objective, ScenarioSpec


DIETS = ["vegetarian", "vegan", "gluten_free", "pescatarian", "none"]


def generate(difficulty: Difficulty, seed: int) -> ScenarioSpec:
    rng = make_rng(seed)
    rels = build_relationships(rng, difficulty)
    contact_ids = [r.contact_id for r in rels]

    # Pick participants
    n_participants = {"easy": 2, "medium": 4, "hard": 6}[difficulty]
    n_participants = min(n_participants, len(rels))
    participants = [r.contact_id for r in rels[:n_participants]]

    # Assign constraints
    diets = {cid: DIETS[integer(rng, 0, len(DIETS))] for cid in participants}
    windows = {
        cid: (uniform(rng, 18.0, 19.5), uniform(rng, 20.0, 22.0))
        for cid in participants
    }
    budgets = {cid: uniform(rng, 800.0, 2500.0) for cid in participants}
    min_budget = min(budgets.values())

    calendar = build_calendar(rng, difficulty, contact_ids)
    # Add the planned dinner slot as a tentative event
    dinner_hr = max(w[0] for w in windows.values())
    calendar.append(
        CalendarEvent(
            event_id="dinner_slot",
            day_offset=0,
            start_hour=dinner_hr,
            end_hour=dinner_hr + 1.5,
            title="Dinner (planning)",
            priority=0.75,
            flexibility=0.4,
            participant_ids=participants,
        )
    )
    calendar.sort(key=lambda e: (e.day_offset, e.start_hour))

    inbox = build_inbox(rng, difficulty, senders=contact_ids)

    pending_tasks = [
        PendingTask(
            task_id="dinner_plan",
            title="Finalize dinner plan",
            priority=0.85,
            deadline_hours=uniform(rng, 4.0, 10.0),
            estimated_minutes=20,
            delegatable=False,
        )
    ]

    objectives = [Objective(kind="dinner_plan_all_constraints_met", weight=2.0)]

    hidden = {
        "dinner_participants": participants,
        "dietary_restrictions": diets,
        "time_windows": windows,
        "budget_per_head_max": min_budget,
        "budget_limit": min_budget * len(participants),
        "budget_used": 0.0,
    }

    return ScenarioSpec(
        category="dinner_planning",
        difficulty=difficulty,
        seed=seed,
        calendar=calendar,
        inbox=inbox,
        relationships=rels,
        pending_tasks=pending_tasks,
        preferences=fresh_prefs(rng),
        objectives=objectives,
        hidden=hidden,
    )
