"""Tests for decision engine policy mode and action validation."""
from __future__ import annotations

from aria_contracts import ActionId, AriaAction
from orchestrator_service.action_validator import ActionValidator
from orchestrator_service.decision_engine import DecisionEngine


def test_action_validator_requires_purchase_approval() -> None:
    validator = ActionValidator()
    action = AriaAction(action_id=int(ActionId.PURCHASE), payload={"amount": 20.0})

    result = validator.validate(action)

    assert result.allowed is False
    assert result.reason == "purchase_requires_user_approval"
    assert result.suggested_action is not None
    assert result.suggested_action.action_id == int(ActionId.ASK_USER)


def test_decision_engine_policy_mode_uses_heuristic() -> None:
    engine = DecisionEngine(policy_mode="policy")
    observation = {
        "inbox": [
            {
                "email_id": "email_1",
                "urgency": 0.95,
            }
        ]
    }

    action = engine.decide("handle my inbox", observation)

    assert action.action_id == int(ActionId.DRAFT_REPLY)
    assert action.target_id == "email_1"


def test_decision_engine_rule_mode_fallback() -> None:
    engine = DecisionEngine(policy_mode="rule")
    action = engine.decide("schedule a meeting next week", None)

    assert action.action_id == int(ActionId.SCHEDULE)
