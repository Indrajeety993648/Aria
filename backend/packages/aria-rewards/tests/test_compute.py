"""Per-dimension reward shaping tests — these are the guardrails that
downstream scenario work depends on.
"""
from __future__ import annotations

from aria_contracts import ActionId, RewardBreakdown
from aria_rewards import StepContext, compute_step_reward, compute_terminal_reward


def _ctx(action_id: int, outcome=None, is_terminal=False, **kw) -> StepContext:
    return StepContext(
        action_id=action_id,
        target_id=kw.get("target_id"),
        payload=kw.get("payload", {}),
        scenario_category=kw.get("scenario_category", "calendar_conflict"),
        difficulty=kw.get("difficulty", "medium"),
        step_count=kw.get("step_count", 0),
        max_steps=kw.get("max_steps", 50),
        is_terminal=is_terminal,
        pre={},
        post={},
        outcome=outcome or {},
    )


# -----------------------------------------------------------------------------
# task_completion
# -----------------------------------------------------------------------------


def test_task_completion_rewards_completion():
    r = compute_step_reward(_ctx(ActionId.DELEGATE.value, {"tasks_completed": ["t1"]}))
    assert r.task_completion > 0
    assert r.total > 0


def test_task_completion_penalizes_overdue():
    r = compute_step_reward(_ctx(ActionId.WAIT.value, {"tasks_overdue": ["t1"]}))
    assert r.task_completion < 0


def test_task_advancing_action_gets_small_positive():
    r = compute_step_reward(
        _ctx(ActionId.DRAFT_REPLY.value, {"success": True})
    )
    assert 0 < r.task_completion <= 0.1


# -----------------------------------------------------------------------------
# relationship_health
# -----------------------------------------------------------------------------


def test_cancel_high_closeness_without_alt_penalizes():
    r = compute_step_reward(
        _ctx(
            ActionId.CANCEL.value,
            {"affected_high_closeness": True, "proposed_alternative": False},
        )
    )
    assert r.relationship_health <= -0.5


def test_cancel_with_alternative_is_milder():
    r_alt = compute_step_reward(
        _ctx(
            ActionId.CANCEL.value,
            {"affected_high_closeness": True, "proposed_alternative": True},
        )
    )
    r_bad = compute_step_reward(
        _ctx(
            ActionId.CANCEL.value,
            {"affected_high_closeness": True, "proposed_alternative": False},
        )
    )
    assert r_alt.relationship_health > r_bad.relationship_health


def test_successful_conflict_resolution_boosts_relationship():
    r = compute_step_reward(
        _ctx(ActionId.RESOLVE_CONFLICT.value, {"success": True})
    )
    assert r.relationship_health > 0


def test_tone_mismatch_is_negative():
    r = compute_step_reward(
        _ctx(ActionId.SEND_MSG.value, {"tone_mismatch": True})
    )
    assert r.relationship_health < 0


# -----------------------------------------------------------------------------
# user_satisfaction
# -----------------------------------------------------------------------------


def test_objective_met_boosts_satisfaction():
    r = compute_step_reward(
        _ctx(ActionId.SCHEDULE.value, {"scenario_objective_met": True})
    )
    assert r.user_satisfaction > 0.5


def test_asking_too_much_penalizes():
    r = compute_step_reward(
        _ctx(ActionId.ASK_USER.value, {"asking_too_much": True})
    )
    assert r.user_satisfaction < 0


def test_unwarranted_escalation_penalizes():
    r = compute_step_reward(
        _ctx(ActionId.ESCALATE.value, {"escalation_warranted": False})
    )
    assert r.user_satisfaction < 0


# -----------------------------------------------------------------------------
# time_efficiency
# -----------------------------------------------------------------------------


def test_batching_rewards_efficiency():
    r = compute_step_reward(
        _ctx(ActionId.BATCH_ACTION.value, {"success": True, "batch_size": 4})
    )
    assert r.time_efficiency > 0


def test_wait_with_urgent_pending_penalizes():
    r = compute_step_reward(
        _ctx(ActionId.WAIT.value, {"urgent_pending_count": 2})
    )
    assert r.time_efficiency < 0


