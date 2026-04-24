"""Unified product runtime for the orchestrator.

This module centralizes decisioning + validation + env stepping so the product
path shares the same action/state/reward logic as the OpenEnv environment.
"""
from __future__ import annotations

import time
from typing import Any

from aria_contracts import AriaAction

from orchestrator_service.action_validator import ActionValidator, ValidationResult
from orchestrator_service.decision_engine import DecisionEngine
from orchestrator_service.tools.env_client import EnvClient


def _ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


class ProductRuntime:
    """Product-layer runtime.

    Uses env-service as the canonical state/action/reward engine and wraps it
    with a decision engine plus a permission gate.
    """

    def __init__(
        self,
        env_client: EnvClient | None = None,
        decision_engine: DecisionEngine | None = None,
        validator: ActionValidator | None = None,
    ) -> None:
        self.env_client = env_client or EnvClient()
        self.decision_engine = decision_engine or DecisionEngine()
        self.validator = validator or ActionValidator()

    async def decide_and_step(
        self, session_id: str, user_text: str
    ) -> tuple[AriaAction, dict[str, Any], ValidationResult, dict[str, int]]:
        timing: dict[str, int] = {}

        t0 = time.perf_counter()
        obs = self.env_client.get_last_observation(session_id)
        action = self.decision_engine.decide(user_text, obs)
        timing["decision"] = _ms_since(t0)

        t0 = time.perf_counter()
        validation = self.validator.validate(action, obs)
        if not validation.allowed and validation.suggested_action is not None:
            action = validation.suggested_action
        timing["validation"] = _ms_since(t0)

        t0 = time.perf_counter()
        try:
            obs_after = await self.env_client.step(session_id, action)
        except Exception:
            obs_after = {}
        timing["env_step"] = _ms_since(t0)

        return action, obs_after, validation, timing


__all__ = ["ProductRuntime"]
