"""Step contract — every action id dispatches, reward is set, step_count advances."""
from __future__ import annotations

import pytest
from aria_contracts import ActionId, AriaAction, NUM_ACTIONS


def test_step_before_reset_raises() -> None:
    from env_service.aria_env import AriaEnv

    e = AriaEnv()
    with pytest.raises(RuntimeError, match="reset"):
        e.step(AriaAction(action_id=ActionId.WAIT.value))


def test_step_advances_step_count(env) -> None:
    env.reset(seed=0, category="email_triage", difficulty="medium")
    obs = env.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs.step_count == 1
    obs = env.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs.step_count == 2


def test_step_sets_reward_breakdown(env) -> None:
    env.reset(seed=0, category="email_triage", difficulty="medium")
    obs = env.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs.reward_breakdown is not None
    # total should equal the weighted sum of the per-dim values
    computed = obs.reward_breakdown.compute_total()
    assert abs(obs.reward_breakdown.total - computed) < 1e-9
    # obs.reward mirrors the breakdown total (set by env)
    assert obs.reward is not None
    assert abs(obs.reward - obs.reward_breakdown.total) < 1e-9


def test_step_advances_time(env) -> None:
    obs0 = env.reset(seed=0, category="email_triage", difficulty="medium")
    t0 = obs0.time
    # WAIT costs 0.5h (largest per TIME_COST)
    obs1 = env.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs1.time > t0


@pytest.mark.parametrize("action_id", list(range(NUM_ACTIONS)))
def test_every_action_dispatches_without_crashing(env, action_id: int) -> None:
    """Each of the 15 actions must handle missing-target / empty-payload gracefully."""
    env.reset(seed=0, category="email_triage", difficulty="medium")
    obs = env.step(AriaAction(action_id=action_id))
    # even when the action fails, the env must still produce a valid reward.
    assert obs.reward_breakdown is not None
    assert obs.step_count == 1
    assert isinstance(obs.done, bool)


def test_episode_terminates_when_all_objectives_met(env) -> None:
    # Running the scripted expert against calendar_conflict/medium should
    # resolve the primary conflict in one step and hit done=True.
    obs = env.reset(seed=1, category="calendar_conflict", difficulty="medium")
    # Find the conflict target exposed via state.hidden:
    meta = env.state.hidden["objectives"]
    assert any(o["kind"] == "resolve_day0_conflict" for o in meta)
    obs = env.step(
        AriaAction(
            action_id=ActionId.RESOLVE_CONFLICT.value,
            target_id="conflict_personal",
        )
    )
    assert obs.done is True
    # Terminal reward must be set with a signed total.
    assert obs.reward_breakdown is not None
    assert obs.reward is not None


def test_episode_terminates_at_max_steps() -> None:
    """If no objective is hit, the episode still ends at max_steps."""
    from env_service.aria_env import AriaEnv

    e = AriaEnv(max_steps=3)
    e.reset(seed=0, category="email_triage", difficulty="easy")
    for _ in range(2):
        obs = e.step(AriaAction(action_id=ActionId.WAIT.value))
        assert obs.done is False
    obs = e.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs.done is True
    assert obs.step_count == 3


def test_unknown_action_id_rejected_by_contract() -> None:
    # Action contract clamps to [0, NUM_ACTIONS-1]; a payload with 99 is invalid
    with pytest.raises(Exception):
        AriaAction(action_id=99)


def test_step_preserves_scenario_metadata(env) -> None:
    env.reset(seed=0, category="delegation", difficulty="hard")
    obs = env.step(AriaAction(action_id=ActionId.WAIT.value))
    assert obs.scenario_category == "delegation"
    assert obs.difficulty == "hard"
    assert obs.max_steps > 0


def test_state_reward_so_far_accumulates(env) -> None:
    env.reset(seed=0, category="email_triage", difficulty="medium")
    assert env.state.reward_so_far.total == 0.0
    env.step(AriaAction(action_id=ActionId.WAIT.value))
    env.step(AriaAction(action_id=ActionId.WAIT.value))
    # Two waits with urgent items queued should compound in some direction.
    # We don't pin the sign — just that it moved off zero.
    assert env.state.reward_so_far != env.state.reward_so_far.__class__.zero()
