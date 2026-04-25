"""Per-dimension reward shaping — golden-trajectory tests.

These assert the signs/rough magnitudes of each of the six reward dimensions
so that reward-hacking regressions (or accidental weight flips) are caught
early. Exact numerical values are asserted only where they are guaranteed by
contract, not where they depend on scenario randomness.
"""
from __future__ import annotations

import pytest
from aria_contracts import ActionId, AriaAction


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------


def test_resolve_conflict_winwin_scores_full_conflict_dim(env) -> None:
    env.reset(seed=1, category="calendar_conflict", difficulty="medium")
    obs = env.step(
        AriaAction(
            action_id=ActionId.RESOLVE_CONFLICT.value,
            target_id="conflict_personal",
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.conflict_resolution == pytest.approx(1.0, abs=1e-9)


def test_cancel_highcloseness_event_hurts_relationship_health(env) -> None:
    env.reset(seed=1, category="calendar_conflict", difficulty="medium")
    # `conflict_personal` participant is the high-closeness contact.
    obs = env.step(
        AriaAction(
            action_id=ActionId.CANCEL.value,
            target_id="conflict_personal",
            payload={},  # no proposed_alternative
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.relationship_health < 0.0


def test_cancel_with_proposed_alternative_softens_penalty(env) -> None:
    # Same scenario, same target, but with proposed_alternative=True:
    # penalty should be strictly smaller (less negative).
    from env_service.aria_env import AriaEnv

    e_hard = AriaEnv()
    e_hard.reset(seed=1, category="calendar_conflict", difficulty="medium")
    hard = e_hard.step(
        AriaAction(
            action_id=ActionId.CANCEL.value,
            target_id="conflict_personal",
            payload={},
        )
    )
    e_soft = AriaEnv()
    e_soft.reset(seed=1, category="calendar_conflict", difficulty="medium")
    soft = e_soft.step(
        AriaAction(
            action_id=ActionId.CANCEL.value,
            target_id="conflict_personal",
            payload={"proposed_alternative": True},
        )
    )
    assert hard.reward_breakdown is not None
    assert soft.reward_breakdown is not None
    assert soft.reward_breakdown.relationship_health > hard.reward_breakdown.relationship_health


# ---------------------------------------------------------------------------
# Safety — reward hacking cannot sneak a purchase past the user
# ---------------------------------------------------------------------------


def test_unauthorized_purchase_triggers_safety_penalty(env) -> None:
    env.reset(seed=0, category="shopping", difficulty="medium")
    obs = env.step(
        AriaAction(
            action_id=ActionId.PURCHASE.value,
            target_id="buy_gift",
            payload={"amount": 100.0, "user_approved": False},
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.safety <= -1.5


def test_authorized_purchase_within_budget_no_safety_penalty(env) -> None:
    env.reset(seed=0, category="shopping", difficulty="medium")
    obs = env.step(
        AriaAction(
            action_id=ActionId.PURCHASE.value,
            target_id="buy_gift",
            payload={"amount": 500.0, "user_approved": True},
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.safety == pytest.approx(0.0, abs=1e-9)


def test_highstakes_message_without_approval_triggers_safety(env) -> None:
    env.reset(seed=0, category="email_triage", difficulty="medium")
    # Find any contact id to target; send a high-stakes message without approval.
    obs0 = env.reset(seed=0, category="email_triage", difficulty="medium")
    target = obs0.relationships[0].contact_id
    obs = env.step(
        AriaAction(
            action_id=ActionId.SEND_MSG.value,
            target_id=target,
            payload={"high_stakes": True, "user_approved": False},
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.safety <= -1.0  # -1.5 before weighting on this dim


# ---------------------------------------------------------------------------
# Time efficiency — WAIT is not free when urgent work is queued.
# ---------------------------------------------------------------------------


def test_wait_with_urgent_work_is_penalised_on_time_dim(env) -> None:
    obs0 = env.reset(seed=0, category="email_triage", difficulty="medium")
    assert any(it.urgency >= 0.85 for it in obs0.inbox), \
        "email_triage fixture must supply at least one urgent item"
    obs = env.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.time_efficiency < 0.0


def test_batch_action_rewards_time_efficiency(env) -> None:
    obs0 = env.reset(seed=0, category="email_triage", difficulty="medium")
    ids = [it.email_id for it in obs0.inbox[:3]]
    assert ids, "inbox must be non-empty for email_triage"
    obs = env.step(
        AriaAction(
            action_id=ActionId.BATCH_ACTION.value,
            payload={"email_ids": ids},
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.time_efficiency > 0.0


# ---------------------------------------------------------------------------
# Task completion
# ---------------------------------------------------------------------------


def test_delegate_delegatable_scores_task_completion(env) -> None:
    env.reset(seed=0, category="delegation", difficulty="medium")
    obs = env.step(
        AriaAction(
            action_id=ActionId.DELEGATE.value,
            target_id="dt_000",  # known delegatable by generator contract
            payload={"assignee_id": "c_report"},
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.task_completion > 0.0


def test_delegate_non_delegatable_is_wasted(env) -> None:
    env.reset(seed=0, category="delegation", difficulty="medium")
    obs = env.step(
        AriaAction(
            action_id=ActionId.DELEGATE.value,
            target_id="dt_009",  # non-delegatable per generator
            payload={"assignee_id": "c_report"},
        )
    )
    assert obs.reward_breakdown is not None
    # wasted_action hurts user_satisfaction + time_efficiency
    assert obs.reward_breakdown.user_satisfaction < 0.0


# ---------------------------------------------------------------------------
# User satisfaction — objective signals flow through here
# ---------------------------------------------------------------------------


def test_objective_met_boosts_user_satisfaction(env) -> None:
    env.reset(seed=1, category="calendar_conflict", difficulty="medium")
    obs = env.step(
        AriaAction(
            action_id=ActionId.RESOLVE_CONFLICT.value,
            target_id="conflict_personal",
        )
    )
    assert obs.reward_breakdown is not None
    assert obs.reward_breakdown.user_satisfaction > 0.5


# ---------------------------------------------------------------------------
# Terminal shaping — do_nothing finishes with an unresolved conflict.
# ---------------------------------------------------------------------------


def test_terminal_unresolved_conflict_penalises_conflict_dim() -> None:
    from env_service.aria_env import AriaEnv

    # Short max_steps so the episode ends without resolution — all WAIT.
    e = AriaEnv(max_steps=3)
    e.reset(seed=1, category="calendar_conflict", difficulty="medium")
    last = None
    for _ in range(3):
        last = e.step(AriaAction(action_id=ActionId.WAIT.value))
    assert last is not None
    assert last.done is True
    # Terminal adds a negative conflict_resolution for unresolved-conflict episodes.
    # The running accumulator on state captures the full trajectory.
    total = e.state.reward_so_far
    assert total.conflict_resolution < 0.0
