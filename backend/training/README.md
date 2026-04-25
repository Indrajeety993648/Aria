# `backend/training/` — TRL GRPO harness

End-to-end pipeline for tomorrow's training run.

## Files

| File | What it does |
|---|---|
| `prompts.py` | `format_observation(obs)` → compact text summary; `build_prompt(obs)` → chat-template messages |
| `action_parser.py` | `parse_action(text)` → `(AriaAction, parse_failed)`; tolerant of LLM formatting variance |
| `rollout.py` | `sample_prompt(rng)` for training; `trajectory(pick_fn, ...)` for eval; embeds `[[ARIA_SEED ...]]` header so reward_fn can recreate the env |
| `reward_fn.py` | TRL-compatible callable: parses LLM output → steps env once → returns scalar reward. Honors `ablate_dimensions` |
| `train_grpo.py` | Main training entrypoint. Qwen 2.5 0.5B-Instruct + LoRA + GRPO via `trl.GRPOTrainer` |
| `eval.py` | Loads a checkpoint, runs trajectories across all 18 cells, writes `eval_summary.json` |
| `plot.py` | Generates PNGs for the README/blog from `trainer_state.json` + eval summaries |

## Tomorrow's commands

```bash
# Setup
pip install "transformers>=4.45" "trl>=0.13" "peft>=0.12" "accelerate>=1.0" \
            "bitsandbytes>=0.43" "datasets>=3.0" wandb matplotlib

# Run A — full reward (≈6h on T4)
python backend/training/train_grpo.py \
    --run-name aria-full \
    --steps 500 \
    --output-dir ./checkpoints/aria-full

# Run B — ablation (relationship_health zeroed)
python backend/training/train_grpo.py \
    --run-name aria-ablate-rh \
    --ablate relationship_health \
    --steps 500 \
    --output-dir ./checkpoints/aria-ablate-rh

# Evaluate both checkpoints
python backend/training/eval.py --model-path ./checkpoints/aria-full/final --out-dir ./eval/full
python backend/training/eval.py --model-path ./checkpoints/aria-ablate-rh/final --ablate relationship_health --out-dir ./eval/ablate

# Generate the submission plots
python backend/training/plot.py \
    --full-dir ./checkpoints/aria-full \
    --ablate-dir ./checkpoints/aria-ablate-rh \
    --eval-full ./eval/full/eval_summary.json \
    --eval-ablate ./eval/ablate/eval_summary.json \
    --baselines ./backend/baselines/baseline_metrics.json \
    --out-dir ./docs/assets
```

## Why GRPO

Group Relative Policy Optimization (DeepSeek-R1) needs no value head; ideal for
small models (Qwen 0.5B). Generates `num_generations=4` rollouts per prompt and
uses relative advantages — episodic-reward friendly. TRL ships it.

## Why Qwen 2.5 0.5B

Fits a T4 with bf16 + LoRA. Has solid chat template + Hindi tokens. Big enough
to learn structured ACTION/TARGET/PAYLOAD format consistently.

## The ablation thesis

`relationship_health` is the dimension we claim is novel. We zero its
contribution to the reward (its `Rubric.last_score` still computes for
introspection — only the weighted sum drops it) and re-train. Hypothesis:
the ablated agent will reward-hack via unilateral cancels and tone-blind
replies. The plot is the proof.
