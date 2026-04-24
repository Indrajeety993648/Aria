"""Scenario generator invariants & determinism."""
from __future__ import annotations

import hashlib
import json

import pytest

from aria_scenarios import CATEGORIES, DIFFICULTIES, generate
from aria_scenarios.spec import ScenarioSpec


def _hash_spec(spec: ScenarioSpec) -> str:
    """Stable hash of the user-facing fields of a spec."""
    payload = {
        "category": spec.category,
        "difficulty": spec.difficulty,
        "seed": spec.seed,
        "initial_time": spec.initial_time,
        "calendar": [e.model_dump() for e in spec.calendar],
        "inbox": [i.model_dump() for i in spec.inbox],
        "relationships": [r.model_dump() for r in spec.relationships],
        "pending_tasks": [t.model_dump() for t in spec.pending_tasks],
        "preferences": spec.preferences,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_generator_determinism(category, difficulty):
    a = generate(category, difficulty, seed=123)
    b = generate(category, difficulty, seed=123)
    assert _hash_spec(a) == _hash_spec(b)


@pytest.mark.parametrize("category", CATEGORIES)
def test_different_seeds_produce_different_scenarios(category):
    a = generate(category, "medium", seed=1)
    b = generate(category, "medium", seed=2)
    assert _hash_spec(a) != _hash_spec(b)


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_calendar_conflict_invariant(difficulty):
    """calendar_conflict must produce at least 2 overlapping events on day 0."""
    s = generate("calendar_conflict", difficulty, seed=7)
    day0 = [e for e in s.calendar if e.day_offset == 0]
    overlapping = [
        (a, b)
        for a in day0 for b in day0
        if a.event_id < b.event_id
        and a.start_hour < b.end_hour and b.start_hour < a.end_hour
    ]
    assert len(overlapping) >= 1


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_email_triage_invariant(difficulty):
    """email_triage must contain >= 2 urgent items and full inbox has mixed urgency."""
    s = generate("email_triage", difficulty, seed=11)
    urgent = [i for i in s.inbox if i.urgency >= 0.85]
    non_urgent = [i for i in s.inbox if i.urgency < 0.5]
    assert len(urgent) >= 2
    assert len(non_urgent) >= 1


def test_message_reply_has_loaded_contact():
    s = generate("message_reply", "medium", seed=3)
    loaded_ids = s.hidden["loaded_email_ids"]
    assert len(loaded_ids) >= 1
    for it in s.inbox:
        if it.email_id in loaded_ids:
            assert it.sentiment < 0  # loaded = upset


def test_dinner_planning_constraints_present():
    s = generate("dinner_planning", "hard", seed=5)
    hidden = s.hidden
    assert "dietary_restrictions" in hidden
    assert "time_windows" in hidden
    assert "budget_per_head_max" in hidden
    assert len(hidden["dinner_participants"]) >= 2


def test_delegation_has_delegatable_tasks():
    s = generate("delegation", "medium", seed=9)
    delegatable = [t for t in s.pending_tasks if t.delegatable]
    non_delegatable = [t for t in s.pending_tasks if not t.delegatable]
    assert len(delegatable) >= 1
    assert len(non_delegatable) >= 1


def test_shopping_has_budget():
    s = generate("shopping", "medium", seed=13)
    assert s.hidden["budget_limit"] > 0
    assert any(t.task_id == "buy_gift" for t in s.pending_tasks)


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_objectives_present(category, difficulty):
    s = generate(category, difficulty, seed=1)
    assert s.objectives_total() >= 1


@pytest.mark.parametrize("category", CATEGORIES)
def test_difficulty_increases_volume(category):
    easy = generate(category, "easy", seed=42)
    hard = generate(category, "hard", seed=42)
    # At least one of: more events, more inbox items, more tasks
    assert (
        len(hard.calendar) > len(easy.calendar)
        or len(hard.inbox) > len(easy.inbox)
        or len(hard.pending_tasks) > len(easy.pending_tasks)
    )


def test_registry_rejects_unknown_category():
    with pytest.raises(ValueError):
        generate("not_a_real_category", "easy", seed=1)  # type: ignore[arg-type]


def test_registry_rejects_unknown_difficulty():
    with pytest.raises(ValueError):
        generate("email_triage", "medium_rare", seed=1)  # type: ignore[arg-type]
