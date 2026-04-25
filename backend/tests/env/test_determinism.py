"""Determinism — same (category, difficulty, seed) yields byte-identical observations.

This is the load-bearing claim behind every graded benchmark: a judge on a
different machine must see the same initial world and the same trajectory
under the same actions.
"""
from __future__ import annotations

import pytest
from aria_contracts import ActionId, AriaAction
from aria_scenarios import CATEGORIES, DIFFICULTIES


def _fresh_env():
    from env_service.aria_env import AriaEnv

    return AriaEnv()


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_reset_is_deterministic(category: str, difficulty: str) -> None:
    e1 = _fresh_env()
    e2 = _fresh_env()
    o1 = e1.reset(seed=123, category=category, difficulty=difficulty)
    o2 = e2.reset(seed=123, category=category, difficulty=difficulty)
    assert o1.model_dump() == o2.model_dump()


def test_different_seeds_give_different_observations() -> None:
    e = _fresh_env()
    o1 = e.reset(seed=1, category="email_triage", difficulty="medium")
    o2 = e.reset(seed=2, category="email_triage", difficulty="medium")
    # Inboxes should differ — senders, urgencies, subjects are seed-driven.
    assert [it.email_id for it in o1.inbox] != [it.email_id for it in o2.inbox] or \
        [it.urgency for it in o1.inbox] != [it.urgency for it in o2.inbox]


def test_identical_trajectories_give_identical_rewards() -> None:
    e1 = _fresh_env()
    e2 = _fresh_env()
    e1.reset(seed=7, category="calendar_conflict", difficulty="medium")
    e2.reset(seed=7, category="calendar_conflict", difficulty="medium")
    actions = [
        AriaAction(action_id=ActionId.WAIT.value),
        AriaAction(action_id=ActionId.WAIT.value),
        AriaAction(
            action_id=ActionId.RESOLVE_CONFLICT.value,
            target_id="conflict_personal",
        ),
    ]
    for a in actions:
        r1 = e1.step(a).reward_breakdown.model_dump()  # type: ignore[union-attr]
        r2 = e2.step(a).reward_breakdown.model_dump()  # type: ignore[union-attr]
        assert r1 == r2


def test_state_hidden_is_deterministic() -> None:
    e1 = _fresh_env()
    e2 = _fresh_env()
    e1.reset(seed=9, category="shopping", difficulty="medium")
    e2.reset(seed=9, category="shopping", difficulty="medium")
    h1 = e1.state.hidden
    h2 = e2.state.hidden
    assert h1["objectives"] == h2["objectives"]
    assert h1["terminal_state_preview"] == h2["terminal_state_preview"]
