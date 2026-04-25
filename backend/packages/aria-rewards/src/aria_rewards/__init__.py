"""aria_rewards — six-dimensional reward function for the ARIA environment.

Pure functions. No I/O, no randomness, no globals. The env-service calls
`compute_step_reward(ctx)` after each action and receives a `RewardBreakdown`.
"""
from aria_rewards.compute import StepContext, compute_step_reward
from aria_rewards.rubrics import (
    AriaCompositeRubric,
    AriaDimensionRubric,
    ConflictResolutionRubric,
    RelationshipHealthRubric,
    SafetyRubric,
    TaskCompletionRubric,
    TimeEfficiencyRubric,
    UserSatisfactionRubric,
    evaluate_via_rubric,
)
from aria_rewards.terminal import compute_terminal_reward

__all__ = [
    "AriaCompositeRubric",
    "AriaDimensionRubric",
    "ConflictResolutionRubric",
    "RelationshipHealthRubric",
    "SafetyRubric",
    "StepContext",
    "TaskCompletionRubric",
    "TimeEfficiencyRubric",
    "UserSatisfactionRubric",
    "compute_step_reward",
    "compute_terminal_reward",
    "evaluate_via_rubric",
]
__version__ = "0.2.0"
