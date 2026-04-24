"""WorldModel — mutable runtime state for one episode.

Built once from a `ScenarioSpec` at `reset()` time. Actions mutate it in-place.
Snapshots (for pre/post context to the reward function) are cheap deep copies
of only the fields we need.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from aria_contracts import (
    CalendarEvent,
    InboxItem,
    Location,
    PendingTask,
    RelationshipNode,
    RewardBreakdown,
)
from aria_scenarios import ScenarioSpec


@dataclass(slots=True)
class WorldModel:
    """Mutable episode state.

    Everything an action can read or write lives here. No behavior — handlers
    in `actions.py` operate on this struct.
    """

    # static-ish
    scenario_category: str
    difficulty: str
    seed: int
    max_steps: int

    # mutable
    step_count: int = 0
    time: float = 8.0
    location: Location = "home"
    calendar: list[CalendarEvent] = field(default_factory=list)
    inbox: list[InboxItem] = field(default_factory=list)
    relationships: list[RelationshipNode] = field(default_factory=list)
    pending_tasks: list[PendingTask] = field(default_factory=list)
    preferences: list[float] = field(default_factory=lambda: [0.0] * 64)

    # bookkeeping
    objectives: list[dict[str, Any]] = field(default_factory=list)
    hidden: dict[str, Any] = field(default_factory=dict)
    reward_so_far: RewardBreakdown = field(default_factory=RewardBreakdown.zero)

    # action history (for ask_user fatigue, user_satisfaction signals)
    action_history: list[int] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # Factories
    # -------------------------------------------------------------------------
    @classmethod
    def from_spec(cls, spec: ScenarioSpec, max_steps: int) -> "WorldModel":
        return cls(
            scenario_category=spec.category,
            difficulty=spec.difficulty,
            seed=spec.seed,
            max_steps=max_steps,
            time=spec.initial_time,
            location=spec.initial_location,
            calendar=[e.model_copy() for e in spec.calendar],
            inbox=[i.model_copy() for i in spec.inbox],
            relationships=[r.model_copy() for r in spec.relationships],
            pending_tasks=[t.model_copy() for t in spec.pending_tasks],
            preferences=list(spec.preferences),
            objectives=[
                {"kind": o.kind, "target_id": o.target_id, "weight": o.weight, "met": o.met}
                for o in spec.objectives
            ],
            hidden=copy.deepcopy(spec.hidden),
        )

    # -------------------------------------------------------------------------
    # Snapshots & lookups
    # -------------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Shallow serializable snapshot of the fields a reward function might read."""
        return {
            "step_count": self.step_count,
            "time": self.time,
            "location": self.location,
            "n_calendar": len(self.calendar),
            "n_inbox": len(self.inbox),
            "open_tasks": sum(1 for t in self.pending_tasks if t.status == "open"),
            "budget_used": self.hidden.get("budget_used", 0.0),
        }

    def find_event(self, event_id: str | None) -> CalendarEvent | None:
        if event_id is None:
            return None
        for e in self.calendar:
            if e.event_id == event_id:
                return e
        return None

    def find_task(self, task_id: str | None) -> PendingTask | None:
        if task_id is None:
            return None
        for t in self.pending_tasks:
            if t.task_id == task_id:
                return t
        return None

    def find_email(self, email_id: str | None) -> InboxItem | None:
        if email_id is None:
            return None
        for e in self.inbox:
            if e.email_id == email_id:
                return e
        return None

    def find_contact(self, contact_id: str | None) -> RelationshipNode | None:
        if contact_id is None:
            return None
        for r in self.relationships:
            if r.contact_id == contact_id:
                return r
        return None

    # -------------------------------------------------------------------------
    # Terminal state helpers
    # -------------------------------------------------------------------------
    def is_terminal(self) -> bool:
        if self.step_count >= self.max_steps:
            return True
        if self.time >= 24.0:
            return True
        if self.objectives and all(o["met"] for o in self.objectives):
            return True
        return False

    def terminal_state_dict(self) -> dict[str, Any]:
        unresolved = self._unresolved_conflicts_count()
        open_hp = sum(
            1 for t in self.pending_tasks
            if t.status == "open" and t.priority >= 0.7
        )
        objectives_met = sum(1 for o in self.objectives if o["met"])
        objectives_total = max(1, len(self.objectives))
        neglected = sum(
            1 for r in self.relationships
            if r.closeness >= 0.7 and r.last_contact_hours > 48.0
        )
        return {
            "unresolved_conflicts": unresolved,
            "open_high_priority_tasks": open_hp,
            "objectives_met": objectives_met,
            "objectives_total": objectives_total,
            "relationships_neglected": neglected,
            "budget_breach": bool(
                self.hidden.get("budget_used", 0.0)
                > self.hidden.get("budget_limit", float("inf"))
            ),
        }

    def _unresolved_conflicts_count(self) -> int:
        """Count pairs of day-0 overlapping events that haven't been resolved."""
        day0 = [e for e in self.calendar if e.day_offset == 0]
        conflicts = 0
        for i, a in enumerate(day0):
            for b in day0[i + 1 :]:
                if a.start_hour < b.end_hour and b.start_hour < a.end_hour:
                    conflicts += 1
        return conflicts
