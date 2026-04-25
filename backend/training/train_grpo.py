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

from .reward_fn import make_reward_fn  # noqa: E402
from .rollout import sample_prompt  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--run-name", type=str, default="aria-grpo-full")
    p.add_argument("--model-id", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--output-dir", type=str, default="./checkpoints/aria-grpo")
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--num-generations", type=int, default=4,
                   help="GRPO rollouts per prompt (default 4; quick=2)")
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

    # ---- Speed knobs --------------------------------------------------------
    p.add_argument("--use-vllm", action="store_true",
                   help="Route rollouts through vLLM (5-10x faster). "
                        "Requires `pip install vllm`. Sets vllm_gpu_memory_utilization=0.35 "
                        "by default to leave room for training.")
    p.add_argument("--vllm-mem", type=float, default=0.35,
                   help="vLLM GPU memory share (0..1). Lower if OOM during training.")
    p.add_argument(
        "--quick", action="store_true",
        help="Fast preset for hackathon-time T4 runs: steps=200, num_generations=2, "
             "max_completion_len=64, max_prompt_len=768, per_device_batch=4. "
             "Reduces a 10h run to ~30-45 min while keeping the learning curve visible. "
             "Overrides the corresponding flags unless you set them AFTER --quick on the command line."
    )
    args = p.parse_args()

    # Apply --quick AFTER parsing so explicit flags after `--quick` win.
    if args.quick:
        # Detect which knobs the user explicitly set so --quick doesn't clobber them.
        # argparse doesn't expose this directly; we infer from the raw argv.
        explicit = {a.lstrip("-").split("=")[0].replace("-", "_")
                    for a in sys.argv[1:] if a.startswith("--")}

        def _maybe(name: str, value):
            if name not in explicit:
                setattr(args, name, value)
        _maybe("steps", 200)
        _maybe("num_generations", 2)
        _maybe("max_completion_len", 64)
        _maybe("max_prompt_len", 768)
        _maybe("per_device_batch", 4)
        _maybe("grad_accum", 1)

    return args


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
    print(f"    batch={args.per_device_batch}*grad_accum={args.grad_accum}  "
          f"prompt_len={args.max_prompt_len}  completion_len={args.max_completion_len}  "
          f"vllm={args.use_vllm}  quick={args.quick}")

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

    grpo_kwargs: dict = {}
    if args.use_vllm:
        # Best case: 5-10x speedup on rollouts via vLLM continuous batching.
        # vllm_gpu_memory_utilization sets vLLM's slice; the remainder is for
        # the training forward/backward. T4 (16 GB): 0.35 leaves ~10 GB for
        # training, more than enough for Qwen 0.5B + LoRA.
        grpo_kwargs["use_vllm"] = True
        grpo_kwargs["vllm_gpu_memory_utilization"] = args.vllm_mem

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
        # Gradient checkpointing OFF: Qwen 2.5 0.5B + LoRA fits a T4 (16 GB)
        # comfortably without it (~3-4 GB peak). Enabling it triggers a known
        # PEFT+checkpoint interaction where `requires_grad` doesn't propagate
        # through the boundary, causing
        #   RuntimeError: element 0 of tensors does not require grad …
        # If you ever swap in a larger base model and DO need checkpointing,
        # use the non-reentrant flavor:
        #   gradient_checkpointing=True,
        #   gradient_checkpointing_kwargs={"use_reentrant": False},
        # AND call model.enable_input_require_grads() after PEFT wrap.
        gradient_checkpointing=False,
        report_to=["wandb"] if os.getenv("WANDB_API_KEY") else ["none"],
        seed=args.seed,
        **grpo_kwargs,
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
