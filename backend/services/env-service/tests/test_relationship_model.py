"""Unit tests for RelationshipModel — tone calibration + post-interaction updates."""
from __future__ import annotations

from aria_contracts import ActionId, RelationshipNode

from env_service.relationship_model import RelationshipModel, ToneConfig


def _contact(**overrides) -> RelationshipNode:
    base: dict = dict(
        contact_id="c_x",
        name="Test",
        relationship_kind="friend",
        closeness=0.7,
        trust=0.8,
        last_contact_hours=4.0,
        tone_preference="casual",
    )
    base.update(overrides)
    return RelationshipNode(**base)


# ---------------------------------------------------------------------------
# get_tone
# ---------------------------------------------------------------------------


def test_get_tone_defaults_to_preference():
    m = RelationshipModel()
    c = _contact(tone_preference="formal", relationship_kind="boss")
    t = m.get_tone(c)
    assert t.tone == "formal"
    assert t.formality > t.brevity or t.formality > 0.5


def test_get_tone_switches_to_warm_on_neglect():
    m = RelationshipModel()
    c = _contact(
        tone_preference="direct",
        closeness=0.3,
        last_contact_hours=96.0,
    )
    t = m.get_tone(c)
    assert t.tone == "warm"
    assert "neglected" in t.reason


def test_get_tone_softens_when_mood_bad():
    m = RelationshipModel()
    c = _contact(tone_preference="direct", current_mood=-0.5)
    t = m.get_tone(c)
    assert t.tone == "warm"


def test_get_tone_first_name_for_high_trust_intimates():
    m = RelationshipModel()
    partner = _contact(relationship_kind="partner", trust=0.95, tone_preference="warm")
    vendor = _contact(relationship_kind="vendor", trust=0.95, tone_preference="formal")
    assert m.get_tone(partner).use_first_name is True
    assert m.get_tone(vendor).use_first_name is False


def test_get_tone_returns_tone_config_type():
    t = RelationshipModel().get_tone(_contact())
    assert isinstance(t, ToneConfig)


# ---------------------------------------------------------------------------
# update_after_interaction
# ---------------------------------------------------------------------------


def test_timely_reply_raises_closeness():
    m = RelationshipModel()
    c = _contact(closeness=0.5, last_contact_hours=24.0)
    d = m.update_after_interaction(
        c, action_id=ActionId.DRAFT_REPLY.value, outcome={"success": True},
    )
    assert d["closeness_delta"] > 0
    assert c.closeness > 0.5
    assert c.last_contact_hours == 0.0


def test_cancel_high_closeness_without_alt_hurts():
    m = RelationshipModel()
    c = _contact(closeness=0.9)
    d = m.update_after_interaction(
        c,
        action_id=ActionId.CANCEL.value,
        outcome={"affected_high_closeness": True, "proposed_alternative": False},
    )
    assert d["closeness_delta"] < 0
    assert c.closeness < 0.9


def test_cancel_with_alternative_neutral():
    m = RelationshipModel()
    c = _contact(closeness=0.9)
    d = m.update_after_interaction(
        c,
        action_id=ActionId.CANCEL.value,
        outcome={"affected_high_closeness": True, "proposed_alternative": True},
    )
    assert d["closeness_delta"] == 0


def test_successful_resolve_conflict_boosts():
    m = RelationshipModel()
    c = _contact(closeness=0.5)
    m.update_after_interaction(
        c, action_id=ActionId.RESOLVE_CONFLICT.value, outcome={"success": True}
    )
    assert c.closeness > 0.7


def test_tone_mismatch_penalizes_both():
    m = RelationshipModel()
    c = _contact(closeness=0.6, trust=0.7)
    m.update_after_interaction(
        c, action_id=ActionId.SEND_MSG.value, outcome={"tone_mismatch": True},
    )
    assert c.closeness < 0.6
    assert c.trust < 0.7


def test_communication_history_appends_when_enabled():
    m = RelationshipModel()
    c = _contact(communication_history=[])
    m.update_after_interaction(
        c, action_id=ActionId.DRAFT_REPLY.value, outcome={"success": True}
    )
    assert c.communication_history is not None
    assert len(c.communication_history) == 1
    assert c.communication_history[0]["success"] is True


def test_clamps_closeness_to_unit_interval():
    m = RelationshipModel()
    c = _contact(closeness=0.98)
    # Many boosts shouldn't push closeness past 1.0
    for _ in range(20):
        m.update_after_interaction(
            c, action_id=ActionId.RESOLVE_CONFLICT.value, outcome={"success": True}
        )
    assert 0.0 <= c.closeness <= 1.0
