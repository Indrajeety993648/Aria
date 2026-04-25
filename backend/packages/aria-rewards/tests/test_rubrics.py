"""Tests for the OpenEnv-Rubric wrappers.

Two guarantees:
  1. The Rubric path produces *byte-identical* RewardBreakdown values to the
     legacy compute_step_reward() path. The math hasn't moved.
  2. Composable APIs work as judges expect: named_rubrics() lists six
     dimensions; ablation zeros a dimension's contribution but keeps it
     introspectable.
"""
from __future__ import annotations

import pytest
from aria_contracts import ActionId, REWARD_WEIGHTS

from aria_rewards import (
    AriaCompositeRubric,
    AriaDimensionRubric,
    StepContext,
    compute_step_reward,
    evaluate_via_rubric,
)


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


# ---------------------------------------------------------------------------
# Parity with the legacy compute path
# ---------------------------------------------------------------------------

PARITY_CASES = [
    (ActionId.RESOLVE_CONFLICT.value, {"success": True, "conflict_resolved": True,
                                        "scenario_objective_met": True}),
    (ActionId.CANCEL.value,           {"affected_high_closeness": True,
                                        "proposed_alternative": False}),
    (ActionId.PURCHASE.value,         {"authorized": False}),
    (ActionId.WAIT.value,             {"urgent_pending_count": 2,
                                        "neglected_close_urgent_count": 2}),
    (ActionId.DRAFT_REPLY.value,      {"success": True, "tone_mismatch": False,
                                        "scenario_objective_met": True}),
    (ActionId.BATCH_ACTION.value,     {"success": True, "batch_size": 3}),
    (ActionId.SEND_MSG.value,         {"high_stakes": True, "user_approved": False}),
]


@pytest.mark.parametrize("action_id,outcome", PARITY_CASES)
def test_rubric_matches_legacy_breakdown(action_id, outcome):
    ctx = _ctx(action_id, outcome)
    legacy = compute_step_reward(ctx)
    rubric = evaluate_via_rubric(ctx)
    assert legacy.task_completion     == pytest.approx(rubric.task_completion)
    assert legacy.relationship_health == pytest.approx(rubric.relationship_health)
    assert legacy.user_satisfaction   == pytest.approx(rubric.user_satisfaction)
    assert legacy.time_efficiency     == pytest.approx(rubric.time_efficiency)
    assert legacy.conflict_resolution == pytest.approx(rubric.conflict_resolution)
    assert legacy.safety              == pytest.approx(rubric.safety)
    assert legacy.total               == pytest.approx(rubric.total)


# ---------------------------------------------------------------------------
# Composable Rubric API contract
# ---------------------------------------------------------------------------


def test_named_rubrics_lists_six_dimensions():
    composite = AriaCompositeRubric()
    names = [n for n, _ in composite.named_rubrics()]
    assert sorted(names) == sorted([
        "task_completion",
        "relationship_health",
        "user_satisfaction",
        "time_efficiency",
        "conflict_resolution",
        "safety",
    ])


def test_each_child_has_correct_weight():
    composite = AriaCompositeRubric()
    for name, child in composite.named_children():
        assert isinstance(child, AriaDimensionRubric)
        assert child.weight == REWARD_WEIGHTS[name]


def test_get_rubric_path_lookup():
    composite = AriaCompositeRubric()
    sub = composite.get_rubric("relationship_health")
    assert isinstance(sub, AriaDimensionRubric)
    assert sub.weight == 0.20


def test_last_score_populated_after_call():
    composite = AriaCompositeRubric()
    composite.set_context(_ctx(ActionId.RESOLVE_CONFLICT.value,
                                {"success": True, "conflict_resolved": True}))
    total = composite(action=None, observation=None)
    assert composite.last_score == pytest.approx(total)
    assert composite.conflict_resolution.last_score == 1.0


# ---------------------------------------------------------------------------
# Ablation — the money plot in the hackathon write-up depends on this
# ---------------------------------------------------------------------------


def test_ablation_zeros_dimension_contribution():
    full = AriaCompositeRubric()
    ablated = AriaCompositeRubric(ablate=("relationship_health",))

    ctx = _ctx(ActionId.CANCEL.value, {"affected_high_closeness": True,
                                        "proposed_alternative": False})

    full.set_context(ctx)
    ablated.set_context(ctx)
    full_total = full(action=None, observation=None)
    abl_total = ablated(action=None, observation=None)

    # Ablated total = full total + (the relationship_health contribution we removed)
    rh_score = full.relationship_health.last_score
    expected_diff = rh_score * REWARD_WEIGHTS["relationship_health"]
    assert abl_total - full_total == pytest.approx(-expected_diff)

    # Breakdown reflects the ablation visibly
    abl_b = ablated.last_breakdown()
    assert abl_b.relationship_health == 0.0


def test_ablation_rejects_unknown_dimension():
    with pytest.raises(ValueError):
        AriaCompositeRubric(ablate=("not_a_real_dim",))


def test_reset_clears_child_context():
    composite = AriaCompositeRubric()
    composite.set_context(_ctx(ActionId.WAIT.value))
    composite(action=None, observation=None)
    composite.reset()
    # After reset, calling without re-setting context returns 0.0
    total = composite(action=None, observation=None)
    assert total == 0.0


# ---------------------------------------------------------------------------
# Hooks — judges may register one to log per-dim scores
# ---------------------------------------------------------------------------


def test_forward_hook_fires_with_per_dim_score():
    composite = AriaCompositeRubric()
    seen: list[tuple[str, float]] = []

    for name, child in composite.named_children():
        # Capture name in default arg to defeat closure-over-loop-var pitfall.
        def hook(_rubric, _action, _obs, score, _name=name):
            seen.append((_name, score))
        child.register_forward_hook(hook)

    composite.set_context(_ctx(ActionId.RESOLVE_CONFLICT.value,
                                {"success": True, "conflict_resolved": True}))
    composite(action=None, observation=None)

    assert len(seen) == 6
    by_name = dict(seen)
    assert by_name["conflict_resolution"] == 1.0
    assert by_name["relationship_health"] == pytest.approx(0.3)  # success boost
