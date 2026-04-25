"""TRL-compatible reward function.

Each call: spin a fresh AriaEnv on the prompt's seed/category/difficulty,
parse the LLM output into an AriaAction, step the env exactly once, return
the scalar reward. Optionally penalises parse failures so the model is
strongly motivated to stay in the ACTION/TARGET/PAYLOAD format.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from env_service.aria_env import AriaEnv

from .action_parser import parse_action


@dataclass(slots=True)
class EpisodeSeed:
    seed: int
    category: str
    difficulty: str


def make_reward_fn(
    *,
    parse_failure_penalty: float = -0.5,
    ablate_dimensions: tuple[str, ...] = (),
):
    """Returns a TRL-compatible reward callable.

    TRL's GRPOTrainer passes prompts (a list[str]) and completions
    (list[str]). We expect the prompt to encode the (seed, category,
    difficulty) tuple in a structured JSON header so we can recreate the
    exact env state for each rollout. See `rollout.py` for how prompts are
    constructed.
    """
    import re
    _RE_SEED = re.compile(r"\[\[ARIA_SEED\s+(\d+)\s+(\w+)\s+(\w+)\]\]")

    def reward_fn(prompts: Sequence[str], completions: Sequence[str], **_kw) -> list[float]:
        rewards: list[float] = []
        for prompt, completion in zip(prompts, completions):
            m = _RE_SEED.search(prompt)
            if not m:
                rewards.append(parse_failure_penalty)
                continue
            seed = int(m.group(1))
            cat = m.group(2)
            diff = m.group(3)

            env = AriaEnv(ablate_dimensions=ablate_dimensions)
            env.reset(seed=seed, category=cat, difficulty=diff)

            action, parse_failed = parse_action(completion)
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


__all__ = ["EpisodeSeed", "make_reward_fn"]
