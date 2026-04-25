"""Action handlers — one function per ActionId.

Each handler:
  - takes (world: WorldModel, action: AriaAction)
  - mutates world in-place
  - advances world.time by an action-appropriate amount
  - returns a `dict` outcome matching the keys aria-rewards expects

Signatures are intentionally uniform so `dispatch()` stays a single table lookup.
"""
from __future__ import annotations

from typing import Any, Callable

from aria_contracts import ActionId, AriaAction

from env_service.world import WorldModel

# Per-action time cost in hours — rough estimate of how long it takes.
TIME_COST: dict[int, float] = {
    ActionId.SEND_MSG.value:            0.05,
    ActionId.SCHEDULE.value:            0.15,
    ActionId.RESCHEDULE.value:          0.15,
    ActionId.CANCEL.value:              0.05,
    ActionId.DELEGATE.value:            0.15,
    ActionId.DRAFT_REPLY.value:         0.10,
    ActionId.SET_REMINDER.value:        0.02,
    ActionId.PURCHASE.value:            0.10,
    ActionId.RESOLVE_CONFLICT.value:    0.25,
    ActionId.ASK_USER.value:            0.05,
    ActionId.DECLINE_INVITE.value:      0.05,
    ActionId.PROPOSE_ALTERNATIVE.value: 0.15,
    ActionId.BATCH_ACTION.value:        0.20,
    ActionId.WAIT.value:                0.50,
    ActionId.ESCALATE.value:            0.10,
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _urgent_pending_count(world: WorldModel) -> int:
    return sum(1 for it in world.inbox if it.urgency >= 0.85 and it.requires_reply)


def _neglected_close_urgent(world: WorldModel) -> int:
    close_ids = {r.contact_id for r in world.relationships if r.closeness >= 0.7}
    return sum(
        1 for it in world.inbox
        if it.urgency >= 0.85 and it.sender_id in close_ids and it.age_hours >= 2.0
    )


def _objective_hit(world: WorldModel, kind: str, target_id: str | None = None) -> bool:
    """Mark matching objectives as met. Returns True if any were flipped."""
    flipped = False
    for o in world.objectives:
        if o["met"]:
            continue
        if o["kind"] != kind:
            continue
        if target_id is not None and o.get("target_id") not in (None, target_id):
            continue
        o["met"] = True
        flipped = True
    return flipped


# =============================================================================
# Handlers
# =============================================================================


def send_msg(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    contact = world.find_contact(a.target_id)
    payload = a.payload or {}
    affected = [contact.contact_id] if contact else []
    tone = payload.get("tone")

    # Tone preference mismatch (existing signal)
    pref_mismatch = bool(contact and tone and tone != contact.tone_preference)

    # NEW: hidden-mood mismatch — direct/formal tone toward an upset contact
    # is a strong relationship hit even if it matches their stated preference.
    # The agent must INFER mood from inbox sentiment; mood itself is never
    # exposed on the observation. This is the partial-observability axis.
    mood_mismatch = False
    if contact is not None and contact.current_mood is not None and tone:
        if contact.current_mood < -0.30 and tone in ("direct", "formal"):
            mood_mismatch = True
    tone_mismatch = pref_mismatch or mood_mismatch

    closeness_delta = 0.0
    high_stakes = bool(payload.get("high_stakes"))
    user_approved = bool(payload.get("user_approved"))

    if contact and not tone_mismatch:
        contact.last_contact_hours = 0.0
        # Small closeness boost for good-tone contact
        contact.closeness = min(1.0, contact.closeness + 0.01)
        closeness_delta += 0.02
        # Warm/casual replies to an upset contact gradually heal the mood.
        if (
            contact.current_mood is not None
            and contact.current_mood < 0.0
            and tone in ("warm", "casual")
        ):
            contact.current_mood = min(1.0, contact.current_mood + 0.10)
    elif contact and mood_mismatch and contact.current_mood is not None:
        # Wrong tone toward an already-upset contact deepens the mood.
        contact.current_mood = max(-1.0, contact.current_mood - 0.10)

    objective_met = False
    if contact is not None and tone and tone == contact.tone_preference and not mood_mismatch:
        objective_met = _objective_hit(world, "reply_with_correct_tone", a.target_id)

    return {
        "success": contact is not None,
        "affected_contacts": affected,
        "closeness_delta": closeness_delta,
        "tone_mismatch": tone_mismatch,
        "mood_mismatch": mood_mismatch,
        "high_stakes": high_stakes,
        "user_approved": user_approved,
        "scenario_objective_met": objective_met,
    }


def schedule(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    payload = a.payload or {}
    day_offset = int(payload.get("day_offset", 0))
    start_hour = float(payload.get("start_hour", 10.0))
    end_hour = float(payload.get("end_hour", start_hour + 1.0))
    # Very permissive — we don't enforce calendar sanity here, just log the event.
    from aria_contracts import CalendarEvent
    new = CalendarEvent(
        event_id=f"sched_{world.step_count:04d}",
        day_offset=min(29, max(0, day_offset)),
        start_hour=max(0.0, min(23.9, start_hour)),
        end_hour=max(0.1, min(24.0, end_hour)),
        title=str(payload.get("title", "New event")),
        priority=float(payload.get("priority", 0.5)),
        flexibility=float(payload.get("flexibility", 0.5)),
        participant_ids=list(payload.get("participants", [])),
    )
    world.calendar.append(new)
    world.calendar.sort(key=lambda e: (e.day_offset, e.start_hour))
    return {"success": True, "created_event_id": new.event_id}


def reschedule(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    evt = world.find_event(a.target_id)
    if evt is None:
        return {"success": False, "reason": "event_not_found"}
    payload = a.payload or {}
    if "start_hour" in payload:
        new_start = float(payload["start_hour"])
        duration = evt.end_hour - evt.start_hour
        evt.start_hour = max(0.0, min(23.9, new_start))
        evt.end_hour = min(24.0, evt.start_hour + duration)
    if "day_offset" in payload:
        evt.day_offset = max(0, min(29, int(payload["day_offset"])))
    # Rescheduling resolves conflicts when it moves one of the overlapping pair
    conflict_meta = world.hidden.get("primary_conflict")
    conflict_resolved = None
    if conflict_meta and evt.event_id in conflict_meta.get("events", []):
        still_overlap = False
        for other_id in conflict_meta["events"]:
            if other_id == evt.event_id:
                continue
            other = world.find_event(other_id)
            if other and evt.day_offset == other.day_offset and (
                evt.start_hour < other.end_hour and other.start_hour < evt.end_hour
            ):
                still_overlap = True
        conflict_resolved = not still_overlap
        if conflict_resolved:
            _objective_hit(world, "resolve_day0_conflict")

    return {
        "success": True,
        "conflict_resolved": conflict_resolved,
    }


def cancel(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    evt = world.find_event(a.target_id)
    if evt is None:
        return {"success": False, "reason": "event_not_found"}
    affected_high = any(
        (c := world.find_contact(pid)) is not None and c.closeness >= 0.8
        for pid in evt.participant_ids
    )
    proposed_alt = bool((a.payload or {}).get("proposed_alternative", False))

    # Capture metadata BEFORE removing the event so cascades can use it.
    cancelled_participants = list(evt.participant_ids)
    cancelled_day = int(evt.day_offset)

    # Remove the event
    world.calendar = [e for e in world.calendar if e.event_id != evt.event_id]

    closeness_delta = 0.0
    for pid in evt.participant_ids:
        c = world.find_contact(pid)
        if c is None:
            continue
        drop = 0.15 if c.closeness >= 0.8 else 0.05
        if proposed_alt:
            drop /= 2.0
        c.closeness = max(0.0, c.closeness - drop)
        closeness_delta -= drop

    # Conflict sacrifice — resolved but at the cost of the cancelled party
    conflict_meta = world.hidden.get("primary_conflict")
    conflict_resolved = None
    conflict_sacrifice = False
    if conflict_meta and evt.event_id in conflict_meta.get("events", []):
        conflict_resolved = True
        conflict_sacrifice = True

    return {
        "success": True,
        "affected_high_closeness": affected_high,
        "proposed_alternative": proposed_alt,
        "closeness_delta": closeness_delta,
        "conflict_resolved": conflict_resolved,
        "conflict_sacrifice": conflict_sacrifice,
        "scenario_objective_hurt": affected_high and not proposed_alt,
        # Cascade inputs (consumed by _apply_cascades)
        "cancel_participants": cancelled_participants,
        "cancel_day": cancelled_day,
    }


def delegate(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    task = world.find_task(a.target_id)
    assignee_id = (a.payload or {}).get("assignee_id")
    if task is None:
        return {"success": False, "reason": "task_not_found"}
    if not task.delegatable:
        return {
            "success": False,
            "reason": "task_not_delegatable",
            "wasted_action": True,
        }
    if assignee_id is None:
        return {"success": False, "reason": "no_assignee", "wasted_action": True}
    task.assignee_id = assignee_id
    task.status = "assigned"
    objective_met = _objective_hit(world, "delegate_delegatable", task.task_id)
    return {
        "success": True,
        "tasks_completed": [task.task_id],  # assignment counts as resolution here
        "scenario_objective_met": objective_met,
    }


def draft_reply(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    email = world.find_email(a.target_id)
    if email is None:
        return {"success": False, "reason": "email_not_found"}
    email.requires_reply = False
    email.urgency = max(0.0, email.urgency - 0.4)
    objective_met_urgent = _objective_hit(world, "reply_to_urgent", email.email_id)
    # tone handling if payload specifies it
    payload = a.payload or {}
    tone = payload.get("tone")
    contact = world.find_contact(email.sender_id)
    pref_mismatch = bool(contact and tone and tone != contact.tone_preference)

    # Hidden-mood gate (same logic as send_msg). Direct/formal tone toward an
    # upset contact is a mismatch even if it matches their stated preference.
    mood_mismatch = False
    if contact is not None and contact.current_mood is not None and tone:
        if contact.current_mood < -0.30 and tone in ("direct", "formal"):
            mood_mismatch = True
    tone_mismatch = pref_mismatch or mood_mismatch
    tone_match = (
        bool(contact and tone and tone == contact.tone_preference)
        and not mood_mismatch
    )

    objective_met_tone = False
    if tone_match:
        objective_met_tone = _objective_hit(
            world, "reply_with_correct_tone", email.email_id
        )

    # Code-mix language gate. ONLY fires for non-English preferences
    # (hi / hinglish) — agents must explicitly pass payload["lang"] matching
    # those. English-preferring contacts skip the check so the bulk of the
    # population doesn't see a mechanic they don't need.
    language_mismatch = False
    if (
        contact is not None
        and contact.language_preference is not None
        and contact.language_preference != "en"
    ):
        agent_lang = (payload.get("lang") or "en").lower()
        if agent_lang != contact.language_preference:
            language_mismatch = True

    # Mutate mood: warm/casual reply to an upset contact heals; bad-tone
    # reply to an upset contact deepens the funk.
    if contact is not None and contact.current_mood is not None:
        if not tone_mismatch and tone in ("warm", "casual") and contact.current_mood < 0.0:
            contact.current_mood = min(1.0, contact.current_mood + 0.10)
        elif mood_mismatch:
            contact.current_mood = max(-1.0, contact.current_mood - 0.10)

    return {
        "success": True,
        "tone_mismatch": tone_mismatch,
        "mood_mismatch": mood_mismatch,
        "language_mismatch": language_mismatch,
        "scenario_objective_met": (
            (objective_met_urgent or objective_met_tone)
            and not language_mismatch
        ),
        "scenario_objective_hurt": language_mismatch,
    }


def set_reminder(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    # Low-impact action. No real effect on world state but not wasted if there's a task.
    has_context = world.find_task(a.target_id) is not None or bool(a.target_id)
    return {"success": has_context, "wasted_action": not has_context}


def purchase(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    payload = a.payload or {}
    amount = float(payload.get("amount", 0.0))
    authorized = bool(payload.get("user_approved", False))
    budget_limit = float(world.hidden.get("budget_limit", 0.0))
    used = float(world.hidden.get("budget_used", 0.0))
    new_used = used + amount
    world.hidden["budget_used"] = new_used

    task = world.find_task(a.target_id)
    objective_met = False
    tasks_completed: list[str] = []
    if task is not None and new_used <= budget_limit and authorized:
        task.status = "done"
        tasks_completed.append(task.task_id)
        objective_met = _objective_hit(world, "purchase_within_budget", task.task_id)

    return {
        "success": authorized and new_used <= budget_limit,
        "authorized": authorized,
        "budget_breach": new_used > budget_limit and budget_limit > 0,
        "tasks_completed": tasks_completed,
        "scenario_objective_met": objective_met,
    }


def resolve_conflict(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    """Successful resolution depends on payload structure — here we trust the
    handler: if it was called with the correct target, we call it resolved.
    """
    meta = world.hidden.get("primary_conflict")
    if meta is None:
        return {"success": False, "reason": "no_conflict", "wasted_action": True}
    if a.target_id not in meta.get("events", []):
        return {"success": False, "reason": "target_not_in_conflict"}

    # Win-win resolution: move the OTHER event out of the overlap window,
    # preserving the target (typically the high-closeness personal event).
    # Shift by enough that start_a >= end_target or vice versa.
    target = world.find_event(a.target_id)
    if target is None:
        return {"success": False, "reason": "event_not_found"}

    moved_any = False
    for other_id in meta["events"]:
        if other_id == a.target_id:
            continue
        other = world.find_event(other_id)
        if other is None or other.day_offset != target.day_offset:
            continue
        if other.start_hour < target.end_hour and target.start_hour < other.end_hour:
            # Move `other` to start right after `target` ends (or to the next morning).
            new_start = min(22.0, target.end_hour + 0.25)
            duration = other.end_hour - other.start_hour
            other.start_hour = new_start
            other.end_hour = min(23.9, new_start + duration)
            moved_any = True

    _objective_hit(world, "resolve_day0_conflict")
    c_id = meta.get("high_closeness_contact")
    c = world.find_contact(c_id)
    closeness_delta = 0.0
    if c is not None:
        c.closeness = min(1.0, c.closeness + 0.05)
        closeness_delta = 0.05

    return {
        "success": True,
        "conflict_resolved": True,
        "scenario_objective_met": True,
        "closeness_delta": closeness_delta,
        "moved_other": moved_any,
    }


def ask_user(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    recent = world.action_history[-5:].count(ActionId.ASK_USER.value)
    return {"success": True, "asking_too_much": recent >= 2}


def decline_invite(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    evt = world.find_event(a.target_id)
    if evt is None:
        return {"success": False}
    # Polite decline — small closeness cost
    closeness_delta = 0.0
    for pid in evt.participant_ids:
        c = world.find_contact(pid)
        if c is None:
            continue
        drop = 0.03
        c.closeness = max(0.0, c.closeness - drop)
        closeness_delta -= drop
    world.calendar = [e for e in world.calendar if e.event_id != evt.event_id]
    return {
        "success": True,
        "closeness_delta": closeness_delta,
    }


def propose_alternative(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    evt = world.find_event(a.target_id)
    if evt is None:
        return {"success": False}
    payload = a.payload or {}
    if "start_hour" in payload:
        new_start = float(payload["start_hour"])
        duration = evt.end_hour - evt.start_hour
        evt.start_hour = max(0.0, min(23.9, new_start))
        evt.end_hour = min(24.0, evt.start_hour + duration)

    # Treated like reschedule but flagged as relationship-preserving
    conflict_meta = world.hidden.get("primary_conflict")
    conflict_resolved = None
    if conflict_meta and evt.event_id in conflict_meta.get("events", []):
        still_overlap = any(
            (o := world.find_event(oid)) is not None
            and o.event_id != evt.event_id
            and o.day_offset == evt.day_offset
            and evt.start_hour < o.end_hour and o.start_hour < evt.end_hour
            for oid in conflict_meta["events"]
        )
        conflict_resolved = not still_overlap
        if conflict_resolved:
            _objective_hit(world, "resolve_day0_conflict")

    return {
        "success": True,
        "proposed_alternative": True,
        "conflict_resolved": conflict_resolved,
        "closeness_delta": 0.04,
    }


def batch_action(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    """Mark N similar low-stakes items as addressed at once (e.g., archive/read)."""
    payload = a.payload or {}
    ids = list(payload.get("email_ids", []))
    affected = 0
    for eid in ids:
        em = world.find_email(eid)
        if em is None:
            continue
        em.requires_reply = False
        em.urgency = max(0.0, em.urgency - 0.2)
        affected += 1
    return {
        "success": affected > 0,
        "batch_size": affected,
        "wasted_action": affected == 0,
    }


def wait(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    urgent = _urgent_pending_count(world)
    neglected = _neglected_close_urgent(world)
    return {
        "success": True,
        "urgent_pending_count": urgent,
        "neglected_close_urgent_count": neglected,
        "wasted_action": urgent > 0,
    }


def escalate(world: WorldModel, a: AriaAction) -> dict[str, Any]:
    # Warranted if conflict exists and is still unresolved, or for high-priority overdue
    conflict_meta = world.hidden.get("primary_conflict")
    warranted = False
    if conflict_meta:
        resolved = any(o["met"] for o in world.objectives if o["kind"].startswith("resolve_"))
        if not resolved:
            warranted = True
    has_hp_overdue = any(
        t.priority >= 0.8 and t.deadline_hours <= 0 and t.status == "open"
        for t in world.pending_tasks
    )
    warranted = warranted or has_hp_overdue
    return {"success": True, "escalation_warranted": warranted}


# =============================================================================
# Dispatcher
# =============================================================================

HANDLERS: dict[int, Callable[[WorldModel, AriaAction], dict[str, Any]]] = {
    ActionId.SEND_MSG.value:            send_msg,
    ActionId.SCHEDULE.value:            schedule,
    ActionId.RESCHEDULE.value:          reschedule,
    ActionId.CANCEL.value:              cancel,
    ActionId.DELEGATE.value:            delegate,
    ActionId.DRAFT_REPLY.value:         draft_reply,
    ActionId.SET_REMINDER.value:        set_reminder,
    ActionId.PURCHASE.value:            purchase,
    ActionId.RESOLVE_CONFLICT.value:    resolve_conflict,
    ActionId.ASK_USER.value:            ask_user,
    ActionId.DECLINE_INVITE.value:      decline_invite,
    ActionId.PROPOSE_ALTERNATIVE.value: propose_alternative,
    ActionId.BATCH_ACTION.value:        batch_action,
    ActionId.WAIT.value:                wait,
    ActionId.ESCALATE.value:            escalate,
}


def _apply_cascades(
    world: WorldModel, action: AriaAction, outcome: dict[str, Any]
) -> None:
    """Mutate `world` with second-order effects of the action.

    Cascades persist for the rest of the episode and are observable in the
    NEXT observation — they're hard to game because the consequences come
    later, not at the same step.

    Modeled effects (each is a known psychological pattern):
      - CANCEL on a high-closeness contact without alternative
        → that contact's future events get less flexible
        → their future inbox messages are filed at lower urgency
        (passive-aggressive: they stop signaling things as urgent because
         they've stopped relying on you)
      - DECLINE_INVITE on a close contact
        → mild version of the same passive-aggressive pattern
      - RESOLVE_CONFLICT (success)
        → permanent trust boost on the affected contact
        → their future events become MORE flexible (cooperation reciprocates)
      - PROPOSE_ALTERNATIVE (success)
        → contact's mood improves (relationship-preserving cancel)
    """
    aid = action.action_id

    # ---------- damaging cascades -----------------------------------------
    if (
        aid == ActionId.CANCEL.value
        and outcome.get("affected_high_closeness")
        and not outcome.get("proposed_alternative")
    ):
        affected = outcome.get("cancel_participants") or []
        cancelled_day = int(outcome.get("cancel_day") or 0)
        for cid in affected:
            # All future events that include this contact lose flexibility.
            for evt in world.calendar:
                if evt.day_offset > cancelled_day and cid in evt.participant_ids:
                    evt.flexibility = max(0.0, evt.flexibility - 0.30)
            # All future inbox messages from this contact get muted urgency.
            for em in world.inbox:
                if em.sender_id == cid:
                    em.urgency = max(0.0, em.urgency * 0.70)

    elif aid == ActionId.DECLINE_INVITE.value and outcome.get("success"):
        # Lighter version — they're a bit less generous next time.
        evt_id = action.target_id
        # The invite has been removed; we can't see participants here.
        # Mark it via the contact graph: any contact whose closeness dropped
        # this step gets a small flexibility hit on their future events.
        # Conservative: only contacts the action explicitly affected.
        for cid in outcome.get("cancel_participants") or []:
            for evt in world.calendar:
                if cid in evt.participant_ids:
                    evt.flexibility = max(0.0, evt.flexibility - 0.10)

    # ---------- helpful cascades ------------------------------------------
    if aid == ActionId.RESOLVE_CONFLICT.value and outcome.get("success"):
        meta = world.hidden.get("primary_conflict") or {}
        contact_id = meta.get("high_closeness_contact")
        c = world.find_contact(contact_id)
        if c is not None:
            c.trust = min(1.0, c.trust + 0.05)
            for evt in world.calendar:
                if c.contact_id in evt.participant_ids:
                    evt.flexibility = min(1.0, evt.flexibility + 0.10)

    if aid == ActionId.PROPOSE_ALTERNATIVE.value and outcome.get("success"):
        evt = world.find_event(action.target_id)
        if evt is not None:
            for pid in evt.participant_ids:
                c = world.find_contact(pid)
                if c is not None and c.current_mood is not None:
                    c.current_mood = min(1.0, c.current_mood + 0.15)


def dispatch(world: WorldModel, action: AriaAction) -> dict[str, Any]:
    handler = HANDLERS.get(action.action_id)
    if handler is None:
        return {"success": False, "reason": "unknown_action"}
    outcome = handler(world, action)

    # Apply second-order effects on world state. Persistent for the episode.
    _apply_cascades(world, action, outcome)

    # Global housekeeping
    world.step_count += 1
    world.action_history.append(action.action_id)
    dt = TIME_COST.get(action.action_id, 0.1)
    world.time = min(24.0, world.time + dt)

    # Age inbox items
    for em in world.inbox:
        em.age_hours += dt

    # Decrement task deadlines
    for t in world.pending_tasks:
        if t.status == "open":
            t.deadline_hours -= dt

    # Tasks going overdue this step
    overdue_ids = [
        t.task_id for t in world.pending_tasks
        if t.status == "open" and t.deadline_hours < 0 and t.deadline_hours + dt >= 0
    ]
    if overdue_ids:
        existing = outcome.get("tasks_overdue") or []
        outcome["tasks_overdue"] = list(existing) + overdue_ids

    # Neglect fields (for reward function)
    outcome.setdefault("urgent_pending_count", _urgent_pending_count(world))
    outcome.setdefault("neglected_close_urgent_count", _neglected_close_urgent(world))

    return outcome
