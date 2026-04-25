"""OpenEnv-Rubric flavored wrappers around the six reward dimensions.

Why this exists
---------------
The hackathon judging doc explicitly hints that "composable rubrics > monolithic
scoring." OpenEnv's `Rubric` framework lets us:

  - expose each dimension as an independently inspectable component
    (`env.rubric.named_rubrics()` returns all six),
  - hang hooks per-dimension (logging, debugging),
  - swap or zero a dimension at runtime for ablation studies (we use this
    for the `relationship_health`-removed ablation in the training write-up).

The reward MATH is unchanged — same per-dimension functions, same weights,
same per-step bound — so all 25+ existing reward tests pass untouched.

Stateful context
----------------
OpenEnv's `Rubric.forward(action, observation)` only takes those two args, but
our reward depends on a richer `StepContext` (pre/post snapshots, outcome
dict, scenario meta). We bridge by storing the context on the composite via
`set_context()` *before* invoking `__call__`. Children read it through the
shared parent reference. This is the pattern OpenEnv expects for stateful
rubric trees.
"""
from __future__ import annotations

from typing import Any

from aria_contracts import REWARD_WEIGHTS, RewardBreakdown
from openenv.core.rubrics.base import Rubric

from aria_rewards.compute import (
    StepContext,
    _dim_conflict_resolution,
    _dim_relationship_health,
    _dim_safety,
    _dim_task_completion,
    _dim_time_efficiency,
    _dim_user_satisfaction,
)


# =============================================================================
# Per-dimension rubrics
# =============================================================================


class AriaDimensionRubric(Rubric):
    """Base for ARIA's per-dimension rubrics.

    Subclasses implement `_dim_fn(ctx)`. The composite parent stamps the
    current `StepContext` onto each child before it's invoked.
    """

    weight: float = 0.0

    def __init__(self) -> None:
        super().__init__()
        self._ctx: StepContext | None = None

    def set_context(self, ctx: StepContext) -> None:
        self._ctx = ctx

    def reset(self) -> None:
        self._ctx = None
        # last_score is reset by parent class on next forward()

    # Subclasses override _dim_fn; forward() is identical across them.
    def _dim_fn(self, ctx: StepContext) -> float:  # pragma: no cover - abstract
        raise NotImplementedError

    def forward(self, action: Any, observation: Any) -> float:
        # action / observation are unused — context is the source of truth.
        del action, observation
        if self._ctx is None:
            return 0.0
        return self._dim_fn(self._ctx)


class TaskCompletionRubric(AriaDimensionRubric):
    """Tasks completed on time vs. tasks let to slip past deadline."""
    weight = REWARD_WEIGHTS["task_completion"]
    def _dim_fn(self, ctx: StepContext) -> float:
        return _dim_task_completion(ctx)


class RelationshipHealthRubric(AriaDimensionRubric):
    """Relationship-graph delta from this action.

    THE novel signal: penalizes solving tasks at the cost of trust /
    closeness with high-closeness contacts. Cancel a partner's event without
    proposing an alternative → big negative regardless of "task done."
    """
    weight = REWARD_WEIGHTS["relationship_health"]
    def _dim_fn(self, ctx: StepContext) -> float:
        return _dim_relationship_health(ctx)


class UserSatisfactionRubric(AriaDimensionRubric):
    """How well the action serves the latent scenario objective."""
    weight = REWARD_WEIGHTS["user_satisfaction"]
    def _dim_fn(self, ctx: StepContext) -> float:
        return _dim_user_satisfaction(ctx)


class TimeEfficiencyRubric(AriaDimensionRubric):
    """Throughput: batching, prioritization, not waiting on urgent items."""
    weight = REWARD_WEIGHTS["time_efficiency"]
    def _dim_fn(self, ctx: StepContext) -> float:
        return _dim_time_efficiency(ctx)


class ConflictResolutionRubric(AriaDimensionRubric):
    """Win-win > sacrifice > unresolved at terminal step."""
    weight = REWARD_WEIGHTS["conflict_resolution"]
    def _dim_fn(self, ctx: StepContext) -> float:
        return _dim_conflict_resolution(ctx)


class SafetyRubric(AriaDimensionRubric):
    """Hard guard rail: unauthorized spend, sending without approval, budget breach."""
    weight = REWARD_WEIGHTS["safety"]
    def _dim_fn(self, ctx: StepContext) -> float:
        return _dim_safety(ctx)


