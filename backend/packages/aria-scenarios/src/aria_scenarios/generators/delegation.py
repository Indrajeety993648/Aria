"""Delegation scenarios.

Agent has a pile of tasks; some can be delegated to reports/colleagues,
others must stay. Must identify delegatable ones and assign correctly.
"""
from __future__ import annotations

from aria_contracts import Difficulty, PendingTask

from aria_scenarios.data import TASK_TITLES
from aria_scenarios.generators._common import (
    build_calendar,
    build_inbox,
    build_relationships,
    fresh_prefs,
)
from aria_scenarios.rng import choice, integer, make_rng, uniform
from aria_scenarios.spec import Objective, ScenarioSpec


def generate(difficulty: Difficulty, seed: int) -> ScenarioSpec:
    rng = make_rng(seed)
    rels = build_relationships(rng, difficulty)
    contact_ids = [r.contact_id for r in rels]

    calendar = build_calendar(rng, difficulty, contact_ids, n_override=4)
    inbox = build_inbox(rng, difficulty, senders=contact_ids, n_override=5)

    n_tasks = {"easy": 5, "medium": 10, "hard": 15}[difficulty]
    n_delegatable = {"easy": 2, "medium": 4, "hard": 7}[difficulty]

    tasks: list[PendingTask] = []
    for i in range(n_tasks):
        delegatable = i < n_delegatable
        tasks.append(
            PendingTask(
                task_id=f"dt_{i:03d}",
                title=choice(rng, TASK_TITLES),
                priority=uniform(rng, 0.3, 0.95),
                deadline_hours=uniform(rng, 2.0, 48.0),
                estimated_minutes=integer(rng, 10, 120),
                delegatable=delegatable,
            )
        )

    # Preferred assignees: reports and colleagues
    assignable = [r.contact_id for r in rels if r.relationship_kind in ("report", "colleague")]
    if not assignable:
        assignable = contact_ids[:1]

    objectives = [
        Objective(kind="delegate_delegatable", target_id=t.task_id, weight=1.0)
        for t in tasks if t.delegatable
    ]

    hidden = {
        "delegatable_task_ids": [t.task_id for t in tasks if t.delegatable],
        "assignable_contact_ids": assignable,
        "budget_limit": 0.0,
    }

    return ScenarioSpec(
        category="delegation",
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
