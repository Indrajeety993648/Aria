"""One module per scenario category. Each exposes `generate(difficulty, seed) -> ScenarioSpec`."""
from aria_scenarios.generators import (
    calendar_conflict,
    delegation,
    dinner_planning,
    email_triage,
    message_reply,
    shopping,
)

__all__ = [
    "calendar_conflict",
    "delegation",
    "dinner_planning",
    "email_triage",
    "message_reply",
    "shopping",
]
