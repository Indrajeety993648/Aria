"""FastAPI entrypoint — wraps AriaEnv via OpenEnv's create_app."""
from __future__ import annotations

from aria_contracts import AriaAction, AriaObservation
from openenv.core.env_server.http_server import create_app

from env_service.aria_env import AriaEnv


def build_app():
    """Build the FastAPI app. Called by uvicorn and by tests."""
    return create_app(
        env=lambda: AriaEnv(),
        action_cls=AriaAction,
        observation_cls=AriaObservation,
        env_name="aria-personal-manager-v1",
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "env_service.server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
