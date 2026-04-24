"""Contract smoke tests — if any of these fail, every downstream service
is on the wrong version of the contract.
"""
from __future__ import annotations

import pytest

from aria_contracts import (
    REWARD_WEIGHTS,
    ActionId,
    AriaAction,
    AriaObservation,
    AriaState,
    CalendarEvent,
    GwAgentEvent,
    MemoryQuery,
    MemoryWrite,
    RelationshipNode,
    RewardBreakdown,
    ToolCall,
    VoiceTranscript,
)
from aria_contracts.env import NUM_ACTIONS


def test_action_ids_are_0_to_14():
    ids = [a.value for a in ActionId]
    assert ids == list(range(NUM_ACTIONS))
    assert NUM_ACTIONS == 15


def test_action_rejects_out_of_range():
    with pytest.raises(Exception):
        AriaAction(action_id=15)
    with pytest.raises(Exception):
        AriaAction(action_id=-1)


def test_action_accepts_all_valid_ids():
    for i in range(NUM_ACTIONS):
        a = AriaAction(action_id=i)
        assert a.action_id == i


def test_action_forbids_extra_fields():
    """extra='forbid' on Action base — if this breaks, OpenEnv changed its API."""
    with pytest.raises(Exception):
        AriaAction(action_id=0, bogus="x")


def test_reward_weights_sum_to_one():
    assert abs(sum(REWARD_WEIGHTS.values()) - 1.0) < 1e-9


def test_reward_breakdown_total_matches_formula():
    b = RewardBreakdown(
        task_completion=1.0,
        relationship_health=-0.5,
        user_satisfaction=0.8,
        time_efficiency=0.3,
        conflict_resolution=0.0,
        safety=-1.0,
    )
    expected = (
        0.25 * 1.0 + 0.20 * -0.5 + 0.20 * 0.8 + 0.15 * 0.3 + 0.15 * 0.0 + 0.05 * -1.0
    )
    assert abs(b.compute_total() - expected) < 1e-9


def test_reward_accumulate_is_elementwise_and_sums_total():
    a = RewardBreakdown(task_completion=0.5, safety=-0.3)
    b = RewardBreakdown(task_completion=0.2, safety=0.1)
    c = a.accumulate(b)
    assert c.task_completion == 0.7
    assert abs(c.safety - -0.2) < 1e-9
    assert abs(c.total - c.compute_total()) < 1e-9


def test_observation_preferences_length_enforced():
    # preferences must be length 64
    with pytest.raises(Exception):
        AriaObservation(time=0.0, preferences=[0.0] * 10)
    obs = AriaObservation(time=0.0)
    assert len(obs.preferences) == 64


def test_observation_inherits_done_and_reward():
    obs = AriaObservation(time=0.0, done=True, reward=1.5)
    assert obs.done is True
    assert obs.reward == 1.5


def test_calendar_event_bounds():
    with pytest.raises(Exception):
        CalendarEvent(
            event_id="e1",
            day_offset=30,  # out of range
            start_hour=10.0,
            end_hour=11.0,
            title="x",
            priority=0.5,
            flexibility=0.5,
        )


def test_relationship_closeness_bounds():
    with pytest.raises(Exception):
        RelationshipNode(
            contact_id="c1",
            name="X",
            relationship_kind="friend",
            closeness=1.5,  # >1
            last_contact_hours=1.0,
        )


def test_state_carries_reward_so_far():
    s = AriaState(
        scenario_category="email_triage",
        difficulty="easy",
        seed=42,
        reward_so_far=RewardBreakdown.zero(),
    )
    assert s.step_count == 0  # inherited from openenv State


def test_gateway_event_kinds_round_trip():
    ev = GwAgentEvent(
        session_id="s1", kind="reward", payload={"total": 0.4}, ts_ms=123
    )
    dumped = ev.model_dump_json()
    restored = GwAgentEvent.model_validate_json(dumped)
    assert restored == ev


def test_memory_query_requires_something_to_query():
    # pydantic itself doesn't enforce this — we keep both optional for flexibility
    # and let memory-service fall back to "most recent".
    q = MemoryQuery(namespace="episodic")
    assert q.top_k == 5


def test_tool_call_result_is_optional():
    tc = ToolCall(tool_name="send_email", arguments={"to": "a@b.com"})
    assert tc.result is None


def test_voice_transcript_round_trip():
    t = VoiceTranscript(
        session_id="s1",
        text="hello",
        intent_id=3,
        intent_confidence=0.7,
        intent_source="heuristic",
    )
    restored = VoiceTranscript.model_validate_json(t.model_dump_json())
    assert restored == t


def test_memory_write_shape():
    w = MemoryWrite(namespace="relationship", key="bob", content="likes coffee")
    assert w.embedding is None
