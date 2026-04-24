"""Baseline policies for grading.

Three policies judges expect to see:
  - random_policy: uniformly samples an action id
  - do_nothing_policy: always WAIT
  - scripted_expert: hand-crafted per-category rules that exploit the env's
    reward structure. Goal: beat random by >30% on medium.

Each policy is a pure function (obs, rng) -> AriaAction.
"""
from __future__ import annotations

import random
from typing import Callable

from aria_contracts import ActionId, AriaAction, AriaObservation


Policy = Callable[[AriaObservation, random.Random], AriaAction]


# -----------------------------------------------------------------------------
# Random
# -----------------------------------------------------------------------------


def random_policy(obs: AriaObservation, rng: random.Random) -> AriaAction:
    aid = rng.randrange(15)
    target = None
    payload: dict = {}
    if aid in (
        ActionId.RESCHEDULE.value, ActionId.CANCEL.value,
        ActionId.DECLINE_INVITE.value, ActionId.PROPOSE_ALTERNATIVE.value,
        ActionId.RESOLVE_CONFLICT.value,
    ) and obs.calendar:
        target = rng.choice(obs.calendar).event_id
    elif aid == ActionId.DRAFT_REPLY.value and obs.inbox:
        target = rng.choice(obs.inbox).email_id
    elif aid in (ActionId.DELEGATE.value, ActionId.SET_REMINDER.value, ActionId.PURCHASE.value) and obs.pending_tasks:
        target = rng.choice(obs.pending_tasks).task_id
        if aid == ActionId.DELEGATE.value:
            # need an assignee
            payload["assignee_id"] = "c_report"
        elif aid == ActionId.PURCHASE.value:
            payload["amount"] = 100.0
            payload["user_approved"] = bool(rng.random() < 0.5)
    elif aid == ActionId.BATCH_ACTION.value and obs.inbox:
        ids = [i.email_id for i in obs.inbox[: min(5, len(obs.inbox))]]
        payload["email_ids"] = ids
    return AriaAction(action_id=aid, target_id=target, payload=payload)


# -----------------------------------------------------------------------------
# Do-nothing (always WAIT)
# -----------------------------------------------------------------------------


def do_nothing_policy(obs: AriaObservation, rng: random.Random) -> AriaAction:
    return AriaAction(action_id=ActionId.WAIT.value)


# -----------------------------------------------------------------------------
# Scripted expert — exploits reward structure per category
# -----------------------------------------------------------------------------


def scripted_expert(obs: AriaObservation, rng: random.Random) -> AriaAction:
    cat = obs.scenario_category
    if cat == "calendar_conflict":
        # Look for the day-0 overlap and call RESOLVE_CONFLICT on the personal event
        day0 = [e for e in obs.calendar if e.day_offset == 0]
        overlaps: list[tuple] = []
        for i, a in enumerate(day0):
            for b in day0[i + 1:]:
                if a.start_hour < b.end_hour and b.start_hour < a.end_hour:
                    overlaps.append((a, b))
        if overlaps:
            a, b = overlaps[0]
            # Prefer the higher-priority personal (partner/family) event as the target
            target = a if a.event_id == "conflict_personal" else b
            return AriaAction(action_id=ActionId.RESOLVE_CONFLICT.value, target_id=target.event_id)
        # If resolved, clear urgent emails
        if obs.inbox:
            urgent = [it for it in obs.inbox if it.urgency >= 0.85 and it.requires_reply]
            if urgent:
                return AriaAction(
                    action_id=ActionId.DRAFT_REPLY.value, target_id=urgent[0].email_id,
                )

    if cat == "email_triage":
        urgent = [it for it in obs.inbox if it.urgency >= 0.85 and it.requires_reply]
        if urgent:
            return AriaAction(
                action_id=ActionId.DRAFT_REPLY.value, target_id=urgent[0].email_id
            )
        # then batch the low-urgency leftovers
        low = [it for it in obs.inbox if it.urgency < 0.5]
        if low:
            return AriaAction(
                action_id=ActionId.BATCH_ACTION.value,
                payload={"email_ids": [it.email_id for it in low[:5]]},
            )

    if cat == "message_reply":
        # Find loaded messages → reply with correct tone per sender preference
        for it in obs.inbox:
            if it.sentiment < -0.3:
                sender = next(
                    (r for r in obs.relationships if r.contact_id == it.sender_id), None
                )
                tone = sender.tone_preference if sender else "warm"
                return AriaAction(
                    action_id=ActionId.DRAFT_REPLY.value,
                    target_id=it.email_id,
                    payload={"tone": tone},
                )

    if cat == "dinner_planning":
        # Schedule is already placed by generator; pick the high-prio plan task
        for t in obs.pending_tasks:
            if t.task_id == "dinner_plan":
                return AriaAction(action_id=ActionId.SET_REMINDER.value, target_id=t.task_id)

    if cat == "delegation":
        # Delegate any delegatable task not yet assigned
        for t in obs.pending_tasks:
            if t.delegatable and t.status == "open":
                return AriaAction(
                    action_id=ActionId.DELEGATE.value,
                    target_id=t.task_id,
                    payload={"assignee_id": "c_report"},
                )

    if cat == "shopping":
        for t in obs.pending_tasks:
            if t.task_id == "buy_gift" and t.status == "open":
                return AriaAction(
                    action_id=ActionId.PURCHASE.value,
                    target_id=t.task_id,
                    payload={"amount": 900.0, "user_approved": True},
                )

    # fallback: urgent reply, else wait
    urgent = [it for it in obs.inbox if it.urgency >= 0.85 and it.requires_reply]
    if urgent:
        return AriaAction(
            action_id=ActionId.DRAFT_REPLY.value, target_id=urgent[0].email_id
        )
    return AriaAction(action_id=ActionId.WAIT.value)


POLICIES: dict[str, Policy] = {
    "random": random_policy,
    "do_nothing": do_nothing_policy,
    "expert": scripted_expert,
}
