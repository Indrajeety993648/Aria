"""TRL-compatible reward function.

Each call: spin a fresh AriaEnv on the prompt's seed/category/difficulty,
parse the LLM output into an AriaAction, step the env exactly once, return
the scalar reward. Optionally penalises parse failures so the model is
strongly motivated to stay in the ACTION/TARGET/PAYLOAD format.

Note on TRL input shape: when our dataset uses chat-format prompts
(`list[{"role": "...", "content": "..."}]`), GRPOTrainer passes BOTH
`prompts` and `completions` as `list[list[dict]]` — NOT `list[str]`.
We normalize either shape via `_to_text` so the reward function works
regardless of which dataset format is in play.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from env_service.aria_env import AriaEnv

from .action_parser import parse_action


@dataclass(slots=True)
class EpisodeSeed:
    seed: int
    category: str
    difficulty: str


def _to_text(payload: Any) -> str:
    """Normalize TRL's prompt/completion to a single string.

    Handles three shapes that GRPOTrainer can pass:
      - plain string                                    → return as-is
      - list of message dicts [{"role", "content"}, …]  → join `content`s
      - list with leading assistant turn (completion)   → take last content
    """
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        # If it's a list of dicts with `content`, join them
        parts: list[str] = []
        for item in payload:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    # OpenAI-style content blocks: [{"type":"text","text":"..."}]
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            parts.append(str(block["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(payload)


def make_reward_fn(
    *,
    parse_failure_penalty: float = -0.5,
    ablate_dimensions: tuple[str, ...] = (),
):
    """Returns a TRL-compatible reward callable.

    Expects the prompt to embed `[[ARIA_SEED <int> <category> <difficulty>]]`
    in any text content (rollout.py puts it in the system message).
    """
    import re
    _RE_SEED = re.compile(r"\[\[ARIA_SEED\s+(\d+)\s+(\w+)\s+(\w+)\]\]")

    def reward_fn(prompts: Sequence[Any], completions: Sequence[Any], **_kw) -> list[float]:
        rewards: list[float] = []
        for prompt, completion in zip(prompts, completions):
            prompt_text = _to_text(prompt)
            completion_text = _to_text(completion)

            m = _RE_SEED.search(prompt_text)
            if not m:
                rewards.append(parse_failure_penalty)
                continue
            seed = int(m.group(1))
            cat = m.group(2)
            diff = m.group(3)

            env = AriaEnv(ablate_dimensions=ablate_dimensions)
            env.reset(seed=seed, category=cat, difficulty=diff)

            action, parse_failed = parse_action(completion_text)
            if parse_failed:
                rewards.append(parse_failure_penalty)
                continue

            try:
                obs = env.step(action)
                rewards.append(float(obs.reward or 0.0))
            except Exception:
                rewards.append(parse_failure_penalty)
        return rewards

    return reward_fn


__all__ = ["EpisodeSeed", "_to_text", "make_reward_fn"]
