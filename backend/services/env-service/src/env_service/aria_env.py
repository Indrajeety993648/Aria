"""AriaEnv — the OpenEnv `Environment` implementation that is THE hackathon deliverable.

- `reset(seed, episode_id, **kwargs)` — kwargs accepted: `category`, `difficulty`.
- `step(action, timeout_s)` — runs one action; returns observation with reward+done set.
- `state` — `AriaState` with hidden debug info (judges can inspect).
"""
from __future__ import annotations

import os
from typing import Any

from aria_contracts import (
    AriaAction,
    AriaObservation,
    AriaState,
    RewardBreakdown,
    ScenarioCategory,
    Difficulty,
)
from aria_rewards import StepContext, compute_step_reward, compute_terminal_reward
from aria_scenarios import CATEGORIES, DIFFICULTIES, generate
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata

from env_service.actions import dispatch
from env_service.observation import to_observation
from env_service.world import WorldModel


DEFAULT_MAX_STEPS = int(os.environ.get("ARIA_ENV_MAX_STEPS", "50"))
DEFAULT_DIFFICULTY: Difficulty = os.environ.get(
    "ARIA_ENV_DEFAULT_DIFFICULTY", "medium"
)  # type: ignore[assignment]


class AriaEnv(Environment[AriaAction, AriaObservation, AriaState]):
    """`aria-personal-manager-v1` — one simulated personal day per episode."""

    SUPPORTS_CONCURRENT_SESSIONS = True  # env instances are independent

    def __init__(
        self,
        *,
        default_category: ScenarioCategory | None = None,
        default_difficulty: Difficulty = DEFAULT_DIFFICULTY,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        super().__init__(transform=None, rubric=None)
        self.default_category: ScenarioCategory | None = default_category
        self.default_difficulty: Difficulty = default_difficulty
        self.max_steps = max_steps
        self._world: WorldModel | None = None
        self._episode_id: str | None = None

    # =========================================================================
    # OpenEnv interface
    # =========================================================================

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        **kwargs: Any,
    ) -> AriaObservation:
        category: ScenarioCategory = kwargs.get(
            "category", self.default_category or _pick_category(seed)
        )
        difficulty: Difficulty = kwargs.get("difficulty", self.default_difficulty)
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category {category!r}; valid: {CATEGORIES}")
        if difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty {difficulty!r}; valid: {DIFFICULTIES}")

        actual_seed = 0 if seed is None else int(seed)
        spec = generate(category, difficulty, seed=actual_seed)
        self._world = WorldModel.from_spec(spec, max_steps=self.max_steps)
        self._episode_id = episode_id

        return to_observation(
            self._world,
            reward_total=None,
            reward_breakdown=RewardBreakdown.zero(),
            done=False,
        )

    def step(
        self,
        action: AriaAction,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> AriaObservation:
        if self._world is None:
            raise RuntimeError("AriaEnv.step() called before reset()")

        world = self._world
        pre_snap = world.snapshot()

        outcome = dispatch(world, action)
        post_snap = world.snapshot()
        is_terminal = world.is_terminal()

        ctx = StepContext(
            action_id=action.action_id,
            target_id=action.target_id,
            payload=action.payload,
            scenario_category=world.scenario_category,
            difficulty=world.difficulty,
            step_count=world.step_count,
            max_steps=world.max_steps,
            is_terminal=is_terminal,
            pre=pre_snap,
            post=post_snap,
            outcome=outcome,
        )
        step_reward = compute_step_reward(ctx)

        # Accumulate running total
        world.reward_so_far = world.reward_so_far.accumulate(step_reward)

        # Terminal add-on
        combined_reward = step_reward
        if is_terminal:
            terminal = compute_terminal_reward(
                world.scenario_category,
                world.difficulty,
                world.terminal_state_dict(),
            )
            combined_reward = step_reward.accumulate(terminal)
            world.reward_so_far = world.reward_so_far.accumulate(terminal)

        return to_observation(
            world,
            reward_total=combined_reward.total,
            reward_breakdown=combined_reward,
            done=is_terminal,
        )

    @property
    def state(self) -> AriaState:
        if self._world is None:
            raise RuntimeError("state accessed before reset()")
        world = self._world
        return AriaState(
            episode_id=self._episode_id,
            step_count=world.step_count,
            scenario_category=world.scenario_category,  # type: ignore[arg-type]
            difficulty=world.difficulty,  # type: ignore[arg-type]
            seed=world.seed,
            max_steps=world.max_steps,
            reward_so_far=world.reward_so_far,
            hidden={
                "objectives": world.objectives,
                "hidden": world.hidden,
                "terminal_state_preview": world.terminal_state_dict(),
            },
        )

    def get_metadata(self) -> EnvironmentMetadata:
        return EnvironmentMetadata(
            name="aria-personal-manager-v1",
            description=(
                "ARIA — a voice-first personal AI manager environment. "
                "One episode = one simulated day. 15-action discrete space, "
                "6-dimensional reward. See README.md for the full spec."
            ),
            version="0.1.0",
            author="ARIA team — Meta PyTorch OpenEnv Hackathon 2026",
        )


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _pick_category(seed: int | None) -> ScenarioCategory:
    """Deterministically cycle through categories based on seed, so successive
    resets without an explicit category still cover the full scenario surface."""
    idx = 0 if seed is None else int(seed) % len(CATEGORIES)
    return CATEGORIES[idx]
