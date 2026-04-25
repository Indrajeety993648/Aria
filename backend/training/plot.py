"""Plot generators for the hackathon submission.

Produces the four PNGs we cite in the README and blog:
  - reward_curve.png        — mean reward vs training step (full + ablated)
  - per_dim_breakdown.png   — bar chart of per-dimension reward at the end
  - category_winrate.png    — per-category mean reward, baselines vs trained
  - trajectory_strip.png    — qualitative example: 10 actions and their dim deltas

Inputs:
  - TRL GRPO writes a `trainer_state.json` with `log_history` containing
    {step, reward, kl, ...}
  - eval.py writes `eval_summary.json`
  - baselines/run_grade.py output

All plots use `figsize=(8, 4.5)`, labeled axes, grid, a single legend,
saved 200 DPI PNG.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _find_trainer_state(output_dir: Path) -> Path | None:
    """TRL/HF writes trainer_state.json into checkpoint-N/ and final/ subdirs,
    not into output_dir/ directly. Find the one with the longest log_history.
    """
    candidates = [output_dir / "trainer_state.json",
                  output_dir / "final" / "trainer_state.json"]
    candidates.extend(sorted(output_dir.glob("checkpoint-*/trainer_state.json")))
    best: Path | None = None
    best_len = -1
    for c in candidates:
        if not c.exists():
            continue
        try:
            n = len(json.loads(c.read_text()).get("log_history", []))
        except (json.JSONDecodeError, OSError):
            continue
        if n > best_len:
            best, best_len = c, n
    return best


def _load_log(output_dir: Path) -> tuple[list[int], list[float]]:
    """Read trainer_state.json from any checkpoint dir under `output_dir`
    and pull (step, reward) tuples from log_history."""
    p = _find_trainer_state(output_dir)
    if p is None:
        return [], []
    state = json.loads(p.read_text())
    history = state.get("log_history", [])
    steps, rewards = [], []
    for row in history:
        if "reward" in row and "step" in row:
            steps.append(row["step"])
            rewards.append(row["reward"])
    return steps, rewards


def _smooth(values: list[float], window: int = 10) -> list[float]:
    if len(values) < window:
        return values
    arr = np.array(values, dtype=float)
    return np.convolve(arr, np.ones(window) / window, mode="valid").tolist()


def reward_curve(full_dir: Path, ablate_dir: Path, out_path: Path) -> None:
    full_steps, full_rew = _load_log(full_dir)
    abl_steps, abl_rew = _load_log(ablate_dir)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if full_rew:
        s_rew = _smooth(full_rew)
        s_steps = full_steps[len(full_steps) - len(s_rew):]
        ax.plot(s_steps, s_rew, label="Full reward (6 dims)", linewidth=2.0)
    if abl_rew:
        s_rew = _smooth(abl_rew)
        s_steps = abl_steps[len(abl_steps) - len(s_rew):]
        ax.plot(s_steps, s_rew, label="Ablated (no relationship_health)",
                linewidth=2.0, linestyle="--")
    ax.set_xlabel("Training step")
    ax.set_ylabel("Mean episode reward (10-step window)")
    ax.set_title("ARIA — GRPO training: full reward vs. relationship-ablated")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def category_winrate(eval_full: Path, eval_abl: Path, baselines: Path | None,
                     out_path: Path) -> None:
    """Per-category bar chart: full / ablated / random / expert."""
    for label, p in [("--eval-full", eval_full), ("--eval-ablate", eval_abl)]:
        if not p.exists():
            raise SystemExit(
                f"\n  ✗ Missing {label}: {p}\n"
                f"    Did you run `eval.py` for this checkpoint first?\n"
                f"    Skip --eval-full / --eval-ablate to render only the\n"
                f"    training reward curve from trainer_state.json.\n"
            )
    full = json.loads(eval_full.read_text())
    abl = json.loads(eval_abl.read_text())
    baselines_data = json.loads(baselines.read_text()) if baselines and baselines.exists() else None

    cats = sorted({k.split("/")[0] for k in full.keys()})
    full_means = [np.mean([full[k]["mean"] for k in full if k.startswith(c)]) for c in cats]
    abl_means = [np.mean([abl[k]["mean"] for k in abl if k.startswith(c)]) for c in cats]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(cats))
    width = 0.22
    ax.bar(x - 1.5 * width, full_means, width, label="Trained (full reward)")
    ax.bar(x - 0.5 * width, abl_means, width, label="Trained (ablated)")
    if baselines_data:
        rand = baselines_data.get("per_policy_per_category", {}).get("random", {})
        exp = baselines_data.get("per_policy_per_category", {}).get("expert", {})
        ax.bar(x + 0.5 * width, [rand.get(c, 0) for c in cats], width, label="Random")
        ax.bar(x + 1.5 * width, [exp.get(c, 0) for c in cats], width, label="Scripted expert")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right")
    ax.set_ylabel("Mean episode reward")
    ax.set_title("ARIA — per-category mean reward, trained agent vs. baselines")
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="lower right", fontsize=9)
    ax.axhline(0, color="black", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--full-dir", required=True, type=Path)
    p.add_argument("--ablate-dir", required=True, type=Path)
    p.add_argument("--eval-full", type=Path, default=None)
    p.add_argument("--eval-ablate", type=Path, default=None)
    p.add_argument("--baselines", type=Path, default=None)
    p.add_argument("--out-dir", type=Path, default=Path("docs/assets"))
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Friendly check up-front so we don't waste user's time
    for label, d in [("--full-dir", args.full_dir), ("--ablate-dir", args.ablate_dir)]:
        if _find_trainer_state(d) is None:
            print(
                f"\n  ⚠  No trainer_state.json under {label}={d}\n"
                f"     (searched: {d}/, {d}/final/, {d}/checkpoint-*/)\n"
                f"     This usually means the training run hasn't finished yet, OR\n"
                f"     you're pointing at the wrong directory. Run `train_grpo.py`\n"
                f"     first; the script writes trainer_state.json incrementally.\n"
            )

    reward_curve(args.full_dir, args.ablate_dir, args.out_dir / "reward_curve.png")
    print(f"wrote {args.out_dir / 'reward_curve.png'}")

    if args.eval_full and args.eval_ablate:
        category_winrate(
            args.eval_full, args.eval_ablate, args.baselines,
            args.out_dir / "category_winrate.png",
        )
        print(f"wrote {args.out_dir / 'category_winrate.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
