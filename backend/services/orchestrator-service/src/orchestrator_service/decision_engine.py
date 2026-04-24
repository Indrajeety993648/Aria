"""Decision engine for the product runtime.

Selects an `AriaAction` using either a rule-based mapper or a lightweight
policy heuristic (placeholder for a real policy network).
"""
from __future__ import annotations

import os
from typing import Any

from aria_contracts import ActionId, AriaAction

from orchestrator_service.context_resolver import ContextResolver
from orchestrator_service.entity_extractor import EntityExtractor
from orchestrator_service.intent_classifier import IntentClassifier
from orchestrator_service.mapper import text_to_action
from orchestrator_service.state_encoder import StateEncoder


class DecisionEngine:
    """Policy selector for the product runtime."""

    def __init__(self, policy_mode: str | None = None) -> None:
        self.policy_mode = (policy_mode or os.environ.get("POLICY_MODE", "rule")).lower()
        self._encoder = StateEncoder()
        model_path = os.environ.get("POLICY_MODEL_PATH")
        self._policy = _OnnxPolicy(model_path, self._encoder) if self.policy_mode == "policy" else None
        self._intent = IntentClassifier()
        self._entities = EntityExtractor()
        self._context = ContextResolver()

    def decide(self, user_text: str, observation: dict[str, Any] | None = None) -> AriaAction:
        context = self._context.resolve(user_text, observation)
        if self.policy_mode == "policy":
            return self._policy_decide(user_text, observation)
        return self._classify_and_extract(user_text, observation, context)

    # ------------------------------------------------------------------
    # Placeholder policy: deterministic heuristics over the observation.
    # ------------------------------------------------------------------
    def _policy_decide(
        self, user_text: str, observation: dict[str, Any] | None
    ) -> AriaAction:
        if self._policy is not None:
            model_action = self._policy.predict_action(observation)
            if model_action is not None:
                return model_action
        if observation:
            action = self._heuristic_from_observation(observation)
            if action is not None:
                return action
        context = self._context.resolve(user_text, observation)
        return self._classify_and_extract(user_text, observation, context)

    def _classify_and_extract(
        self,
        user_text: str,
        observation: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> AriaAction:
        intent = self._intent.classify(user_text, context)
        if intent.confidence < self._intent.min_confidence:
            return text_to_action(user_text, observation)

        entities = self._entities.extract(user_text)
        target_id = entities.get("target_id") or context.get("suggested_target_id")
        payload: dict[str, Any] = {"user_text": user_text, "entities": entities}
        if context:
            payload["context"] = context
        return AriaAction(action_id=int(intent.action_id), target_id=target_id, payload=payload)

    def _heuristic_from_observation(
        self, observation: dict[str, Any]
    ) -> AriaAction | None:
        inbox = observation.get("inbox") or []
        urgent = [m for m in inbox if m.get("urgency", 0.0) >= 0.8]
        if urgent:
            top = urgent[0]
            return AriaAction(
                action_id=int(ActionId.DRAFT_REPLY),
                target_id=top.get("email_id"),
                payload={"user_text": "auto: draft reply to urgent email"},
            )

        calendar = observation.get("calendar") or []
        conflict = _find_first_conflict(calendar)
        if conflict is not None:
            return AriaAction(
                action_id=int(ActionId.RESOLVE_CONFLICT),
                target_id=conflict,
                payload={"user_text": "auto: resolve detected calendar conflict"},
            )

        tasks = observation.get("pending_tasks") or []
        delegatable = [t for t in tasks if t.get("delegatable") and not t.get("assignee_id")]
        if delegatable:
            top = delegatable[0]
            return AriaAction(
                action_id=int(ActionId.DELEGATE),
                target_id=top.get("task_id"),
                payload={"user_text": "auto: delegate a delegatable task"},
            )

        return None


def _find_first_conflict(calendar: list[dict[str, Any]]) -> str | None:
    day0 = [e for e in calendar if e.get("day_offset", 0) == 0]
    for i, a in enumerate(day0):
        a_start = float(a.get("start_hour", 0.0))
        a_end = float(a.get("end_hour", 0.0))
        for b in day0[i + 1 :]:
            b_start = float(b.get("start_hour", 0.0))
            b_end = float(b.get("end_hour", 0.0))
            if a_start < b_end and b_start < a_end:
                return a.get("event_id") or b.get("event_id")
    return None


class _OnnxPolicy:
    """Optional ONNX policy inference hook.

    This is a lightweight bridge: if onnxruntime or numpy are unavailable, the
    policy simply reports itself as inactive and callers fall back to heuristics.
    """

    def __init__(self, model_path: str | None, encoder: StateEncoder) -> None:
        self._model_path = model_path
        self._session = None
        self._input_name = None
        self._input_size = None
        self._np = None
        self._encoder = encoder

        if not model_path:
            return
        try:
            import onnxruntime as ort  # type: ignore
            import numpy as np  # type: ignore

            self._np = np
            self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            self._input_name = self._session.get_inputs()[0].name
            shape = self._session.get_inputs()[0].shape
            self._input_size = int(shape[-1]) if shape and shape[-1] else None
        except Exception:
            self._session = None
            self._input_name = None
            self._input_size = None
            self._np = None

    def predict_action(self, observation: dict[str, Any] | None) -> AriaAction | None:
        if observation is None or self._session is None or self._input_name is None:
            return None

        vec = self._encoder.encode(observation)
        if self._input_size:
            if len(vec) < self._input_size:
                vec = vec + [0.0] * (self._input_size - len(vec))
            elif len(vec) > self._input_size:
                vec = vec[: self._input_size]

        np = self._np
        if np is None:
            return None

        inputs = {self._input_name: np.asarray([vec], dtype=np.float32)}
        outputs = self._session.run(None, inputs)
        if not outputs:
            return None
        logits = outputs[0]
        try:
            scores = list(logits[0])
        except Exception:
            return None
        if len(scores) < len(ActionId):
            return None
        scores = scores[: len(ActionId)]
        action_id = int(max(range(len(scores)), key=lambda i: scores[i]))
        return AriaAction(
            action_id=action_id,
            target_id=None,
            payload={"user_text": "auto: policy", "policy_model": self._model_path},
        )


__all__ = ["DecisionEngine"]
