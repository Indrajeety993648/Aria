"""Regenerate the golden-episode fixtures.

Run after intentional env changes; commit the diff.

    python backend/tests/fixtures/generate_golden.py

Design choices:
  - We use `scripted_expert` as the policy because it's deterministic and
    demonstrates the "expert beats random" story on short trajectories.
  - Episodes are capped at 10 steps: long enough to exercise multi-step
    dynamics (time decay, inbox aging), short enough to diff readably.
  - Observations are hashed (SHA-256 of canonical JSON), not stored raw,
    so a test failure points at the first step that drifted without
    bloating git history.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

# Make backend/ imports resolve when run as a script.
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "backend"))

from aria_contracts import AriaObservation  # noqa: E402
from baselines.policies import scripted_expert  # noqa: E402
from env_service.aria_env import AriaEnv  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "golden_episodes"
MAX_STEPS = 10

# (category, difficulty, seed) — chosen to cover different scenario shapes.
CASES: list[tuple[str, str, int]] = [
    ("calendar_conflict", "medium", 1),
    ("email_triage",      "easy",   0),
    ("delegation",        "medium", 2),
    ("shopping",          "medium", 3),
]


def _obs_hash(obs: AriaObservation) -> str:
    """Canonical JSON hash of the observation payload."""
    payload = obs.model_dump(mode="json")
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _record(category: str, difficulty: str, seed: int) -> dict:
    env = AriaEnv(max_steps=MAX_STEPS)
    obs = env.reset(seed=seed, category=category, difficulty=difficulty)
    rng = random.Random(seed + 10_000)
    steps: list[dict] = []
    for _ in range(MAX_STEPS):
        if obs.done:
            break
        action = scripted_expert(obs, rng)
        next_obs = env.step(action)
        steps.append(
            {
                "action": {
                    "action_id": action.action_id,
                    "target_id": action.target_id,
                    "payload": action.payload,
                },
                "obs_sha256": _obs_hash(next_obs),
                "reward_breakdown": (
                    next_obs.reward_breakdown.model_dump()
                    if next_obs.reward_breakdown is not None
                    else None
                ),
                "done": bool(next_obs.done),
            }
        )
        obs = next_obs

    return {
        "meta": {
            "category": category,
            "difficulty": difficulty,
            "seed": seed,
            "max_steps": MAX_STEPS,
            "policy": "scripted_expert",
        },
        "reset_obs_sha256": _obs_hash(env.reset(seed=seed, category=category, difficulty=difficulty)),
        "steps": steps,
    }


def main() -> int:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for category, difficulty, seed in CASES:
        data = _record(category, difficulty, seed)
        path = FIXTURES_DIR / f"{category}_{difficulty}_s{seed}.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        written.append(path)
        print(f"  wrote {path.relative_to(_ROOT)} — {len(data['steps'])} steps")

    print(f"\n{len(written)} fixture(s) written under "
          f"{FIXTURES_DIR.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
