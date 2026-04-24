"""aria_scenarios — deterministic scenario generators for ARIA.

Usage:
    spec = generate(category="calendar_conflict", difficulty="hard", seed=42)

Every spec is a pure function of (category, difficulty, seed). Same inputs →
byte-identical output across Python minor versions and across machines.
"""
from aria_scenarios.registry import CATEGORIES, DIFFICULTIES, generate
from aria_scenarios.spec import Objective, ScenarioSpec

__all__ = [
    "CATEGORIES",
    "DIFFICULTIES",
    "generate",
    "Objective",
    "ScenarioSpec",
]
__version__ = "0.1.0"