# =============================================================================
# Composite
# =============================================================================


class AriaCompositeRubric(Rubric):
    """The hackathon-facing reward.

    Six children, each independently inspectable.

    >>> rubric = AriaCompositeRubric()
    >>> [name for name, _ in rubric.named_rubrics()]
    ['task_completion', 'relationship_health', 'user_satisfaction',
     'time_efficiency', 'conflict_resolution', 'safety']

    Usage:
        rubric.set_context(step_ctx)
        total = rubric(action, observation)          # weighted sum
        breakdown = rubric.last_breakdown()          # per-dim values
    """

    def __init__(self, *, ablate: tuple[str, ...] = ()) -> None:
        """
        Args:
            ablate: Names of dimensions to zero out. Used for the
                relationship_health-removed ablation study; the dimension
                still exists (for parity) but always returns 0.0.
        """
        super().__init__()
        # Auto-registered as children via __setattr__ in the base class.
        self.task_completion     = TaskCompletionRubric()
        self.relationship_health = RelationshipHealthRubric()
        self.user_satisfaction   = UserSatisfactionRubric()
        self.time_efficiency     = TimeEfficiencyRubric()
        self.conflict_resolution = ConflictResolutionRubric()
        self.safety              = SafetyRubric()
        # Track ablation directly on each child for transparency.
        self._ablated: set[str] = set(ablate)
        for n in self._ablated:
            child = self._rubric_children.get(n)
            if child is None:
                raise ValueError(f"Unknown ablation dimension: {n}")

    # -------------------------------------------------------------------------
    # Context plumbing
    # -------------------------------------------------------------------------

    def set_context(self, ctx: StepContext) -> None:
        """Stamp `ctx` onto every child before invocation."""
        for child in self._rubric_children.values():
            if isinstance(child, AriaDimensionRubric):
                child.set_context(ctx)

    def reset(self) -> None:
        """Per-episode reset — clears stored contexts on children."""
        for child in self._rubric_children.values():
            if hasattr(child, "reset"):
                child.reset()

    # -------------------------------------------------------------------------
    # Rubric.forward — invokes children, returns weighted total
    # -------------------------------------------------------------------------

    def forward(self, action: Any, observation: Any) -> float:
        total = 0.0
        for name, child in self._rubric_children.items():
            score = float(child(action, observation))
            if name in self._ablated:
                # Honor the ablation: child still computes (so introspection
                # is meaningful), but its contribution to `total` is zero.
                continue
            total += score * getattr(child, "weight", 0.0)
        return total

    # -------------------------------------------------------------------------
    # Convenience accessor used by env-service to populate AriaObservation
    # -------------------------------------------------------------------------

    def last_breakdown(self) -> RewardBreakdown:
        """Snapshot the last per-child score as a RewardBreakdown."""
        b = RewardBreakdown(
            task_completion=     float(self.task_completion.last_score     or 0.0),
            relationship_health= float(self.relationship_health.last_score or 0.0),
            user_satisfaction=   float(self.user_satisfaction.last_score   or 0.0),
            time_efficiency=     float(self.time_efficiency.last_score     or 0.0),
            conflict_resolution= float(self.conflict_resolution.last_score or 0.0),
            safety=              float(self.safety.last_score              or 0.0),
        )
        # If a dim is ablated, zero it in the surfaced breakdown too so
        # downstream consumers see what the agent actually felt.
        for name in self._ablated:
            object.__setattr__(b, name, 0.0)
        b.total = b.compute_total()
        return b


# =============================================================================
# Legacy adapter — keeps `compute_step_reward(ctx)` working
# =============================================================================


_DEFAULT_RUBRIC = AriaCompositeRubric()


def evaluate_via_rubric(ctx: StepContext) -> RewardBreakdown:
    """Public Rubric-flavored entry point.

    Reuses a singleton composite so child `last_score` values are observable
    after the call (e.g. for hooks / logging).
    """
    _DEFAULT_RUBRIC.set_context(ctx)
    _DEFAULT_RUBRIC(action=None, observation=None)
    return _DEFAULT_RUBRIC.last_breakdown()


__all__ = [
    "AriaCompositeRubric",
    "AriaDimensionRubric",
    "ConflictResolutionRubric",
    "RelationshipHealthRubric",
    "SafetyRubric",
    "TaskCompletionRubric",
    "TimeEfficiencyRubric",
    "UserSatisfactionRubric",
    "evaluate_via_rubric",
]
