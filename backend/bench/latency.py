"""Latency benchmark for the ARIA voice → action → reward pipeline.

What this measures:
  - STT latency is MOCKED (faster-whisper isn't loaded in CI).
  - Intent + entity + context + state_encoder + decision_engine are REAL
    Python paths that run on every request in simulated mode.
  - TTS latency is MOCKED (piper isn't loaded in CI).
  - OpenEnv step() is REAL.

So this benchmark honestly reports:
  * the p50/p95/p99 cost of everything we control in-process, and
  * documented constants for the model-dependent stages.

On real hardware with faster-whisper-tiny + Piper loaded, STT and TTS
typically sit around 120ms and 90ms respectively (see voice-service/README).

Output is printed and also written to docs/LATENCY.md.

Usage:
    PYTHONPATH=backend python backend/bench/latency.py --n 200
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/services/orchestrator-service/src")

from aria_contracts import AriaAction, ActionId
from env_service.aria_env import AriaEnv
from orchestrator_service.context_resolver import ContextResolver
from orchestrator_service.decision_engine import DecisionEngine
from orchestrator_service.entity_extractor import EntityExtractor
from orchestrator_service.intent_classifier import IntentClassifier
from orchestrator_service.state_encoder import StateEncoder


# Model-dependent stages are declared, not timed here.
STATIC_BUDGET_MS = {
    "stt_whisper_tiny_en":   {"typical_ms": 120, "source": "voice-service/README, mock-mode bypasses model"},
    "tts_piper_first_byte":  {"typical_ms":  90, "source": "voice-service/README, streaming to first chunk"},
}


def p(name: str, samples_ms: list[float]) -> dict[str, float]:
    samples_ms = sorted(samples_ms)
    return {
        "stage": name,
        "n":    len(samples_ms),
        "mean": statistics.mean(samples_ms),
        "p50":  samples_ms[int(len(samples_ms) * 0.50)],
        "p95":  samples_ms[min(len(samples_ms) - 1, int(len(samples_ms) * 0.95))],
        "p99":  samples_ms[min(len(samples_ms) - 1, int(len(samples_ms) * 0.99))],
        "max":  samples_ms[-1],
    }


def time_it(n: int, fn: Callable[[], object]) -> list[float]:
    # Warm-up
    for _ in range(5):
        fn()
    ts: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000.0)
    return ts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument(
        "--out",
        type=str,
        default="docs/LATENCY.md",
        help="Markdown output path (repo-relative)",
    )
    args = parser.parse_args()

    # --- env setup ----------------------------------------------------------
    env = AriaEnv()
    obs = env.reset(seed=42, category="calendar_conflict", difficulty="medium")
    obs_dict = obs.model_dump()
    text = "resolve my 5pm conflict with riya's play"

    intent = IntentClassifier()
    entity = EntityExtractor()
    ctx = ContextResolver()
    enc = StateEncoder()
    dec = DecisionEngine(policy_mode="rule")

    # --- per-stage timings --------------------------------------------------
    stages: list[dict] = []
    stages.append(p("intent_classifier",   time_it(args.n, lambda: intent.classify(text))))
    stages.append(p("entity_extractor",    time_it(args.n, lambda: entity.extract(text))))
    stages.append(p("context_resolver",    time_it(args.n, lambda: ctx.resolve(text, obs_dict))))
    stages.append(p("state_encoder",       time_it(args.n, lambda: enc.encode(obs_dict))))
    stages.append(p("decision_engine",     time_it(args.n, lambda: dec.decide(text, obs_dict))))
    stages.append(p("env_step",            time_it(args.n, lambda: env.step(AriaAction(action_id=ActionId.WAIT.value)))))

    # --- end-to-end realistic pipeline (intent→decide→step) ----------------
    def full_turn() -> None:
        _ = intent.classify(text)
        _ = entity.extract(text)
        _ = ctx.resolve(text, obs_dict)
        _ = enc.encode(obs_dict)
        action = dec.decide(text, obs_dict)
        env.step(action)

    stages.append(p("full_turn_in_proc", time_it(args.n, full_turn)))

    # --- render ------------------------------------------------------------
    repo_root = Path(__file__).resolve().parents[2]
    out_path = repo_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total_p95 = sum(s["p95"] for s in stages if s["stage"] != "full_turn_in_proc")
    budget_total = total_p95 + sum(v["typical_ms"] for v in STATIC_BUDGET_MS.values())

    lines: list[str] = []
    lines.append("# ARIA — voice pipeline latency")
    lines.append("")
    lines.append(f"_Measured {args.n} iterations per stage, warm caches, single thread, no GPU._")
    lines.append("")
    lines.append("## In-process stages (measured)")
    lines.append("")
    lines.append("| Stage | n | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for s in stages:
        lines.append(
            f"| `{s['stage']}` | {s['n']} | {s['p50']:.2f} | {s['p95']:.2f} | "
            f"{s['p99']:.2f} | {s['max']:.2f} |"
        )
    lines.append("")
    lines.append("## Model-dependent stages (documented budget)")
    lines.append("")
    lines.append("| Stage | typical (ms) | source |")
    lines.append("|---|---:|---|")
    for k, v in STATIC_BUDGET_MS.items():
        lines.append(f"| `{k}` | {v['typical_ms']} | {v['source']} |")
    lines.append("")
    lines.append("## Derived end-to-end p95")
    lines.append("")
    lines.append(f"- sum of in-process p95 stages (excluding `full_turn_in_proc`): **{total_p95:.2f} ms**")
    lines.append(
        f"- plus model-dependent budget (STT {STATIC_BUDGET_MS['stt_whisper_tiny_en']['typical_ms']}ms + "
        f"TTS first-byte {STATIC_BUDGET_MS['tts_piper_first_byte']['typical_ms']}ms): **{budget_total:.2f} ms**"
    )
    lines.append("")
    lines.append(
        f"- target per README § 6: **< 500 ms** — "
        f"{'✓ within budget' if budget_total < 500 else '⚠ exceeds budget'}"
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- STT / TTS numbers are quoted from the voice-service README; this bench does not load faster-whisper or piper weights.")
    lines.append("- `full_turn_in_proc` is the total per-turn overhead for everything we own in-process.")
    lines.append("- Regenerate with: `PYTHONPATH=backend python backend/bench/latency.py --n 200`")

    out_path.write_text("\n".join(lines) + "\n")

    # console
    print(f"\nwrote {out_path}\n")
    print(f"{'stage':<22}  {'p50':>8}  {'p95':>8}  {'p99':>8}")
    print("-" * 54)
    for s in stages:
        print(f"{s['stage']:<22}  {s['p50']:>8.2f}  {s['p95']:>8.2f}  {s['p99']:>8.2f}")
    print(f"\nderived e2e p95 (in-proc + STT+TTS budget): {budget_total:.1f} ms "
          f"({'WITHIN' if budget_total < 500 else 'EXCEEDS'} 500ms target)")

    # also dump raw JSON next to the md for CI diffing
    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "stages": stages,
                "static_budget_ms": STATIC_BUDGET_MS,
                "in_process_p95_sum_ms": total_p95,
                "derived_e2e_p95_ms": budget_total,
                "n": args.n,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
