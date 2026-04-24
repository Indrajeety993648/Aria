"""Tests for intent classification, entity extraction, and context resolution."""
from __future__ import annotations

from aria_contracts import ActionId
from orchestrator_service.context_resolver import ContextResolver
from orchestrator_service.decision_engine import DecisionEngine
from orchestrator_service.entity_extractor import EntityExtractor
from orchestrator_service.intent_classifier import IntentClassifier


def test_intent_classifier_reschedule() -> None:
    clf = IntentClassifier()
    result = clf.classify("reschedule my 3pm to Thursday")
    assert result.action_id == int(ActionId.RESCHEDULE)
    assert result.confidence > 0


def test_entity_extractor_target_id() -> None:
    ex = EntityExtractor()
    entities = ex.extract("reply to email_7 from Dana")
    assert entities.get("target_id") == "email_7"


def test_entity_extractor_time_hint() -> None:
    ex = EntityExtractor()
    entities = ex.extract("tomorrow at 3pm")
    assert "date_hint" in entities or "time_hint" in entities


def test_context_resolver_suggests_inbox() -> None:
    resolver = ContextResolver()
    obs = {"inbox": [{"email_id": "email_42", "urgency": 0.9}]}
    ctx = resolver.resolve("reply to that email", obs)
    assert ctx.get("suggested_target_id") == "email_42"


def test_decision_engine_uses_context_target() -> None:
    engine = DecisionEngine(policy_mode="rule")
    obs = {"inbox": [{"email_id": "email_99", "urgency": 0.9}]}
    action = engine.decide("reply to that email", obs)
    assert action.action_id == int(ActionId.DRAFT_REPLY)
    assert action.target_id == "email_99"
