"""TRL GRPO fine-tune of Qwen 2.5 0.5B-Instruct on the ARIA env.

Runs on a single T4-class GPU in ~6 hours for 500 steps with our defaults.

Usage:
  python backend/training/train_grpo.py \
      --run-name full \
      --steps 500 \
      --output-dir ./checkpoints/aria-grpo-full

  # Ablation run — relationship_health dimension removed from reward
  python backend/training/train_grpo.py \
      --run-name ablate-rh \
      --ablate relationship_health \
      --steps 500 \
      --output-dir ./checkpoints/aria-grpo-ablate-rh

Outputs:
  - LoRA adapters in `--output-dir`
  - wandb run (if WANDB_API_KEY is set; otherwise local CSV in `--output-dir`)
  - Local CSV `training_log.csv` always written for offline plotting
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

# Make sibling packages importable when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "env-service" / "src"))

from .reward_fn import make_reward_fn  # noqa: E402
from .rollout import sample_prompt  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--run-name", type=str, default="aria-grpo-full")
    p.add_argument("--model-id", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--output-dir", type=str, default="./checkpoints/aria-grpo")
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--num-generations", type=int, default=4,
                   help="GRPO rollouts per prompt (default 4)")
    p.add_argument("--lr", type=float, default=1e-6)
    p.add_argument("--kl-beta", type=float, default=0.04)
    p.add_argument("--max-prompt-len", type=int, default=1024)
    p.add_argument("--max-completion-len", type=int, default=128)
    p.add_argument("--per-device-batch", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=2)
    p.add_argument("--ablate", action="append", default=[],
                   help="Dimension to ablate (zero out) in the reward. "
                        "Repeat for multiple. Use 'relationship_health' for the headline ablation.")
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--num-prompts", type=int, default=2000,
                   help="Number of unique training prompts to pre-generate")
    p.add_argument("--wandb-project", type=str, default="aria-openenv-hackathon")
    return p.parse_args()


def _build_dataset(args: argparse.Namespace, ablate: tuple[str, ...]):
    """Pre-generate `num_prompts` random scenario prompts, in chat-template form.

    GRPO consumes prompts; rewards come from the env at training time via
    `reward_fn`. Pre-generation is fine because the env is deterministic
    given seed + category + difficulty.
    """
    from datasets import Dataset

    rng = random.Random(args.seed)
    rows: list[dict] = []
    for _ in range(args.num_prompts):
        sample = sample_prompt(rng, ablate_dimensions=ablate)
        rows.append({
            "prompt": sample.prompt_messages,  # list of {role, content}
            "seed": sample.seed,
            "category": sample.category,
            "difficulty": sample.difficulty,
        })
    return Dataset.from_list(rows)


def main() -> int:
    args = _parse_args()
    ablate = tuple(args.ablate)

    # Heavy imports deferred so the module is importable on a CPU-only box
    # (e.g. for unit-testing the prompt formatter).
    import torch
    from peft import LoraConfig
    from transformers import AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "args.json").write_text(json.dumps(vars(args), indent=2))

    print(f"=== ARIA GRPO === run={args.run_name} ablate={ablate or '()'}")
    print(f"    model={args.model_id}  steps={args.steps}  "
          f"generations={args.num_generations}  lr={args.lr}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_id, padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    dataset = _build_dataset(args, ablate)
    print(f"    train prompts: {len(dataset)}")

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )

    config = GRPOConfig(
        output_dir=str(output_dir),
        run_name=args.run_name,
        learning_rate=args.lr,
        per_device_train_batch_size=args.per_device_batch,
        gradient_accumulation_steps=args.grad_accum,
        max_steps=args.steps,
        save_steps=max(50, args.steps // 10),
        logging_steps=5,
        max_prompt_length=args.max_prompt_len,
        max_completion_length=args.max_completion_len,
        num_generations=args.num_generations,
        beta=args.kl_beta,
        bf16=torch.cuda.is_available()
            and torch.cuda.get_device_capability()[0] >= 8,
        fp16=torch.cuda.is_available()
            and torch.cuda.get_device_capability()[0] < 8,
        gradient_checkpointing=True,
        report_to=["wandb"] if os.getenv("WANDB_API_KEY") else ["none"],
        seed=args.seed,
    )

    reward_fn = make_reward_fn(ablate_dimensions=ablate)

    trainer = GRPOTrainer(
        model=args.model_id,
        reward_funcs=reward_fn,
        args=config,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=lora_config,
    )

    trainer.train()
    trainer.save_model(str(output_dir / "final"))
    print(f"=== done. checkpoints + metrics → {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
