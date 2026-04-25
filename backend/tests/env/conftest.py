"""Shared fixtures for the env grader suite.

The suite is structured to run in two tiers:
  - default: pure-Python tests against `AriaEnv` and `build_app()` via the
    FastAPI TestClient. No network, no subprocess. Fast.
  - --run-http: additionally exercise tests that spin real HTTP servers or
    rely on long-running processes. Opt-in so `make test-env` stays under a
    minute for local iteration.
"""
from __future__ import annotations

import pytest
from aria_scenarios import CATEGORIES, DIFFICULTIES


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-http",
        action="store_true",
        default=False,
        help="Also run tests that spin HTTP/WebSocket servers.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "http: test requires --run-http (spins a real server)"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-http"):
        return
    skip = pytest.mark.skip(reason="needs --run-http")
    for item in items:
        if "http" in item.keywords:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# Shared data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def all_categories() -> tuple[str, ...]:
    return CATEGORIES


@pytest.fixture(scope="session")
def all_difficulties() -> tuple[str, ...]:
    return DIFFICULTIES


@pytest.fixture
def env():
    """A fresh AriaEnv. Import lazily so collection doesn't require the service."""
    from env_service.aria_env import AriaEnv

    return AriaEnv()
