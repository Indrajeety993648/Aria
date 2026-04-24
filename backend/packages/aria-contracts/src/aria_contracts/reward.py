"""Six-dimensional reward for ARIA.

Weights are the single source of truth for the reward function. They must match
the README and the judge-facing documentation. Changing them is a breaking
contract change — bump the package version.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

REWARD_WEIGHTS: dict[str, float] = {
    "task_completion":     0.25,
    "relationship_health": 0.20,
    "user_satisfaction":   0.20,
    "time_efficiency":     0.15,
    "conflict_resolution": 0.15,
    "safety":              0.05,
}

# Sanity: weights must sum to 1.0 (within float epsilon).
assert abs(sum(REWARD_WEIGHTS.values()) - 1.0) < 1e-9, (
    f"Reward weights must sum to 1.0; got {sum(REWARD_WEIGHTS.values())}"
)


class RewardBreakdown(BaseModel):
    """Per-dimension reward, plus the weighted total.

    No hard bounds in the type: per-step values are clamped by the reward
    compute functions (see `aria_rewards.compute`), while episode-accumulated
    values can legitimately exceed the per-step range. `total` is the weighted
    sum; kept as a stored field for cheap inspection.

    Per-step ranges (by contract in aria_rewards, not by validation here):
      task_completion      ∈ [-1, 1]
      relationship_health  ∈ [-1, 1]
      user_satisfaction    ∈ [-1, 1]
      time_efficiency      ∈ [-1, 1]
      conflict_resolution  ∈ [-1, 1]
      safety               ∈ [-2, 1]   (asymmetric — egregious safety violations hit hard)
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_completion:     float = 0.0
    relationship_health: float = 0.0
    user_satisfaction:   float = 0.0
    time_efficiency:     float = 0.0
    conflict_resolution: float = 0.0
    safety:              float = 0.0
    total:               float = 0.0

    def compute_total(self) -> float:
        """Recompute `total` from per-dim values and weights. Does not mutate."""
        return (
            REWARD_WEIGHTS["task_completion"]     * self.task_completion
            + REWARD_WEIGHTS["relationship_health"] * self.relationship_health
            + REWARD_WEIGHTS["user_satisfaction"]   * self.user_satisfaction
            + REWARD_WEIGHTS["time_efficiency"]     * self.time_efficiency
            + REWARD_WEIGHTS["conflict_resolution"] * self.conflict_resolution
            + REWARD_WEIGHTS["safety"]              * self.safety
        )

    def accumulate(self, other: "RewardBreakdown") -> "RewardBreakdown":
        """Sum two breakdowns dimension-wise, returning a new instance."""
        summed = RewardBreakdown(
            task_completion=     self.task_completion     + other.task_completion,
            relationship_health= self.relationship_health + other.relationship_health,
            user_satisfaction=   self.user_satisfaction   + other.user_satisfaction,
            time_efficiency=     self.time_efficiency     + other.time_efficiency,
            conflict_resolution= self.conflict_resolution + other.conflict_resolution,
            safety=              self.safety              + other.safety,
        )
        summed.total = summed.compute_total()
        return summed

    @classmethod
    def zero(cls) -> "RewardBreakdown":
        return cls()
