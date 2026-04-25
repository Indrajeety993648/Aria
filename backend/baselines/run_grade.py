"""`make grade` — runs the three baseline policies over N episodes per category.

Prints a reward table and asserts the expert beats random by ≥30% mean reward
on medium difficulty. This is what a judge script is shaped like.

Usage:
    python backend/baselines/run_grade.py            # medium, 20 episodes
    python backend/baselines/run_grade.py --n 100    # 100 episodes per cell
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from statistics import mean, stdev

# Make `baselines` and `env_service` importable whether the script is invoked
# from the repo root (`python backend/baselines/run_grade.py`) or from
# `backend/` directly. Must run before any of our package imports.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from aria_contracts import AriaAction  # noqa: E402
from aria_scenarios import CATEGORIES  # noqa: E402

from baselines.policies import POLICIES  # noqa: E402
from env_service.aria_env import AriaEnv  # noqa: E402


def run_episode(policy_name: str, category: str, difficulty: str, seed: int) -> float:
    env = AriaEnv()
    obs = env.reset(seed=seed, category=category, difficulty=difficulty)
    total = 0.0
    rng = random.Random(seed + 10_000)
    policy = POLICIES[policy_name]
    steps = 0
    while not obs.done and steps < 100:
        act = policy(obs, rng)
        obs = env.step(act)
        total += obs.reward or 0.0
        steps += 1
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20, help="episodes per category")
    parser.add_argument(
        "--difficulty", type=str, default="medium", choices=["easy", "medium", "hard"]
    )
    parser.add_argument("--fail-below", type=float, default=0.30,
                        help="expected (expert - random) / |random + eps| >= this")
    args = parser.parse_args()

    header = f"\n{'Policy':<12}" + "".join(f"{c:>22}" for c in CATEGORIES) + f"{'MEAN':>10}"
    print(header)
    print("-" * len(header))

    means: dict[str, dict[str, float]] = {}
    for policy_name in ("do_nothing", "random", "expert"):
        row = f"{policy_name:<12}"
        cat_means: dict[str, float] = {}
        for category in CATEGORIES:
            rewards = [
                run_episode(policy_name, category, args.difficulty, seed=seed)
                for seed in range(args.n)
            ]
            m = mean(rewards)
            s = stdev(rewards) if len(rewards) > 1 else 0.0
            row += f"  {m:+.3f}±{s:4.2f}      "[:22]
            cat_means[category] = m
        overall = mean(cat_means.values())
        row += f"{overall:+.3f}"
        print(row)
        means[policy_name] = cat_means
        means[policy_name]["__overall__"] = overall

    expert = means["expert"]["__overall__"]
    rand = means["random"]["__overall__"]
    delta = expert - rand
    rel = delta / (abs(rand) + 1e-6)
    print(f"\nexpert − random = {delta:+.3f}  (relative {rel:+.1%})")
    print(f"expert − do_nothing = {expert - means['do_nothing']['__overall__']:+.3f}")

    if rel < args.fail_below:
        print(f"\nFAIL: relative gain {rel:+.1%} < {args.fail_below:+.1%}")
        return 1
    print("\nPASS: expert beats random by the required margin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
