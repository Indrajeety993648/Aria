"""Episode rollout helpers — used both in training (GRPO needs single-step
prompts) and in evaluation (multi-step trajectories for plotting).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from aria_contracts import AriaAction, AriaObservation
from aria_scenarios import CATEGORIES, DIFFICULTIES
from env_service.aria_env import AriaEnv

from .prompts import build_prompt, format_observation


# A magic comment embedded in every prompt so reward_fn can re-create the
# exact env state. Reads as: [[ARIA_SEED <int> <category> <difficulty>]]
def encode_prompt_seed_header(seed: int, category: str, difficulty: str) -> str:
    return f"[[ARIA_SEED {seed} {category} {difficulty}]]"


@dataclass(slots=True)
class PromptSample:
    prompt_messages: list[dict[str, str]]      # for tokenizer.apply_chat_template
    seed: int
    category: str
    difficulty: str


def sample_prompt(
    rng: random.Random,
    *,
    categories: list[str] | None = None,
    difficulties: list[str] | None = None,
    ablate_dimensions: tuple[str, ...] = (),
) -> PromptSample:
    """Pick a random scenario and produce a single-step prompt.

    The reset is fresh — the prompt represents step 0 of an episode.
    """
    cats = list(categories or CATEGORIES)
    diffs = list(difficulties or DIFFICULTIES)
    seed = rng.randint(0, 1_000_000)
    cat = rng.choice(cats)
    diff = rng.choice(diffs)

    env = AriaEnv(ablate_dimensions=ablate_dimensions)
    obs = env.reset(seed=seed, category=cat, difficulty=diff)

    msgs = build_prompt(obs)
    # Tag the system message with the seed header so reward_fn can recover it.
    msgs[0]["content"] = (
        encode_prompt_seed_header(seed, cat, diff)
        + "\n"
        + msgs[0]["content"]
    )
    return PromptSample(prompt_messages=msgs, seed=seed, category=cat, difficulty=diff)


def trajectory(
    pick_action,                              # callable: obs -> AriaAction
    *,
    seed: int,
    category: str,
    difficulty: str,
    max_steps: int = 50,
    ablate_dimensions: tuple[str, ...] = (),
) -> list[tuple[AriaObservation, AriaAction, float]]:
    """Run a complete episode and return (obs, action, reward) triples.

    Used for evaluation + qualitative plotting. The pick_action callable can
    be a trained LLM wrapper, a baseline, or the scripted expert.
    """
    env = AriaEnv(ablate_dimensions=ablate_dimensions)
    obs = env.reset(seed=seed, category=category, difficulty=difficulty)
    out: list[tuple[AriaObservation, AriaAction, float]] = []
    for _ in range(max_steps):
        a = pick_action(obs)
        next_obs = env.step(a)
        out.append((obs, a, float(next_obs.reward or 0.0)))
        if next_obs.done:
            break
        obs = next_obs
    return out


__all__ = [
    "PromptSample",
    "encode_prompt_seed_header",
    "sample_prompt",
    "trajectory",
]
