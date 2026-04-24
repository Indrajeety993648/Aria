"""aria_rewards — six-dimensional reward function for the ARIA environment.

Pure functions. No I/O, no randomness, no globals. The env-service calls
`compute_step_reward(ctx)` after each action and receives a `RewardBreakdown`.
"""
from aria_rewards.compute import StepContext, compute_step_reward
from aria_rewards.terminal import compute_terminal_reward

__all__ = ["StepContext", "compute_step_reward", "compute_terminal_reward"]
__version__ = "0.1.0"
