"""RelationshipModel — tone calibration and post-interaction updates.

Extracted from `env_service.actions` so the logic has a single home, is
unit-testable in isolation, and is easy to swap for a learned model later.

The model is pure state-manipulation over `RelationshipNode` instances —
no I/O, no randomness. The env holds the nodes; this class just mutates them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aria_contracts import ActionId, RelationshipNode


# =============================================================================
# Tone calibration
# =============================================================================


@dataclass(slots=True, frozen=True)
class ToneConfig:
    """What the tone-calibration layer emits to the response generator.

    Consumers read `tone` for the primary channel. `formality`, `warmth`,
    `brevity` are useful when the response generator wants to blend cues.
    """

    tone: str              # "formal" | "casual" | "warm" | "direct"
    formality: float       # 0 = very casual, 1 = very formal
    warmth: float          # 0 = cold/transactional, 1 = affectionate
    brevity: float         # 0 = expansive, 1 = terse
    use_first_name: bool
    reason: str            # why this tone was chosen (for explainability)


_TONE_FORMALITY: dict[str, float] = {
    "formal": 0.9, "casual": 0.35, "warm": 0.4, "direct": 0.55,
}
_TONE_WARMTH: dict[str, float] = {
    "formal": 0.25, "casual": 0.55, "warm": 0.9, "direct": 0.35,
}
_TONE_BREVITY: dict[str, float] = {
    "formal": 0.4, "casual": 0.45, "warm": 0.35, "direct": 0.8,
}


class RelationshipModel:
    """Compute per-contact tone and update relationship state after actions."""

    # ------------------------------------------------------------------ tone

    def get_tone(self, contact: RelationshipNode) -> ToneConfig:
        """Pick a tone for this contact using their preference + current state.

        Rules:
          - Start from the contact's declared `tone_preference`.
          - If the relationship is in decline (low closeness AND long neglect),
            shift one notch toward `warm` to repair.
          - If contact is visibly unhappy (current_mood < -0.3), soften:
            any "direct" becomes "warm"; "formal" stays formal but higher warmth.
          - High-trust + family/partner → always prefer first-name.
        """
        base = contact.tone_preference
        tone = base
        reason = f"preference={base}"

        if contact.closeness < 0.5 and contact.last_contact_hours > 72:
            tone = "warm"
            reason = "neglected → repair with warmth"

        mood = contact.current_mood
        if mood is not None and mood < -0.3 and tone == "direct":
            tone = "warm"
            reason = "mood<-0.3 → soften from direct to warm"

        formality = _TONE_FORMALITY[tone]
        warmth = _TONE_WARMTH[tone]
        brevity = _TONE_BREVITY[tone]

        # Mood nudge (inside tone envelope)
        if mood is not None:
            warmth = _clamp(warmth + 0.15 * max(0.0, -mood), 0.0, 1.0)

        use_first_name = (
            contact.trust >= 0.8
            and contact.relationship_kind in ("partner", "family", "friend")
        )

        return ToneConfig(
            tone=tone,
            formality=formality,
            warmth=warmth,
            brevity=brevity,
            use_first_name=use_first_name,
            reason=reason,
        )

    # ----------------------------------------------------- post-interaction

    def update_after_interaction(
        self,
        contact: RelationshipNode,
        *,
        action_id: int,
        outcome: dict[str, Any],
    ) -> dict[str, float]:
        """Apply relationship deltas based on an action outcome.

        Mutates `contact` in place. Returns the deltas applied, for the
        reward function to consume.
        """
        d_closeness = 0.0
        d_trust = 0.0
        tone_mismatch = bool(outcome.get("tone_mismatch"))

        # Timely response to an urgent message from this contact.
        if action_id == ActionId.DRAFT_REPLY.value and outcome.get("success"):
            d_closeness += 0.10
            d_trust += 0.02
            contact.last_contact_hours = 0.0

        # Successful conflict resolution that preserved this contact's slot.
        if action_id == ActionId.RESOLVE_CONFLICT.value and outcome.get("success"):
            d_closeness += 0.30
            d_trust += 0.05

        # Cancel without alternative on a high-closeness event.
        if (
            action_id == ActionId.CANCEL.value
            and outcome.get("affected_high_closeness")
            and not outcome.get("proposed_alternative")
        ):
            d_closeness -= 0.25
            d_trust -= 0.03

        # Proposing an alternative is relationship-preserving.
        if action_id == ActionId.PROPOSE_ALTERNATIVE.value and outcome.get("success"):
            d_closeness += 0.04

        # Wrong tone detected anywhere → relationship hurt.
        if tone_mismatch:
            d_closeness -= 0.20
            d_trust -= 0.02

        # Neglect: detected upstream (env passes neglect count in outcome).
        neglect = int(outcome.get("neglected_close_urgent_count", 0))
        if neglect > 0:
            d_closeness -= 0.15 * min(3, neglect)

        # Clamp the mutation.
        contact.closeness = _clamp(contact.closeness + d_closeness, 0.0, 1.0)
        contact.trust = _clamp(contact.trust + d_trust, 0.0, 1.0)

        # Short bounded history.
        if contact.communication_history is not None:
            contact.communication_history.append(
                {
                    "action_id": action_id,
                    "closeness_delta": d_closeness,
                    "trust_delta": d_trust,
                    "success": bool(outcome.get("success")),
                }
            )
            # keep last 20
            if len(contact.communication_history) > 20:
                contact.communication_history = contact.communication_history[-20:]

        return {"closeness_delta": d_closeness, "trust_delta": d_trust}


# =============================================================================
# helpers
# =============================================================================


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


__all__ = ["RelationshipModel", "ToneConfig"]
