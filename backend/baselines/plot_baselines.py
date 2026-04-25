"""Generate baseline-only plots tonight (no GPU, no trained checkpoint).

Outputs four PNGs to docs/assets/, each labeled axes, grid, legend, single
figure, 200 DPI. After tomorrow's training run, the same axes are re-used by
backend/training/plot.py to overlay the trained agent.

Usage:
    PYTHONPATH=backend python backend/baselines/plot_baselines.py --n 30
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/services/env-service/src")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from aria_contracts import AriaAction  # noqa: E402
from aria_scenarios import CATEGORIES, DIFFICULTIES  # noqa: E402

from baselines.policies import POLICIES  # type: ignore[import-not-found]  # noqa: E402

from env_service.aria_env import AriaEnv  # noqa: E402


# ----------------------------------------------------------------------------
# Data collection
# ----------------------------------------------------------------------------


def run_episode(policy_name: str, category: str, difficulty: str, seed: int) -> tuple[float, list[float], dict[str, float]]:
    """Return (total_reward, per_step_rewards, per_dim_total)."""
    env = AriaEnv()
    obs = env.reset(seed=seed, category=category, difficulty=difficulty)
    rng = random.Random(seed + 10_000)
    policy = POLICIES[policy_name]
    per_step: list[float] = []
    dim_totals = {
        "task_completion": 0.0,
        "relationship_health": 0.0,
        "user_satisfaction": 0.0,
        "time_efficiency": 0.0,
        "conflict_resolution": 0.0,
        "safety": 0.0,
    }
    steps = 0
    while not obs.done and steps < 80:
        action = policy(obs, rng)
        obs = env.step(action)
        per_step.append(float(obs.reward or 0.0))
        if obs.reward_breakdown:
            for k in dim_totals:
                dim_totals[k] += float(getattr(obs.reward_breakdown, k))
        steps += 1
    return sum(per_step), per_step, dim_totals


def collect(n: int = 30, difficulty: str = "medium") -> dict:
    """Run all baselines × all categories × n seeds."""
    results: dict = {}
    for policy in ("do_nothing", "random", "expert"):
        results[policy] = {}
        for cat in CATEGORIES:
            ep_totals: list[float] = []
            per_step_arrays: list[list[float]] = []
            dim_means: list[dict[str, float]] = []
            for seed in range(n):
                total, per_step, dims = run_episode(policy, cat, difficulty, seed)
                ep_totals.append(total)
                per_step_arrays.append(per_step)
                dim_means.append(dims)
            results[policy][cat] = {
                "ep_totals": ep_totals,
                "per_step": per_step_arrays,
                "dim_means": {
                    k: mean(d[k] for d in dim_means) for k in dim_means[0]
                },
            }
    return results


# ----------------------------------------------------------------------------
# Plots
# ----------------------------------------------------------------------------


def plot_reward_curve(results: dict, out_path: Path) -> None:
    """Mean per-step reward over the course of an episode (smoothed)."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for policy in ("do_nothing", "random", "expert"):
        # Aggregate per-step across all categories and seeds, padding short eps with 0.
        all_steps: list[list[float]] = []
        for cat in CATEGORIES:
            for arr in results[policy][cat]["per_step"]:
                all_steps.append(arr)
        max_len = max(len(a) for a in all_steps)
        # Pad with NaN so means ignore variable-length tails.
        padded = np.full((len(all_steps), max_len), np.nan)
        for i, a in enumerate(all_steps):
            padded[i, :len(a)] = a
        means = np.nanmean(padded, axis=0)
        # Cumulative running mean (a clearer story than per-step noise)
        cumulative = np.cumsum(np.where(np.isnan(means), 0, means)) / np.arange(1, max_len + 1)
        ax.plot(np.arange(max_len), cumulative, label=policy.replace("_", " "),
                linewidth=2.0)
    ax.set_xlabel("Episode step")
    ax.set_ylabel("Cumulative-mean reward (per step)")
    ax.set_title("ARIA — baseline reward over an episode (medium, 30 seeds × 6 cats)")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_per_dim_breakdown(results: dict, out_path: Path) -> None:
    """Bar chart: per-dimension total reward, averaged across episodes, per policy."""
    DIMS = ["task_completion", "relationship_health", "user_satisfaction",
            "time_efficiency", "conflict_resolution", "safety"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(DIMS))
    width = 0.27
    for i, policy in enumerate(("do_nothing", "random", "expert")):
        # Average across categories
        means = []
        for d in DIMS:
            cat_means = [results[policy][cat]["dim_means"][d] for cat in CATEGORIES]
            means.append(mean(cat_means))
        offset = (i - 1) * width
        ax.bar(x + offset, means, width, label=policy.replace("_", " "))
    ax.set_xticks(x)
    ax.set_xticklabels([d.replace("_", "\n") for d in DIMS])
    ax.set_ylabel("Mean episode-total reward")
    ax.set_title("ARIA — per-dimension reward by policy (baselines)")
    ax.grid(True, alpha=0.3, axis="y")
    ax.axhline(0, color="black", linewidth=0.6)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_category_means(results: dict, out_path: Path) -> None:
    """Bar chart: mean episode total reward per (policy, category)."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cats = list(CATEGORIES)
    x = np.arange(len(cats))
    width = 0.27
    for i, policy in enumerate(("do_nothing", "random", "expert")):
        means = [mean(results[policy][cat]["ep_totals"]) for cat in cats]
        ax.bar(x + (i - 1) * width, means, width, label=policy.replace("_", " "))
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=25, ha="right")
    ax.set_ylabel("Mean episode total reward")
    ax.set_title("ARIA — per-category baseline performance")
    ax.grid(True, alpha=0.3, axis="y")
    ax.axhline(0, color="black", linewidth=0.6)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--difficulty", default="medium")
    p.add_argument("--out-dir", default="docs/assets")
    args = p.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Collecting baselines: {args.n} seeds × {len(CATEGORIES)} categories ({args.difficulty})…")
    results = collect(n=args.n, difficulty=args.difficulty)

    # Persist raw data for downstream use
    raw = {
        policy: {
            cat: {
                "ep_total_mean": mean(results[policy][cat]["ep_totals"]),
                "ep_total_std": stdev(results[policy][cat]["ep_totals"])
                    if len(results[policy][cat]["ep_totals"]) > 1 else 0.0,
                "dim_means": results[policy][cat]["dim_means"],
            }
            for cat in CATEGORIES
        }
        for policy in ("do_nothing", "random", "expert")
    }
    (out / "baseline_results.json").write_text(json.dumps(raw, indent=2))
    print(f"  → {out / 'baseline_results.json'}")

    plot_reward_curve(results, out / "baseline_reward_curve.png")
    print(f"  → {out / 'baseline_reward_curve.png'}")
    plot_per_dim_breakdown(results, out / "baseline_per_dim.png")
    print(f"  → {out / 'baseline_per_dim.png'}")
    plot_category_means(results, out / "baseline_category_means.png")
    print(f"  → {out / 'baseline_category_means.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
