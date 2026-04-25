"""pytest-asyncio config for voice-service tests."""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: run async tests via pytest-asyncio"
    )


# Auto-enable asyncio for @pytest.mark.asyncio tests without forcing `asyncio_mode = auto`.
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
