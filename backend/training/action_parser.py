"""Parse LLM text output → AriaAction.

Robust to common LLM mistakes:
  - extra whitespace / blank lines
  - markdown code fences (```...```)
  - Action specified by name OR by integer
  - PAYLOAD that's a JSON-ish but with smart quotes / single quotes
  - completely malformed output → fallback to WAIT, with `parse_failed=True` flag
"""
from __future__ import annotations

import json
import re
from typing import Any

from aria_contracts import ActionId, AriaAction


_ACTION_NAME_TO_ID: dict[str, int] = {a.name: a.value for a in ActionId}
_ACTION_ID_TO_NAME: dict[int, str] = {a.value: a.name for a in ActionId}

# Accept :, /, =, or whitespace as separator. Small instruct-tuned models
# (Qwen 0.5B) frequently emit `ACTION/X` or `ACTION X` instead of `ACTION: X`.
_SEP = r"[\s:/=]+"
_RE_ACTION = re.compile(rf"^\s*ACTION{_SEP}([\w]+)\s*$", re.MULTILINE | re.IGNORECASE)
_RE_TARGET = re.compile(rf"^\s*TARGET{_SEP}(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_RE_PAYLOAD = re.compile(rf"^\s*PAYLOAD{_SEP}(.*)$", re.MULTILINE | re.IGNORECASE | re.DOTALL)


def _coerce_payload(raw: str) -> dict[str, Any]:
    """Best-effort parse of a payload field into a dict."""
    if not raw or raw.strip() in ("{}", "NONE", "None", "none", "-"):
        return {}
    s = raw.strip()
    # Strip trailing junk after the JSON object — LLMs sometimes append commentary.
    if s.startswith("{"):
        depth = 0
        end = -1
        for i, ch in enumerate(s):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > 0:
            s = s[:end]
    # Fix common issues
    s = s.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_action(text: str) -> tuple[AriaAction, bool]:
    """Parse a model output into an AriaAction.

    Returns (action, parse_failed). On parse failure, returns a WAIT action
    with parse_failed=True — the env will reward that as a wasted action.
    """
    if not text:
        return AriaAction(action_id=ActionId.WAIT.value), True

    # Strip code fences if present.
    fence = re.search(r"```[\w]*\n(.+?)\n```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    a_match = _RE_ACTION.search(text)
    if not a_match:
        return AriaAction(action_id=ActionId.WAIT.value), True

    a_raw = a_match.group(1).strip().upper()
    # Allow integer or name
    action_id: int | None = None
    if a_raw.isdigit():
        n = int(a_raw)
        if 0 <= n <= 14:
            action_id = n
    else:
        action_id = _ACTION_NAME_TO_ID.get(a_raw)

    if action_id is None:
        return AriaAction(action_id=ActionId.WAIT.value), True

    target: str | None = None
    t_match = _RE_TARGET.search(text)
    if t_match:
        raw_t = t_match.group(1).strip().strip('"').strip("'")
        if raw_t and raw_t.upper() not in ("NONE", "NULL", "-"):
            target = raw_t

    payload: dict[str, Any] = {}
    p_match = _RE_PAYLOAD.search(text)
    if p_match:
        payload = _coerce_payload(p_match.group(1))

    try:
        return AriaAction(action_id=action_id, target_id=target, payload=payload), False
    except Exception:
        return AriaAction(action_id=ActionId.WAIT.value), True


def render_action(a: AriaAction) -> str:
    """Inverse — used in test fixtures + few-shot examples."""
    name = _ACTION_ID_TO_NAME.get(a.action_id, "WAIT")
    target = a.target_id if a.target_id else "NONE"
    payload = json.dumps(a.payload or {}, separators=(",", ":"))
    return f"ACTION: {name}\nTARGET: {target}\nPAYLOAD: {payload}"


__all__ = ["parse_action", "render_action"]
