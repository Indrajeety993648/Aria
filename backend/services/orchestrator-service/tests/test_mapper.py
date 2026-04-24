"""Tests for the rule-based intent mapper.

Covers every ActionId in the 15-action enum with at least one canonical
utterance, plus some edge cases (fallback to WAIT, target-id extraction,
priority tie-breakers).
"""
from __future__ import annotations

import pytest

from aria_contracts import ActionId, AriaAction
from orchestrator_service.mapper import text_to_action


# One canonical utterance per action. Each pair must map unambiguously.
CASES: list[tuple[str, ActionId]] = [
    ("send message to Bob about the demo", ActionId.SEND_MSG),
    ("schedule a sync with Alice on Friday", ActionId.SCHEDULE),
    ("reschedule my 3pm to Thursday", ActionId.RESCHEDULE),
    ("cancel the standup", ActionId.CANCEL),
    ("delegate to Priya this TPS report", ActionId.DELEGATE),
    ("reply to the CTO email", ActionId.DRAFT_REPLY),
    ("remind me to follow up tomorrow", ActionId.SET_REMINDER),
    ("buy a birthday card", ActionId.PURCHASE),
    ("resolve conflict on my calendar", ActionId.RESOLVE_CONFLICT),
    ("ask me before you move anything", ActionId.ASK_USER),
    ("decline the all-hands invite", ActionId.DECLINE_INVITE),
    ("propose alternative meeting time", ActionId.PROPOSE_ALTERNATIVE),
    ("batch process my inbox", ActionId.BATCH_ACTION),
    ("wait, do nothing yet", ActionId.WAIT),
    ("escalate to my manager", ActionId.ESCALATE),
]


@pytest.mark.parametrize("text,expected", CASES, ids=[e[1].name for e in CASES])
def test_canonical_utterance_maps_to_expected_action(
    text: str, expected: ActionId
) -> None:
    action = text_to_action(text)
    assert isinstance(action, AriaAction)
    assert action.action_id == int(expected), (
        f"Expected {expected.name} but got "
        f"{ActionId(action.action_id).name} for text: {text!r}"
    )


def test_all_15_action_ids_have_coverage() -> None:
    """Guard against someone adding an ActionId without a test case."""
    tested = {exp for _, exp in CASES}
    all_ids = set(ActionId)
    assert tested == all_ids, f"missing coverage for: {all_ids - tested}"


def test_empty_text_falls_back_to_wait() -> None:
    assert text_to_action("").action_id == int(ActionId.WAIT)


def test_nonsense_text_falls_back_to_wait() -> None:
    assert text_to_action("asdlkfjasdlkfj qwerty").action_id == int(ActionId.WAIT)


def test_reschedule_beats_schedule() -> None:
    """Priority table sanity: 'reschedule' must not fall through to SCHEDULE."""
    action = text_to_action("reschedule the meeting to next week")
    assert action.action_id == int(ActionId.RESCHEDULE)


def test_target_id_extraction() -> None:
    """IDs shaped like event_123 or email_7 should be captured."""
    a = text_to_action("reply to email_7 from Dana")
    assert a.action_id == int(ActionId.DRAFT_REPLY)
    assert a.target_id == "email_7"


def test_payload_carries_original_user_text() -> None:
    a = text_to_action("buy a gift card")
    assert a.payload.get("user_text") == "buy a gift card"


def test_case_insensitive() -> None:
    a = text_to_action("RESCHEDULE my 3PM")
    assert a.action_id == int(ActionId.RESCHEDULE)


def test_session_observation_hint_recorded() -> None:
    a = text_to_action("reply to that email", session_observation={"inbox": []})
    assert a.payload.get("has_observation") is True
