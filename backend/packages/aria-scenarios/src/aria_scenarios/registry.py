"""Registry dispatching (category, difficulty, seed) to the right generator."""
from __future__ import annotations

from typing import Callable

from aria_contracts import Difficulty, ScenarioCategory

from aria_scenarios.generators import (
    calendar_conflict,
    delegation,
    dinner_planning,
    email_triage,
    message_reply,
    shopping,
)
from aria_scenarios.spec import ScenarioSpec

CATEGORIES: tuple[ScenarioCategory, ...] = (
    "calendar_conflict",
    "email_triage",
    "message_reply",
    "dinner_planning",
    "delegation",
    "shopping",
)

DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")

_GENERATORS: dict[str, Callable[[Difficulty, int], ScenarioSpec]] = {
    "calendar_conflict": calendar_conflict.generate,
    "email_triage": email_triage.generate,
    "message_reply": message_reply.generate,
    "dinner_planning": dinner_planning.generate,
    "delegation": delegation.generate,
    "shopping": shopping.generate,
}


def generate(
    category: ScenarioCategory,
    difficulty: Difficulty,
    seed: int,
) -> ScenarioSpec:
    if category not in _GENERATORS:
        raise ValueError(f"Unknown scenario category: {category}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    return _GENERATORS[category](difficulty, seed)
