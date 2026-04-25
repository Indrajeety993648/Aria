"""Replay golden-episode fixtures and assert byte-identical trajectories.

Each fixture (`backend/tests/fixtures/golden_episodes/*.json`) was produced
by `backend/tests/fixtures/generate_golden.py`. A drift here means the env
is no longer deterministic across machines — either a generator changed
(intentional → regenerate fixtures), or there's an accidental nondeterminism
source (unintentional → bug).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from aria_contracts import AriaAction, AriaObservation

FIXTURES_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "golden_episodes"
)
FIXTURES = sorted(FIXTURES_DIR.glob("*.json"))


def _obs_hash(obs: AriaObservation) -> str:
    payload = obs.model_dump(mode="json")
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def test_fixtures_are_committed() -> None:
    # Guardrail — if someone deletes the fixtures dir, fail loudly.
    assert FIXTURES, (
        f"No fixtures found in {FIXTURES_DIR}. Run "
        "`python backend/tests/fixtures/generate_golden.py` to regenerate."
    )


@pytest.mark.parametrize(
    "fixture_path",
    FIXTURES,
    ids=lambda p: p.stem if isinstance(p, Path) else str(p),
)
def test_replay_matches_fixture(fixture_path: Path) -> None:
    from env_service.aria_env import AriaEnv

    data = json.loads(fixture_path.read_text())
    meta = data["meta"]

    env = AriaEnv(max_steps=meta["max_steps"])
    obs = env.reset(
        seed=meta["seed"],
        category=meta["category"],
        difficulty=meta["difficulty"],
    )
    assert _obs_hash(obs) == data["reset_obs_sha256"], (
        f"reset observation drifted for {fixture_path.name}; "
        "regenerate fixture if the change was intentional."
    )

    for i, step in enumerate(data["steps"]):
        action = AriaAction(
            action_id=step["action"]["action_id"],
            target_id=step["action"]["target_id"],
            payload=step["action"]["payload"],
        )
        next_obs = env.step(action)
        got_hash = _obs_hash(next_obs)
        assert got_hash == step["obs_sha256"], (
            f"step {i} observation drifted for {fixture_path.name}: "
            f"expected {step['obs_sha256'][:12]}… got {got_hash[:12]}…"
        )
        if step["reward_breakdown"] is not None:
            assert next_obs.reward_breakdown is not None
            assert (
                next_obs.reward_breakdown.model_dump()
                == step["reward_breakdown"]
            ), f"reward drift at step {i} of {fixture_path.name}"
        assert bool(next_obs.done) == step["done"]
