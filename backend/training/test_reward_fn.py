"""Smoke tests for the TRL-compatible reward function.

The TRL bug we ran into: GRPOTrainer passes `prompts` as `list[list[dict]]`
when the dataset is chat-formatted, NOT `list[str]`. These tests pin the
contract so we never regress.

Run from repo root:
    PYTHONPATH=backend:backend/services/env-service/src \
        python backend/training/test_reward_fn.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make sibling packages importable
_REPO = Path(__file__).resolve().parents[2]
for _p in (
    _REPO,
    _REPO / "backend",
    _REPO / "backend" / "services" / "env-service" / "src",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.training.action_parser import render_action  # noqa: E402
from backend.training.reward_fn import _to_text, make_reward_fn  # noqa: E402
from backend.training.rollout import encode_prompt_seed_header  # noqa: E402

from aria_contracts import ActionId, AriaAction  # noqa: E402


def test_to_text_with_string():
    assert _to_text("hello") == "hello"


def test_to_text_with_message_list():
    msgs = [
        {"role": "system", "content": "You are ARIA."},
        {"role": "user", "content": "Pick an action."},
    ]
    out = _to_text(msgs)
    assert "You are ARIA." in out
    assert "Pick an action." in out


def test_to_text_with_assistant_completion():
    """TRL passes completions as [{"role":"assistant","content":"..."}]."""
    completion = [{"role": "assistant", "content": "ACTION: WAIT\nTARGET: NONE\nPAYLOAD: {}"}]
    assert "ACTION: WAIT" in _to_text(completion)


def test_to_text_with_openai_blocks():
    """Handles content blocks like [{type:text, text:...}]."""
    msgs = [
        {"role": "system", "content": [{"type": "text", "text": "embedded text"}]},
    ]
    assert "embedded text" in _to_text(msgs)


def test_reward_fn_with_message_list_prompt():
    """The exact failure mode from Colab. Should now work."""
    fn = make_reward_fn()

    # Prompt as TRL passes it: list of message dicts including ARIA_SEED header.
    seed_header = encode_prompt_seed_header(42, "calendar_conflict", "medium")
    prompts = [[
        {"role": "system", "content": f"{seed_header}\nYou are ARIA."},
        {"role": "user", "content": "Pick an action."},
    ]]

    # Completion as TRL passes it: list with one assistant message.
    a = AriaAction(action_id=ActionId.RESOLVE_CONFLICT.value, target_id="conflict_personal")
    completions = [[{"role": "assistant", "content": render_action(a)}]]

    rewards = fn(prompts, completions)
    assert len(rewards) == 1
    # Should be POSITIVE — resolve_conflict on the right target gets +1 conflict_resolution
    assert rewards[0] > 0, f"expected positive reward, got {rewards[0]}"


def test_reward_fn_with_string_prompt_still_works():
    """Backward-compatible string path."""
    fn = make_reward_fn()
    seed_header = encode_prompt_seed_header(42, "calendar_conflict", "medium")
    prompts = [f"{seed_header}\n... rest of prompt ..."]
    a = AriaAction(action_id=ActionId.RESOLVE_CONFLICT.value, target_id="conflict_personal")
    completions = [render_action(a)]
    rewards = fn(prompts, completions)
    assert rewards[0] > 0


def test_reward_fn_missing_header_returns_penalty():
    fn = make_reward_fn(parse_failure_penalty=-0.5)
    rewards = fn(["no header here"], ["ACTION: WAIT\nTARGET: NONE\nPAYLOAD: {}"])
    assert rewards == [-0.5]


def test_reward_fn_unparseable_completion_returns_penalty():
    fn = make_reward_fn(parse_failure_penalty=-0.5)
    seed_header = encode_prompt_seed_header(42, "calendar_conflict", "medium")
    rewards = fn([[{"role": "system", "content": seed_header}]],
                 [[{"role": "assistant", "content": "uhh I don't know"}]])
    assert rewards == [-0.5]


def test_ablation_changes_reward():
    """Same action, two reward fns — ablated one should give different reward."""
    full = make_reward_fn()
    abl = make_reward_fn(ablate_dimensions=("relationship_health",))
    seed_header = encode_prompt_seed_header(1, "calendar_conflict", "medium")
    prompts = [[{"role": "system", "content": seed_header}]]
    # Cancel high-closeness without alternative — relationship_health takes a hit
    a = AriaAction(action_id=ActionId.CANCEL.value, target_id="conflict_personal",
                   payload={"proposed_alternative": False})
    completions = [[{"role": "assistant", "content": render_action(a)}]]
    full_r = full(prompts, completions)[0]
    abl_r = abl(prompts, completions)[0]
    # Ablated should be HIGHER (it doesn't see the relationship_health penalty)
    assert abl_r > full_r, f"ablation should hide the penalty: full={full_r} abl={abl_r}"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ✗ {t.__name__} — {e}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__} — {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
