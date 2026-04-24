"""Tests for the state encoder."""
from __future__ import annotations

from orchestrator_service.state_encoder import StateEncoder


def test_state_encoder_empty() -> None:
    enc = StateEncoder()
    vec = enc.encode(None)
    assert len(vec) == 8
    assert all(v == 0.0 for v in vec)


def test_state_encoder_features() -> None:
    enc = StateEncoder()
    obs = {
        "inbox": [{"urgency": 0.9}, {"urgency": 0.1}],
        "calendar": [
            {"day_offset": 0, "start_hour": 9, "end_hour": 10},
            {"day_offset": 0, "start_hour": 9.5, "end_hour": 11},
        ],
        "pending_tasks": [
            {"status": "open", "priority": 0.8},
            {"status": "done", "priority": 0.2},
        ],
        "time": 12.5,
        "step_count": 3,
    }
    vec = enc.encode(obs)
    assert len(vec) == 8
    # inbox size, urgent count, calendar size, conflicts
    assert vec[0] == 2.0
    assert vec[1] == 1.0
    assert vec[2] == 2.0
    assert vec[3] == 1.0
    # open tasks, high priority
    assert vec[4] == 1.0
    assert vec[5] == 1.0
    assert vec[6] == 12.5
    assert vec[7] == 3.0
