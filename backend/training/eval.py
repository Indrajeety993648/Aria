"""Post-training evaluation — runs a trained checkpoint over all 18
scenario × difficulty cells and writes a per-cell reward summary.

Outputs:
  - `eval_summary.json` — mean/std/n per (category, difficulty)
  - `trajectories/<cat>_<diff>_seed<n>.json` — first-N trajectories for inspection

Used by:
  - `plot.py` to render the post-training comparison curves
  - the video (we replay these trajectories on the demo UI)
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import product
from pathlib import Path
from statistics import mean, stdev

from tqdm.auto import tqdm

# Make sibling packages importable whether or not editable pip-installs took.
_REPO = Path(__file__).resolve().parents[2]
_BACKEND = _REPO / "backend"
for _p in (
    _REPO,
    _BACKEND / "packages" / "aria-contracts" / "src",
    _BACKEND / "packages" / "aria-scenarios" / "src",
    _BACKEND / "packages" / "aria-rewards" / "src",
    _BACKEND / "services" / "env-service" / "src",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from aria_contracts import AriaAction, AriaObservation
from aria_scenarios import CATEGORIES, DIFFICULTIES

from .action_parser import parse_action
from .prompts import build_prompt
from .rollout import trajectory


def _build_pick_fn(model_path: str, base_id: str):
    """Return a (obs -> AriaAction) callable backed by the trained model."""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    tok = AutoTokenizer.from_pretrained(base_id, padding_side="left")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    base = AutoModelForCausalLM.from_pretrained(
        base_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base, model_path)
    model.eval()

    @torch.no_grad()
    def pick(obs: AriaObservation) -> AriaAction:
        msgs = build_prompt(obs)
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt", truncation=True, max_length=1024).to(model.device)
        out = model.generate(
            **ids,
            max_new_tokens=128,
            do_sample=False,
            temperature=0.0,
            pad_token_id=tok.pad_token_id,
        )
        completion = tok.decode(out[0, ids.input_ids.shape[1]:], skip_special_tokens=True)
        action, _failed = parse_action(completion)
        return action
    return pick


def evaluate(model_path: str, base_id: str, *, n_seeds: int = 5,
             ablate: tuple[str, ...] = (), out_dir: str = "./eval_out") -> dict:
    # Friendly error if the checkpoint isn't there yet — common mistake when
    # someone runs eval before the training cells in the Colab notebook
    # have completed.
    cfg = Path(model_path) / "adapter_config.json"
    if not cfg.exists():
        msg = (
            f"\n\n  ✗ No trained checkpoint found at {model_path!r}\n"
            f"    (looked for {cfg})\n\n"
            f"    Did you run training first? In the Colab notebook, the order is:\n"
            f"      Cell 5 — Run A (full reward)        — ~6h on T4\n"
            f"      Cell 6 — Run B (ablate rh)          — ~6h on T4\n"
            f"      Cell 7 — eval ← THIS step\n"
            f"      Cell 8 — plot\n\n"
            f"    Cell 7 only works after cells 5 + 6 have completed and produced\n"
            f"    a `final/` directory containing `adapter_config.json`.\n"
        )
        raise SystemExit(msg)
    pick = _build_pick_fn(model_path, base_id)
    out = Path(out_dir)
    (out / "trajectories").mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    cells = list(product(CATEGORIES, DIFFICULTIES))
    total = len(cells) * n_seeds
    pbar = tqdm(total=total, desc="eval", unit="ep")
    for cat, diff in cells:
        rewards: list[float] = []
        for seed in range(n_seeds):
            trips = trajectory(
                pick, seed=seed, category=cat, difficulty=diff,
                ablate_dimensions=ablate,
            )
            ep_total = sum(r for _, _, r in trips)
            rewards.append(ep_total)
            traj_path = out / "trajectories" / f"{cat}_{diff}_seed{seed:02d}.json"
            traj_path.write_text(json.dumps([
                {"action_id": a.action_id, "target_id": a.target_id,
                 "payload": a.payload, "reward": r}
                for _, a, r in trips
            ], indent=2))
            pbar.set_postfix_str(f"{cat}/{diff} r={ep_total:+.2f}")
            pbar.update(1)
        summary[f"{cat}/{diff}"] = {
            "n": len(rewards),
            "mean": mean(rewards),
            "std": stdev(rewards) if len(rewards) > 1 else 0.0,
        }
    pbar.close()
    (out / "eval_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-path", required=True, help="Path to LoRA adapters")
    p.add_argument("--base-id", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--ablate", action="append", default=[])
    p.add_argument("--n-seeds", type=int, default=5)
    p.add_argument("--out-dir", default="./eval_out")
    args = p.parse_args()
    summary = evaluate(
        args.model_path, args.base_id,
        n_seeds=args.n_seeds, ablate=tuple(args.ablate), out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
