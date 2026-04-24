"""Action validation / permission gate for the product runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aria_contracts import ActionId, AriaAction


@dataclass(slots=True)
class ValidationResult:
    allowed: bool
    reason: str | None = None
    suggested_action: AriaAction | None = None


def _ask_user(reason: str, original: AriaAction) -> AriaAction:
    payload: dict[str, Any] = dict(original.payload)
    payload.update({"validation_reason": reason, "original_action": original.model_dump()})
    return AriaAction(action_id=int(ActionId.ASK_USER), target_id=None, payload=payload)


class ActionValidator:
    """Explicit gate for safety/permissions.

    This is intentionally conservative and policy-agnostic. If a required
    permission is missing, we downshift to ASK_USER rather than fail.
    """

    def validate(
        self, action: AriaAction, observation: dict[str, Any] | None = None
    ) -> ValidationResult:
        _ = observation  # reserved for future policy checks

        if action.action_id == ActionId.PURCHASE.value:
            if not action.payload.get("user_approved", False):
                reason = "purchase_requires_user_approval"
                return ValidationResult(
                    allowed=False,
                    reason=reason,
                    suggested_action=_ask_user(reason, action),
                )

        if action.action_id == ActionId.SEND_MSG.value:
            if action.payload.get("high_stakes", False) and not action.payload.get(
                "user_approved", False
            ):
                reason = "high_stakes_message_requires_approval"
                return ValidationResult(
                    allowed=False,
                    reason=reason,
                    suggested_action=_ask_user(reason, action),
                )

        return ValidationResult(allowed=True)


__all__ = ["ActionValidator", "ValidationResult"]
