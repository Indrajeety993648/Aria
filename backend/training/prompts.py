"""AriaObservation → prompt formatter for LLM-based RL.

Goal: produce a compact, model-friendly description of the world the agent
must act on, including the available action space, so the LLM emits a parseable
ACTION/TARGET/PAYLOAD response.

Why compact: Qwen 0.5B has a 32k context window but small models lose track
fast in long prompts. We keep it under ~600 tokens.
"""
from __future__ import annotations

from aria_contracts import AriaObservation


SYSTEM_PROMPT = """\
You are ARIA, a personal AI manager helping a busy professional.
You receive a snapshot of their current world (calendar, inbox, contacts,
tasks). You pick exactly ONE action from the 15 available. You care about
completing tasks AND preserving relationships AND staying safe.

Format your output EXACTLY like this:
ACTION: <NAME>
TARGET: <id or NONE>
PAYLOAD: <JSON object or {}>

Pick from these actions:
  0  SEND_MSG             — message a contact (target=contact_id, payload={"tone": "...", "lang": "en|hinglish"})
  1  SCHEDULE             — create a new event (payload={"title", "start_hour", "day_offset", "participants"})
  2  RESCHEDULE           — move an existing event (target=event_id, payload={"start_hour"})
  3  CANCEL               — cancel an event (target=event_id, payload={"proposed_alternative": bool})
  4  DELEGATE             — hand a task to someone (target=task_id, payload={"assignee_id"})
  5  DRAFT_REPLY          — reply to an inbox message (target=email_id, payload={"tone", "lang"})
  6  SET_REMINDER         — flag a task for later (target=task_id)
  7  PURCHASE             — spend money (target=task_id, payload={"amount", "user_approved": bool})
  8  RESOLVE_CONFLICT     — fix a calendar conflict (target=conflict_event_id)
  9  ASK_USER             — ask the principal for clarification (use sparingly)
 10  DECLINE_INVITE       — decline an event (target=event_id)
 11  PROPOSE_ALTERNATIVE  — offer a new time for an event (target=event_id, payload={"start_hour"})
 12  BATCH_ACTION         — bulk-archive low-urgency emails (payload={"email_ids": [...]})
 13  WAIT                 — do nothing this step
 14  ESCALATE             — flag for human attention

Tone options: formal, casual, warm, direct.
Language options: en, hi, hinglish.
"""


def _summarize_calendar(obs: AriaObservation, max_items: int = 8) -> str:
    if not obs.calendar:
        return "  (empty)"
    lines = []
    # Sort by day_offset, then start_hour; emphasise day-0 first.
    items = sorted(obs.calendar, key=lambda e: (e.day_offset, e.start_hour))[:max_items]
    for e in items:
        when = f"D+{e.day_offset:02d} {e.start_hour:.1f}-{e.end_hour:.1f}"
        ppl = "+".join(p.replace("c_", "") for p in e.participant_ids[:2]) or "-"
        lines.append(
            f"  {e.event_id:<22} {when:<14} pri={e.priority:.2f} flex={e.flexibility:.2f} w/{ppl} \"{e.title}\""
        )
    return "\n".join(lines)


def _summarize_inbox(obs: AriaObservation, max_items: int = 6) -> str:
    if not obs.inbox:
        return "  (empty)"
    lines = []
    for it in obs.inbox[:max_items]:
        sender = it.sender_id.replace("c_", "")
        sent = f"sent={it.sentiment:+.2f}"
        flag = "URG" if it.urgency >= 0.85 else "med" if it.urgency >= 0.5 else "low"
        reply = "reply" if it.requires_reply else "info"
        lines.append(
            f"  {it.email_id:<10} from={sender:<8} {flag:<3} age={it.age_hours:.1f}h {sent} {reply}: \"{it.subject}\""
        )
    return "\n".join(lines)


def _summarize_relationships(obs: AriaObservation, max_items: int = 8) -> str:
    if not obs.relationships:
        return "  (none)"
    lines = []
    for r in obs.relationships[:max_items]:
        lang = f" lang={r.language_preference}" if r.language_preference and r.language_preference != "en" else ""
        lines.append(
            f"  {r.contact_id:<12} {r.relationship_kind:<10} closeness={r.closeness:.2f} "
            f"trust={r.trust:.2f} tone={r.tone_preference}{lang} last={r.last_contact_hours:.0f}h"
        )
    return "\n".join(lines)


def _summarize_tasks(obs: AriaObservation, max_items: int = 6) -> str:
    if not obs.pending_tasks:
        return "  (none)"
    lines = []
    for t in obs.pending_tasks[:max_items]:
        lines.append(
            f"  {t.task_id:<10} pri={t.priority:.2f} due={t.deadline_hours:+.1f}h "
            f"{'DELG' if t.delegatable else '----'} status={t.status} \"{t.title}\""
        )
    return "\n".join(lines)


def format_observation(obs: AriaObservation) -> str:
    scenario = obs.scenario_category or "unknown"
    diff = obs.difficulty or "unknown"
    return f"""\
SCENARIO: {scenario} ({diff}) | TIME: {obs.time:.2f}h | LOC: {obs.location} | STEP: {obs.step_count}/{obs.max_steps}

CALENDAR (next 30d):
{_summarize_calendar(obs)}

INBOX (priority order):
{_summarize_inbox(obs)}

CONTACTS:
{_summarize_relationships(obs)}

TASKS:
{_summarize_tasks(obs)}

Pick one action. Respond ONLY with the three required lines (ACTION/TARGET/PAYLOAD).
"""


def build_prompt(obs: AriaObservation) -> list[dict[str, str]]:
    """Return a chat-template-friendly message list."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": format_observation(obs)},
    ]


__all__ = ["SYSTEM_PROMPT", "build_prompt", "format_observation"]
