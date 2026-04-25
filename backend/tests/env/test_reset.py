"""Reset contract — every (category, difficulty) returns a valid observation."""
from __future__ import annotations

import pytest
from aria_contracts import AriaObservation
from aria_scenarios import CATEGORIES, DIFFICULTIES


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_reset_returns_observation(env, category: str, difficulty: str) -> None:
    obs = env.reset(seed=0, category=category, difficulty=difficulty)
    assert isinstance(obs, AriaObservation)
    assert obs.scenario_category == category
    assert obs.difficulty == difficulty
    assert obs.step_count == 0
    assert obs.max_steps > 0
    assert obs.done is False
    assert len(obs.preferences) == 64
    # calendar/inbox/relationships/tasks may or may not be empty depending on
    # scenario, but should always be lists.
    assert isinstance(obs.calendar, list)
    assert isinstance(obs.inbox, list)
    assert isinstance(obs.relationships, list)
    assert isinstance(obs.pending_tasks, list)


def test_reset_defaults_pick_category_from_seed(env) -> None:
    # Without an explicit category the env cycles deterministically through
    # CATEGORIES — so successive resets still cover the surface.
    categories = {env.reset(seed=s).scenario_category for s in range(len(CATEGORIES))}
    assert categories == set(CATEGORIES)


def test_reset_rejects_unknown_category(env) -> None:
    with pytest.raises(ValueError, match="category"):
        env.reset(seed=0, category="not_a_real_category")


def test_reset_rejects_unknown_difficulty(env) -> None:
    with pytest.raises(ValueError, match="difficulty"):
        env.reset(seed=0, difficulty="impossible")


def test_reset_accepts_none_seed(env) -> None:
    obs = env.reset()  # no seed, no category
    assert obs.step_count == 0
    assert obs.scenario_category in CATEGORIES


def test_calendar_conflict_has_day0_overlap(env) -> None:
    # Scenario invariant from README: at least 2 overlapping events on day 0.
    obs = env.reset(seed=42, category="calendar_conflict", difficulty="medium")
    day0 = [e for e in obs.calendar if e.day_offset == 0]
    assert len(day0) >= 2
    overlaps = 0
    for i, a in enumerate(day0):
        for b in day0[i + 1:]:
            if a.start_hour < b.end_hour and b.start_hour < a.end_hour:
                overlaps += 1
    assert overlaps >= 1


def test_email_triage_has_urgent_and_nonurgent(env) -> None:
    obs = env.reset(seed=1, category="email_triage", difficulty="medium")
    assert any(it.urgency >= 0.85 for it in obs.inbox)
    assert any(it.urgency < 0.5 for it in obs.inbox)


def test_reset_is_idempotent_on_env_instance(env) -> None:
    # Calling reset twice with the same args should give identical public
    # observation shape — no state leak between episodes.
    o1 = env.reset(seed=5, category="email_triage", difficulty="medium")
    o2 = env.reset(seed=5, category="email_triage", difficulty="medium")
    assert o1.model_dump() == o2.model_dump()


def test_state_not_accessible_before_reset() -> None:
    from env_service.aria_env import AriaEnv

    fresh = AriaEnv()
    with pytest.raises(RuntimeError):
        _ = fresh.state


def test_state_exposes_hidden_objectives(env) -> None:
    env.reset(seed=7, category="calendar_conflict", difficulty="hard")
    st = env.state
    assert st.scenario_category == "calendar_conflict"
    assert st.difficulty == "hard"
    assert "objectives" in st.hidden
    assert isinstance(st.hidden["objectives"], list)
    assert st.hidden["objectives"]  # hard produces at least one objective
