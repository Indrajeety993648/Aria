"""Structural tests for the aria-personal-manager-v1 contract.

If any of these break, the env is no longer recognizable to a judge following
the README. They are intentionally free of fancy fixtures — each test reads
like a one-line claim about the published API.
"""
from __future__ import annotations

import pytest
from aria_contracts import (
    NUM_ACTIONS,
    ActionId,
    AriaAction,
    AriaObservation,
    RewardBreakdown,
)
from aria_contracts.reward import REWARD_WEIGHTS


def test_action_space_is_15_discrete() -> None:
    assert NUM_ACTIONS == 15
    assert len(ActionId) == 15
    assert {m.value for m in ActionId} == set(range(15))


def test_action_out_of_range_rejected() -> None:
    with pytest.raises(Exception):
        AriaAction(action_id=15)
    with pytest.raises(Exception):
        AriaAction(action_id=-1)


def test_reward_weights_sum_to_one() -> None:
    assert abs(sum(REWARD_WEIGHTS.values()) - 1.0) < 1e-9


def test_reward_weights_match_readme_spec() -> None:
    # README.md spec — must not drift silently.
    assert REWARD_WEIGHTS == {
        "task_completion":     0.25,
        "relationship_health": 0.20,
        "user_satisfaction":   0.20,
        "time_efficiency":     0.15,
        "conflict_resolution": 0.15,
        "safety":              0.05,
    }


def test_reward_breakdown_total_is_weighted_sum() -> None:
    b = RewardBreakdown(
        task_completion=1.0,
        relationship_health=1.0,
        user_satisfaction=1.0,
        time_efficiency=1.0,
        conflict_resolution=1.0,
        safety=1.0,
    )
    # sum of weights = 1.0
    assert abs(b.compute_total() - 1.0) < 1e-9


def test_metadata_names_env_as_published(env) -> None:
    meta = env.get_metadata()
    assert meta.name == "aria-personal-manager-v1"
    assert meta.version  # non-empty string
