"""PPO training stub — wires AriaEnv to a Gymnasium-compatible adapter so
stable-baselines3's PPO can train on it.

WHAT THIS IS:
  - A runnable scaffold, not a completed training run.
  - Demonstrates that the env is learnable and supports standard RL tooling.
  - On CPU, 100k steps takes ~30min; real convergence needs ~1M+ steps on GPU.

WHAT THIS ISN'T:
  - A trained checkpoint shipped with this repo.
  - A promise about convergence wall time.

USAGE:
    pip install stable-baselines3 gymnasium
    python backend/baselines/train_ppo.py --steps 50000 --category email_triage --out ./checkpoints/ppo_email.zip
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import gymnasium as gym
    from gymnasium import spaces
    import numpy as np
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_checker import check_env
except ImportError:
    print(
        "stable-baselines3 and gymnasium are not installed.\n"
        "This is a training stub — install with:\n"
        "    pip install stable-baselines3 gymnasium\n"
    )
    sys.exit(2)

from aria_contracts import ActionId, AriaAction
from aria_scenarios import CATEGORIES

from env_service.aria_env import AriaEnv


def _flatten_observation(obs) -> np.ndarray:
    """Flatten an AriaObservation into a fixed-length float vector.

    We use a lossy but deterministic projection:
      - counts of different world-state elements (scalar features)
      - first 64 preference dims
    Total: 64 + 16 = 80 dims.
    """
    close_sum = sum(r.closeness for r in obs.relationships)
    urgent_count = sum(1 for i in obs.inbox if i.urgency >= 0.85)
    overdue_count = sum(1 for t in obs.pending_tasks if t.deadline_hours < 0)
    open_high_tasks = sum(1 for t in obs.pending_tasks if t.priority >= 0.7 and t.status == "open")

    scalars = np.array(
        [
            obs.time / 24.0,
            len(obs.calendar) / 30.0,
            len(obs.inbox) / 50.0,
            urgent_count / 10.0,
            len(obs.relationships) / 10.0,
            close_sum / 10.0,
            len(obs.pending_tasks) / 20.0,
            overdue_count / 10.0,
            open_high_tasks / 10.0,
            (obs.step_count or 0) / max(1, obs.max_steps),
            float(obs.done),
            0.0, 0.0, 0.0, 0.0, 0.0,  # padding to 16
        ],
        dtype=np.float32,
    )
    prefs = np.array(obs.preferences, dtype=np.float32)
    return np.concatenate([prefs, scalars], axis=0)


class AriaGymEnv(gym.Env):
    """Thin Gymnasium adapter — returns Gymnasium's (obs, reward, terminated, truncated, info) tuple."""

    metadata = {"render_modes": []}

    def __init__(self, category: str = "email_triage", difficulty: str = "medium"):
        super().__init__()
        self._env = AriaEnv()
        self._category = category
        self._difficulty = difficulty
        self.action_space = spaces.Discrete(15)
        self.observation_space = spaces.Box(low=-10.0, high=10.0, shape=(80,), dtype=np.float32)
        self._last_obs = None

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        obs = self._env.reset(seed=seed, category=self._category, difficulty=self._difficulty)
        self._last_obs = obs
        return _flatten_observation(obs), {}

    def step(self, action: int):
        # Choose a reasonable target for actions that need one, so the agent
        # can actually get non-trivial rewards without learning target picking.
        target = None
        payload: dict = {}
        if action == ActionId.DRAFT_REPLY.value and self._last_obs and self._last_obs.inbox:
            urgent = [i for i in self._last_obs.inbox if i.urgency >= 0.7]
            target = (urgent or self._last_obs.inbox)[0].email_id
        elif action == ActionId.DELEGATE.value and self._last_obs and self._last_obs.pending_tasks:
            deleg = [t for t in self._last_obs.pending_tasks if t.delegatable and t.status == "open"]
            target = (deleg or self._last_obs.pending_tasks)[0].task_id
            payload["assignee_id"] = "c_report"
        elif action == ActionId.RESOLVE_CONFLICT.value:
            target = "conflict_personal"
        elif action == ActionId.PURCHASE.value and self._last_obs:
            t = next((t for t in self._last_obs.pending_tasks if t.task_id == "buy_gift"), None)
            target = t.task_id if t else None
            payload = {"amount": 500.0, "user_approved": True}
        elif action == ActionId.BATCH_ACTION.value and self._last_obs:
            payload["email_ids"] = [i.email_id for i in self._last_obs.inbox[:5]]

        obs = self._env.step(AriaAction(action_id=action, target_id=target, payload=payload))
        self._last_obs = obs
        reward = obs.reward or 0.0
        terminated = bool(obs.done)
        truncated = False
        return _flatten_observation(obs), float(reward), terminated, truncated, {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=50_000)
    parser.add_argument("--category", type=str, default="email_triage", choices=list(CATEGORIES))
    parser.add_argument("--difficulty", type=str, default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--out", type=str, default="ppo_aria.zip")
    args = parser.parse_args()

    env = AriaGymEnv(category=args.category, difficulty=args.difficulty)
    check_env(env, warn=True)

    model = PPO("MlpPolicy", env, verbose=1, n_steps=256, batch_size=64, learning_rate=3e-4)
    model.learn(total_timesteps=args.steps)
    model.save(args.out)
    print(f"saved → {args.out}")

    # Quick eval
    obs, _ = env.reset(seed=0)
    total = 0.0
    for _ in range(60):
        action, _ = model.predict(obs, deterministic=True)
        obs, r, term, trunc, _ = env.step(int(action))
        total += r
        if term or trunc:
            break
    print(f"eval (1 episode, greedy) total_reward={total:+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
