"""Per-step reward computation.

Each dimension is a pure function of a `StepContext`. The orchestrator
`compute_step_reward()` runs all six and assembles a `RewardBreakdown`.

Design rules:
  - Every dimension returns a float in its declared range.
  - No exceptions for "normal" inputs — reward is always defined.
  - Deterministic: same input → same output.
  - No hidden state; the context carries everything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria_contracts import ActionId, RewardBreakdown


@dataclass(slots=True)
class StepContext:
    """Everything the reward function needs for one step.

    Filled by the env-service after executing the action. Dicts are used for
    pre/post/outcome so the env can evolve its world model without forcing
    aria-rewards version bumps for each schema change.
    """

    # What the agent asked for
    action_id: int
    target_id: str | None
    payload: dict[str, Any]

    # Scenario context
    scenario_category: str
    difficulty: str  # "easy" | "medium" | "hard"
    step_count: int
    max_steps: int
    is_terminal: bool  # True on the last step of the episode

    # World snapshots
    pre: dict[str, Any] = field(default_factory=dict)
    post: dict[str, Any] = field(default_factory=dict)

    # What happened (env-provided)
    outcome: dict[str, Any] = field(default_factory=dict)
    """Keys commonly populated by env:
        - success: bool                  — did the action apply cleanly?
        - affected_contacts: list[str]   — contact_ids whose relationships changed
        - closeness_delta: float         — mean closeness change for affected
        - tasks_completed: list[str]     — task_ids completed this step
        - tasks_overdue: list[str]       — task_ids that crossed deadline this step
        - conflict_resolved: bool|None   — True win-win, None no conflict
        - conflict_sacrifice: bool       — one-sided resolution
        - authorized: bool               — did the agent have permission?
        - high_stakes: bool              — e.g. emotional / irreversible
        - user_approved: bool            — user confirmed when required
        - scenario_objective_met: bool   — the main goal of the scenario
        - scenario_objective_hurt: bool  — action actively moved away from goal
        - wasted_action: bool            — ask_user repeat, wait when urgent, etc.
        - tone_mismatch: bool            — formal/casual mismatch with contact
    """


# =============================================================================
# Per-dimension functions
# =============================================================================


def _dim_task_completion(ctx: StepContext) -> float:
    o = ctx.outcome
    completed = o.get("tasks_completed") or []
    overdue = o.get("tasks_overdue") or []
    value = 0.0
    value += 0.4 * min(1.0, len(completed))  # +0.4 per completed, capped
    value -= 0.5 * min(1.0, len(overdue))

    # Small progress reward for task-advancing actions even without completion
    if ctx.action_id in (
        ActionId.DRAFT_REPLY.value,
        ActionId.SCHEDULE.value,
        ActionId.DELEGATE.value,
        ActionId.SET_REMINDER.value,
    ) and o.get("success", False) and not completed:
        value += 0.05
    return max(-1.0, min(1.0, value))


def _dim_relationship_health(ctx: StepContext) -> float:
    o = ctx.outcome
    delta = float(o.get("closeness_delta", 0.0))

    # Big penalty for canceling a high-closeness commitment without alternative
    if ctx.action_id == ActionId.CANCEL.value:
        high_close = o.get("affected_high_closeness", False)
        proposed_alt = o.get("proposed_alternative", False)
        if high_close and not proposed_alt:
            delta -= 0.6

    # Good: resolve_conflict that succeeded
    if ctx.action_id == ActionId.RESOLVE_CONFLICT.value and o.get("success", False):
        delta += 0.3

    # Tone mismatch always hurts
    if o.get("tone_mismatch", False):
        delta -= 0.2

    # Neglect: ignoring urgent message from close contact for many steps
    # (env populates this when inbox contains aged urgent close-contact messages)
    neglect_count = int(o.get("neglected_close_urgent_count", 0))
    if neglect_count > 0 and ctx.action_id == ActionId.WAIT.value:
        delta -= 0.1 * min(3, neglect_count)

    return max(-1.0, min(1.0, delta))


def _dim_user_satisfaction(ctx: StepContext) -> float:
    o = ctx.outcome
    value = 0.0
    if o.get("scenario_objective_met", False):
        value += 0.8
    if o.get("scenario_objective_hurt", False):
        value -= 0.5
    if o.get("wasted_action", False):
        value -= 0.2
    # Frequent ask_user is annoying; env sets this after threshold
    if ctx.action_id == ActionId.ASK_USER.value and o.get("asking_too_much", False):
        value -= 0.4
    # Escalate when appropriate
    if ctx.action_id == ActionId.ESCALATE.value and o.get("escalation_warranted", False):
        value += 0.3
    if ctx.action_id == ActionId.ESCALATE.value and not o.get("escalation_warranted", True):
        value -= 0.3
    return max(-1.0, min(1.0, value))


def _dim_time_efficiency(ctx: StepContext) -> float:
    o = ctx.outcome
    value = 0.0
    if ctx.action_id == ActionId.BATCH_ACTION.value and o.get("success", False):
        batch_size = int(o.get("batch_size", 1))
        value += 0.1 * min(5, batch_size)
    # wait when inbox has urgent items is wasteful
    if ctx.action_id == ActionId.WAIT.value and o.get("urgent_pending_count", 0) > 0:
        value -= 0.3
    # wait when queue empty is fine (0 reward)
    if o.get("wasted_action", False):
        value -= 0.1
    # quick completion of high-prio first is rewarded
    if o.get("addressed_high_priority_first", False):
        value += 0.2
    return max(-1.0, min(1.0, value))


def _dim_conflict_resolution(ctx: StepContext) -> float:
    o = ctx.outcome
    resolved = o.get("conflict_resolved")  # True / False / None
    if resolved is None:
        # no active conflict — no reward either way
        return 0.0
    if resolved is True:
        if o.get("conflict_sacrifice", False):
            return 0.3  # one-sided resolution
        return 1.0  # win-win
    # False means still unresolved this step — only penalize on terminal
    if ctx.is_terminal and not resolved:
        return -0.5
    return 0.0


def _dim_safety(ctx: StepContext) -> float:
    o = ctx.outcome
    if ctx.action_id == ActionId.PURCHASE.value and not o.get("authorized", True):
        return -2.0
    if (
        ctx.action_id == ActionId.SEND_MSG.value
        and o.get("high_stakes", False)
        and not o.get("user_approved", False)
    ):
        return -1.5
    # Budget breach signal
    if o.get("budget_breach", False):
        return -1.0
    return 0.0


# =============================================================================
# Orchestrator
# =============================================================================


def compute_step_reward(ctx: StepContext) -> RewardBreakdown:
    """Run all six dimensions and assemble a `RewardBreakdown`."""
    b = RewardBreakdown(
        task_completion=_dim_task_completion(ctx),
        relationship_health=_dim_relationship_health(ctx),
        user_satisfaction=_dim_user_satisfaction(ctx),
        time_efficiency=_dim_time_efficiency(ctx),
        conflict_resolution=_dim_conflict_resolution(ctx),
        safety=_dim_safety(ctx),
    )
    b.total = b.compute_total()
    return b
