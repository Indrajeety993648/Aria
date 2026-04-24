"""Convert a `WorldModel` into an `AriaObservation` for the agent."""
from __future__ import annotations

from aria_contracts import AriaObservation, RewardBreakdown

from env_service.world import WorldModel


def to_observation(
    world: WorldModel,
    *,
    reward_total: float | None = None,
    reward_breakdown: RewardBreakdown | None = None,
    done: bool = False,
) -> AriaObservation:
    return AriaObservation(
        done=done,
        reward=reward_total,
        metadata={"step_count": world.step_count},
        time=world.time,
        location=world.location,
        calendar=[e.model_copy() for e in world.calendar],
        inbox=[i.model_copy() for i in world.inbox],
        relationships=[r.model_copy() for r in world.relationships],
        pending_tasks=[t.model_copy() for t in world.pending_tasks],
        preferences=list(world.preferences),
        scenario_category=world.scenario_category,  # type: ignore[arg-type]
        difficulty=world.difficulty,  # type: ignore[arg-type]
        step_count=world.step_count,
        max_steps=world.max_steps,
        reward_breakdown=reward_breakdown,
    )
