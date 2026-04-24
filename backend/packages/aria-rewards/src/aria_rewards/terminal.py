"""Terminal-step reward adjustments.

Some signals are only meaningful at episode end: was the day's main objective met?
Did any calendar conflict remain unresolved? Are any high-priority tasks still open?
"""
from __future__ import annotations

from typing import Any

from aria_contracts import RewardBreakdown


def compute_terminal_reward(
    scenario_category: str,
    difficulty: str,
    final_state: dict[str, Any],
) -> RewardBreakdown:
    """Return an additional reward applied on the terminal step only.

    `final_state` is a plain dict supplied by the env. Commonly populated keys:
      - unresolved_conflicts: int
      - open_high_priority_tasks: int
      - objectives_met: int
      - objectives_total: int
      - relationships_neglected: int
      - budget_breach: bool
    """
    unresolved = int(final_state.get("unresolved_conflicts", 0))
    open_high = int(final_state.get("open_high_priority_tasks", 0))
    met = int(final_state.get("objectives_met", 0))
    total = max(1, int(final_state.get("objectives_total", 1)))
    neglected = int(final_state.get("relationships_neglected", 0))
    budget_breach = bool(final_state.get("budget_breach", False))

    objective_ratio = met / total  # 0..1

    b = RewardBreakdown(
        task_completion=max(-1.0, min(1.0, objective_ratio - 0.2 * open_high)),
        relationship_health=max(-1.0, min(1.0, -0.2 * neglected)),
        user_satisfaction=max(-1.0, min(1.0, objective_ratio)),
        time_efficiency=0.0,
        conflict_resolution=0.0 if unresolved == 0 else max(-1.0, -0.3 * unresolved),
        safety=-1.0 if budget_breach else 0.0,
    )
    b.total = b.compute_total()
    return b
