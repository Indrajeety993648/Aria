"""Deterministic RNG helpers.

We use `numpy.random.Generator` (PCG64), which is bit-identical across
numpy minor versions — unlike Python's `random` module which doesn't
promise cross-version stability.
"""
from __future__ import annotations

from typing import Iterable, Sequence, TypeVar

import numpy as np

T = TypeVar("T")


def make_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def choice(rng: np.random.Generator, seq: Sequence[T]) -> T:
    idx = int(rng.integers(0, len(seq)))
    return seq[idx]


def sample(rng: np.random.Generator, seq: Sequence[T], k: int) -> list[T]:
    if k > len(seq):
        raise ValueError(f"Cannot sample {k} from {len(seq)}")
    idx = rng.choice(len(seq), size=k, replace=False)
    return [seq[int(i)] for i in idx]


def uniform(rng: np.random.Generator, low: float, high: float) -> float:
    return float(rng.uniform(low, high))


def integer(rng: np.random.Generator, low: int, high: int) -> int:
    """Inclusive-exclusive [low, high)."""
    return int(rng.integers(low, high))


def pref_vector(rng: np.random.Generator, length: int = 64) -> list[float]:
    v = rng.normal(0.0, 0.3, size=length)
    return [float(x) for x in v]