def test_wait_when_idle_is_neutral():
    r = compute_step_reward(_ctx(ActionId.WAIT.value, {"urgent_pending_count": 0}))
    assert r.time_efficiency == 0.0


# -----------------------------------------------------------------------------
# conflict_resolution
# -----------------------------------------------------------------------------


def test_win_win_resolution_is_one():
    r = compute_step_reward(
        _ctx(ActionId.RESOLVE_CONFLICT.value, {"conflict_resolved": True})
    )
    assert r.conflict_resolution == 1.0


def test_sacrifice_resolution_is_partial():
    r = compute_step_reward(
        _ctx(
            ActionId.CANCEL.value,
            {"conflict_resolved": True, "conflict_sacrifice": True},
        )
    )
    assert r.conflict_resolution == 0.3


def test_terminal_unresolved_conflict_penalizes():
    r = compute_step_reward(
        _ctx(
            ActionId.WAIT.value,
            {"conflict_resolved": False},
            is_terminal=True,
        )
    )
    assert r.conflict_resolution == -0.5


def test_no_active_conflict_neutral():
    r = compute_step_reward(_ctx(ActionId.WAIT.value, {}))
    assert r.conflict_resolution == 0.0


# -----------------------------------------------------------------------------
# safety
# -----------------------------------------------------------------------------


def test_unauthorized_purchase_severe_penalty():
    r = compute_step_reward(
        _ctx(ActionId.PURCHASE.value, {"authorized": False})
    )
    assert r.safety == -2.0


def test_high_stakes_message_without_approval_penalizes():
    r = compute_step_reward(
        _ctx(
            ActionId.SEND_MSG.value,
            {"high_stakes": True, "user_approved": False},
        )
    )
    assert r.safety == -1.5


def test_authorized_purchase_is_neutral():
    r = compute_step_reward(
        _ctx(ActionId.PURCHASE.value, {"authorized": True})
    )
    assert r.safety == 0.0


# -----------------------------------------------------------------------------
# total + weight formula
# -----------------------------------------------------------------------------


def test_total_is_weighted_sum():
    r = compute_step_reward(
        _ctx(
            ActionId.RESOLVE_CONFLICT.value,
            {
                "success": True,
                "conflict_resolved": True,
                "scenario_objective_met": True,
            },
        )
    )
    expected = r.compute_total()
    assert abs(r.total - expected) < 1e-9


def test_optimal_beats_pathological_meaningfully():
    optimal = compute_step_reward(
        _ctx(
            ActionId.RESOLVE_CONFLICT.value,
            {
                "success": True,
                "conflict_resolved": True,
                "scenario_objective_met": True,
                "closeness_delta": 0.3,
            },
        )
    )
    pathological = compute_step_reward(
        _ctx(
            ActionId.CANCEL.value,
            {
                "affected_high_closeness": True,
                "proposed_alternative": False,
                "scenario_objective_hurt": True,
                "wasted_action": True,
            },
        )
    )
    assert optimal.total - pathological.total > 0.5


# -----------------------------------------------------------------------------
# terminal
# -----------------------------------------------------------------------------


def test_terminal_perfect_day_positive():
    r = compute_terminal_reward(
        "calendar_conflict",
        "medium",
        {
            "unresolved_conflicts": 0,
            "open_high_priority_tasks": 0,
            "objectives_met": 3,
            "objectives_total": 3,
            "relationships_neglected": 0,
        },
    )
    assert r.total > 0.3


def test_terminal_bad_day_negative():
    r = compute_terminal_reward(
        "calendar_conflict",
        "hard",
        {
            "unresolved_conflicts": 2,
            "open_high_priority_tasks": 5,
            "objectives_met": 0,
            "objectives_total": 3,
            "relationships_neglected": 4,
            "budget_breach": True,
        },
    )
    assert r.total < 0


def test_terminal_accumulate_with_running_sum():
    running = RewardBreakdown.zero()
    term = compute_terminal_reward(
        "email_triage",
        "easy",
        {"objectives_met": 2, "objectives_total": 2},
    )
    combined = running.accumulate(term)
    assert abs(combined.total - term.total) < 1e-9
