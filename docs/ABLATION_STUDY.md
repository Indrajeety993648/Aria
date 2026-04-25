# ARIA — Ablation study spec

**Hypothesis:** the `relationship_health` dimension is what teaches the
agent to choose `PROPOSE_ALTERNATIVE` / `RESOLVE_CONFLICT` over unilateral
`CANCEL`. With it ablated, the agent reward-hacks: it learns to cancel
events to clear the calendar, leaving relationship state collapsing.

This is the headline experiment for the submission. The two reward curves
on the same axes are the proof that our novel signal isn't decorative.

## Experimental setup

| | Run A — full reward | Run B — ablated |
|---|---|---|
| Base model | Qwen/Qwen2.5-0.5B-Instruct | Qwen/Qwen2.5-0.5B-Instruct |
| Adapters | LoRA r=16 α=32 on q/k/v/o_proj | identical |
| Method | TRL `GRPOTrainer` | identical |
| Steps | 500 | 500 |
| `num_generations` | 4 | 4 |
| Per-device batch | 2 | 2 |
| Grad accum | 2 | 2 |
| Learning rate | 1e-6 | 1e-6 |
| KL β | 0.04 | 0.04 |
| Max prompt len | 1024 | 1024 |
| Max completion len | 128 | 128 |
| Seed | 42 | 42 |
| Train prompts | 2000 (pre-generated) | identical |
| Reward function | full 6-dim rubric | `ablate_dimensions=("relationship_health",)` |
| Hardware | T4-class GPU, single device, ≈6h wall | identical |

**The only difference between the two runs is the `--ablate relationship_health` flag** —
which goes through the `AriaCompositeRubric.ablate` parameter, zeros that
dimension's contribution to the surfaced reward (its `Rubric.last_score` still
computes for analysis), and propagates down to the env's `step()` return.

## Expected outcomes

1. Both runs converge on similar `task_completion` mean.
2. Run A's `relationship_health` contribution stays positive throughout training;
   Run B's collapses (the agent never "feels" that dimension).
3. Run A's qualitative trajectories show preferred actions: `PROPOSE_ALTERNATIVE`,
   `RESOLVE_CONFLICT`, `WARM`-toned `DRAFT_REPLY` to upset contacts.
4. Run B's qualitative trajectories show reward-hacking: heavy `CANCEL`,
   tone-blind replies, more cumulative cascading damage.
5. On the held-out evaluation across all 18 (category, difficulty) cells,
   Run A's mean reward beats Run B by **≥ 0.20** (about one full standard
   deviation of episode reward).

## Plots to ship

After both runs finish, generate these PNGs into `docs/assets/`:

1. **`reward_curve.png`** — Mean episode reward (10-step rolling) vs. training step.
   Two lines on the same axes (Run A solid, Run B dashed). Same y-range.
   Rendered by `backend/training/plot.py::reward_curve`.

2. **`per_dim_during_training.png`** — Six small subplots (one per reward
   dimension), each showing the dimension's per-rollout mean over training.
   Critical: shows that `relationship_health` flatlines for Run B as expected.

3. **`category_winrate.png`** — Per-(category, difficulty) bar chart of mean
   episode reward, with bars for {Run A, Run B, scripted_expert, random}.
   Rendered by `backend/training/plot.py::category_winrate`.

4. **`trajectory_strip.png`** — Qualitative side-by-side: same starting
   observation, two agents' first 8 actions and step-by-step rewards.
   Hand-pick a `calendar_conflict` medium scenario with a high-closeness
   conflict event.

## Script-level commands (tomorrow)

```bash
# 12:05 — kick off Run A
nohup python backend/training/train_grpo.py \
    --run-name aria-full \
    --steps 500 \
    --output-dir ./checkpoints/aria-full \
    > ./logs/run-a.log 2>&1 &

# 18:15 — kick off Run B (after Run A finishes; can pipeline if 2 GPUs)
nohup python backend/training/train_grpo.py \
    --run-name aria-ablate-rh \
    --ablate relationship_health \
    --steps 500 \
    --output-dir ./checkpoints/aria-ablate-rh \
    > ./logs/run-b.log 2>&1 &

# 23:00 — generate plots
python backend/training/eval.py --model-path ./checkpoints/aria-full/final --out-dir ./eval/full
python backend/training/eval.py --model-path ./checkpoints/aria-ablate-rh/final \
    --ablate relationship_health --out-dir ./eval/ablate
python backend/training/plot.py \
    --full-dir ./checkpoints/aria-full \
    --ablate-dir ./checkpoints/aria-ablate-rh \
    --eval-full ./eval/full/eval_summary.json \
    --eval-ablate ./eval/ablate/eval_summary.json \
    --baselines ./backend/baselines/baseline_metrics.json \
    --out-dir ./docs/assets
```

## Runtime checklist

- [ ] GPU access confirmed
- [ ] `pip install` completes for trl/transformers/peft/accelerate/bitsandbytes
- [ ] WANDB_API_KEY exported (or accept local-CSV-only logging)
- [ ] `mkdir -p checkpoints logs eval`
- [ ] Smoke-test 10 steps on Run A first (`--steps 10`) to catch bugs early
- [ ] Confirm reward function returns non-trivial values from a sample prompt
      (run `backend/training/reward_fn.py` adhoc with a hand-crafted
       prompt + completion)
- [ ] Pre-warm Qwen 0.5B model download before kicking off the long run
      (cuts ~5min off Run A startup)

## Failure modes + recoveries

**Reward goes flat → 0.0**: parser is rejecting all completions. Check
`backend/training/action_parser.py` regex. Re-test against
`backend/training/render_action(a)` round-trip.

**KL divergence explodes**: lower `lr` to 5e-7 and resume.

**OOM on T4**: lower `per_device_train_batch_size` to 1, raise
`gradient_accumulation_steps` to 4. Or pivot to Qwen2.5-0.5B with
`load_in_4bit=True` via bitsandbytes.

**Loss diverges past step ~100**: the reward distribution might be too
sparse. Lower `max_completion_length` so the model can't ramble outside
format.

**Run A and Run B converge to identical mean**: hypothesis didn't replicate.
Pivot framing in the blog: "we observe the agent eventually learns to game
either reward; the relationship-aware reward delays this by N steps and
produces qualitatively different terminal trajectories." Still publishable.
