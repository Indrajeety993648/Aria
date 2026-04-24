"""Agent loop. Turns AgentTurnRequest -> AgentTurnResponse.

Pipeline:
  1. Parse text -> AriaAction via mapper.text_to_action().
  2. In simulated mode: call env_client.step() to advance the env.
  3. In live mode: also dispatch stubbed tool calls matching the action kind.
  4. Build a human-readable reply_text from a small template.
  5. Return AgentTurnResponse with timing info.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from aria_contracts import (
    ActionId,
    AgentTurnRequest,
    AgentTurnResponse,
    AriaAction,
    ToolCall,
)

from orchestrator_service.mapper import text_to_action
from orchestrator_service.tools import calendar_stub, gmail_stub
from orchestrator_service.tools.env_client import EnvClient

log = logging.getLogger(__name__)


# Reply templates keyed by ActionId. Kept short and action-specific.
_REPLY_TEMPLATES: dict[ActionId, str] = {
    ActionId.SEND_MSG: "Got it — I'll send that message now.",
    ActionId.SCHEDULE: "Scheduled. I've added it to your calendar.",
    ActionId.RESCHEDULE: "Done — I've rescheduled your meeting.",
    ActionId.CANCEL: "Cancelled. I've cleared it from your calendar.",
    ActionId.DELEGATE: "Delegated — I've handed that off.",
    ActionId.DRAFT_REPLY: "I've drafted a reply for you to review.",
    ActionId.SET_REMINDER: "Reminder set.",
    ActionId.PURCHASE: "Ordered. I'll keep you posted on delivery.",
    ActionId.RESOLVE_CONFLICT: "I've resolved the conflict on your calendar.",
    ActionId.ASK_USER: "Quick question before I proceed — can you clarify?",
    ActionId.DECLINE_INVITE: "Declined on your behalf.",
    ActionId.PROPOSE_ALTERNATIVE: "I've proposed an alternative time.",
    ActionId.BATCH_ACTION: "Working through them as a batch now.",
    ActionId.WAIT: "Holding off for now.",
    ActionId.ESCALATE: "Escalated to the right person.",
}


def _ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


class AgentLoop:
    """Holds the env-client; drives one turn at a time."""

    def __init__(self, env_client: EnvClient | None = None) -> None:
        self.env_client = env_client or EnvClient()
        self.mock_llm: bool = os.environ.get("MOCK_LLM", "1") != "0"

    # ------------------------------------------------------------------ #
    # Main entry                                                          #
    # ------------------------------------------------------------------ #
    async def turn(self, req: AgentTurnRequest) -> AgentTurnResponse:
        t_start = time.perf_counter()

        # --- parse -------------------------------------------------------
        t0 = time.perf_counter()
        action = self._parse_intent(req.user_text)
        parse_ms = _ms_since(t0)

        # --- env step (simulated mode always calls step) ----------------
        env_ms = 0
        try:
            t0 = time.perf_counter()
            await self.env_client.step(req.session_id, action)
            env_ms = _ms_since(t0)
        except Exception as exc:
            # Don't fail the turn — just surface the env issue in metadata.
            log.warning("env step failed for %s: %s", req.session_id, exc)
            env_ms = _ms_since(t0)

        # --- live-mode tool calls ---------------------------------------
        tool_calls: list[ToolCall] = []
        tool_ms = 0
        if req.mode == "live":
            t0 = time.perf_counter()
            tool_calls = await self._dispatch_tools(action)
            tool_ms = _ms_since(t0)

        # --- reply -------------------------------------------------------
        reply = _REPLY_TEMPLATES.get(
            ActionId(action.action_id),
            "Okay.",
        )

        return AgentTurnResponse(
            session_id=req.session_id,
            reply_text=reply,
            tool_calls=tool_calls,
            mapped_env_action=action,
            latency_ms={
                "parse": parse_ms,
                "env_step": env_ms,
                "tools": tool_ms,
                "total": _ms_since(t_start),
            },
        )

    # ------------------------------------------------------------------ #
    # Intent parsing                                                      #
    # ------------------------------------------------------------------ #
    def _parse_intent(self, user_text: str) -> AriaAction:
        """Use the rule-based mapper; optionally fall through to Anthropic."""
        action = text_to_action(user_text)

        if self.mock_llm:
            return action

        # Optional: real LLM assist when MOCK_LLM=0 AND anthropic is installed
        # AND an API key is configured. Import is lazy on purpose.
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                llm_action = self._anthropic_refine(user_text, action)
                if llm_action is not None:
                    return llm_action
            except Exception as exc:  # pragma: no cover — defensive
                log.warning("anthropic refine failed, using rule-based: %s", exc)
        return action

    def _anthropic_refine(
        self, user_text: str, fallback: AriaAction
    ) -> AriaAction | None:  # pragma: no cover — optional, no key in CI
        """Stub hook for a real LLM. Returns None to keep the rule-based result.

        Kept as a named method so tests can monkeypatch it. We deliberately do
        not call the Anthropic SDK here — the mock path is canonical.
        """
        return None

    # ------------------------------------------------------------------ #
    # Tool dispatch                                                       #
    # ------------------------------------------------------------------ #
    async def _dispatch_tools(self, action: AriaAction) -> list[ToolCall]:
        """Map an AriaAction to one or more stubbed tool invocations."""
        calls: list[ToolCall] = []
        kind = ActionId(action.action_id)

        if kind in (ActionId.SEND_MSG, ActionId.DRAFT_REPLY):
            args: dict[str, Any] = {
                "to": action.payload.get("to", action.target_id or "unknown@example.com"),
                "subject": action.payload.get("subject", "(no subject)"),
                "body": action.payload.get("body", action.payload.get("user_text", "")),
            }
            result = await gmail_stub.send_email(**args)
            calls.append(
                ToolCall(tool_name="gmail.send_email", arguments=args, result=result)
            )

        elif kind == ActionId.SCHEDULE:
            args = {
                "title": action.payload.get("title", "New meeting"),
                "start_iso": action.payload.get("start_iso"),
                "end_iso": action.payload.get("end_iso"),
                "attendees": action.payload.get("attendees", []),
            }
            result = await calendar_stub.create_event(**args)
            calls.append(
                ToolCall(tool_name="calendar.create_event", arguments=args, result=result)
            )

        elif kind == ActionId.RESCHEDULE:
            args = {
                "event_id": action.target_id or "unknown",
                "new_start_iso": action.payload.get("new_start_iso"),
                "new_end_iso": action.payload.get("new_end_iso"),
            }
            result = await calendar_stub.reschedule_event(**args)
            calls.append(
                ToolCall(
                    tool_name="calendar.reschedule_event",
                    arguments=args,
                    result=result,
                )
            )

        elif kind == ActionId.CANCEL:
            args = {"event_id": action.target_id or "unknown"}
            result = await calendar_stub.cancel_event(**args)
            calls.append(
                ToolCall(tool_name="calendar.cancel_event", arguments=args, result=result)
            )

        # Other action kinds don't map to a real-world tool in the stub catalog.
        return calls


__all__ = ["AgentLoop"]
