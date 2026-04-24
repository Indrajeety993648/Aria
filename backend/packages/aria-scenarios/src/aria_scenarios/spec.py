"""Scenario spec dataclass — what a generator returns."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria_contracts import (
    CalendarEvent,
    Difficulty,
    InboxItem,
    Location,
    PendingTask,
    RelationshipNode,
    ScenarioCategory,
)


@dataclass(slots=True)
class Objective:
    """One hidden objective for the scenario.

    The env evaluates these after each action to populate
    `scenario_objective_met` / `scenario_objective_hurt` in the reward outcome.
    """

    kind: str                       # e.g. "resolve_conflict", "reply_to_urgent", "stay_in_budget"
    target_id: str | None = None    # the entity this objective is about
    weight: float = 1.0             # contribution to terminal objectives_met
    met: bool = False


@dataclass(slots=True)
class ScenarioSpec:
    category: ScenarioCategory
    difficulty: Difficulty
    seed: int

    # initial observation data
    initial_time: float = 8.0  # 8 AM
    initial_location: Location = "home"
    calendar: list[CalendarEvent] = field(default_factory=list)
    inbox: list[InboxItem] = field(default_factory=list)
    relationships: list[RelationshipNode] = field(default_factory=list)
    pending_tasks: list[PendingTask] = field(default_factory=list)
    preferences: list[float] = field(default_factory=lambda: [0.0] * 64)

    # hidden state
    objectives: list[Objective] = field(default_factory=list)
    hidden: dict[str, Any] = field(default_factory=dict)

    def objectives_total(self) -> int:
        return len(self.objectives)
