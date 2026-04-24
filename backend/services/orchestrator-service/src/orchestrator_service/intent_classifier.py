"""Low-latency intent classifier with optional ONNX model support."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from aria_contracts import ActionId


@dataclass(slots=True)
class IntentResult:
    action_id: int
    confidence: float
    source: str


class IntentClassifier:
    """Intent classifier with heuristic fallback.

    If `INTENT_MODEL_PATH` is set and onnxruntime is available, a model is used.
    Otherwise a fast keyword-based classifier is used.
    """

    def __init__(self) -> None:
        self._min_conf = float(os.environ.get("INTENT_MIN_CONF", "0.25"))
        self._model = _OnnxIntentModel(os.environ.get("INTENT_MODEL_PATH"))

    def classify(self, text: str, context: dict[str, Any] | None = None) -> IntentResult:
        _ = context
        if self._model.available:
            result = self._model.predict(text)
            if result is not None:
                return result
        return _heuristic_intent(text)

    @property
    def min_confidence(self) -> float:
        return self._min_conf


# -----------------------------------------------------------------------------
# Heuristic fallback
# -----------------------------------------------------------------------------


_KEYWORDS: dict[ActionId, list[str]] = {
    ActionId.SEND_MSG: ["send", "message", "text", "email", "notify"],
    ActionId.SCHEDULE: ["schedule", "book", "set up", "add to calendar"],
    ActionId.RESCHEDULE: ["reschedule", "move", "push back", "change the time"],
    ActionId.CANCEL: ["cancel", "call off", "drop the meeting"],
    ActionId.DELEGATE: ["delegate", "assign", "hand off"],
    ActionId.DRAFT_REPLY: ["reply", "draft reply", "respond", "write back"],
    ActionId.SET_REMINDER: ["remind", "set a reminder"],
    ActionId.PURCHASE: ["buy", "purchase", "order"],
    ActionId.RESOLVE_CONFLICT: ["conflict", "double booked", "overlapping"],
    ActionId.ASK_USER: ["ask me", "check with me", "clarify"],
    ActionId.DECLINE_INVITE: ["decline", "reject", "turn down"],
    ActionId.PROPOSE_ALTERNATIVE: ["propose", "suggest another", "offer another time"],
    ActionId.BATCH_ACTION: ["batch", "clear my inbox", "handle all"],
    ActionId.WAIT: ["wait", "hold off", "do nothing"],
    ActionId.ESCALATE: ["escalate", "raise", "loop in"],
}


def _heuristic_intent(text: str) -> IntentResult:
    norm = " ".join(text.lower().split())
    if "reply" in norm or "draft reply" in norm or "respond" in norm:
        return IntentResult(action_id=int(ActionId.DRAFT_REPLY), confidence=0.8, source="heuristic")
    if "reschedule" in norm:
        return IntentResult(action_id=int(ActionId.RESCHEDULE), confidence=0.8, source="heuristic")
    best: tuple[int, float] = (int(ActionId.WAIT), 0.0)

    for action, patterns in _KEYWORDS.items():
        score = 0
        for p in patterns:
            if p in norm:
                score += 1
        if score > best[1]:
            best = (int(action), float(score))

    confidence = 0.5 if best[1] > 0 else 0.2
    return IntentResult(action_id=best[0], confidence=confidence, source="heuristic")


# -----------------------------------------------------------------------------
# Optional ONNX model
# -----------------------------------------------------------------------------


class _OnnxIntentModel:
    def __init__(self, model_path: str | None) -> None:
        self.available = False
        self._session = None
        self._input_name = None
        self._labels = list(ActionId)

        if not model_path:
            return
        try:
            import onnxruntime as ort  # type: ignore
            import numpy as np  # type: ignore

            self._np = np
            self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            self._input_name = self._session.get_inputs()[0].name
            self.available = True
        except Exception:
            self.available = False

    def predict(self, text: str) -> IntentResult | None:
        if not self.available or self._session is None or self._input_name is None:
            return None

        # Simple bag-of-chars encoding for now. Replace with proper tokenizer for real model.
        vec = _encode_text(text)
        np = self._np
        inputs = {self._input_name: np.asarray([vec], dtype=np.float32)}
        outputs = self._session.run(None, inputs)
        if not outputs:
            return None
        logits = outputs[0]
        scores = list(logits[0])
        if len(scores) < len(self._labels):
            return None
        scores = scores[: len(self._labels)]
        idx = int(max(range(len(scores)), key=lambda i: scores[i]))
        confidence = float(_softmax_conf(scores)[idx])
        return IntentResult(action_id=int(self._labels[idx]), confidence=confidence, source="onnx")


def _encode_text(text: str, size: int = 128) -> list[float]:
    norm = text.lower()
    vec = [0.0] * size
    for ch in norm:
        vec[ord(ch) % size] += 1.0
    total = sum(vec) or 1.0
    return [v / total for v in vec]


def _softmax_conf(scores: list[float]) -> list[float]:
    import math

    mx = max(scores)
    exps = [math.exp(s - mx) for s in scores]
    total = sum(exps) or 1.0
    return [e / total for e in exps]


__all__ = ["IntentClassifier", "IntentResult"]
