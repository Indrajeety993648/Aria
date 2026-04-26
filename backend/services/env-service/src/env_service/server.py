"""FastAPI entrypoint — wraps AriaEnv via OpenEnv's create_app."""
from __future__ import annotations

from aria_contracts import AriaAction, AriaObservation
from fastapi.responses import JSONResponse
from openenv.core.env_server.http_server import create_app

from env_service.aria_env import AriaEnv


def build_app():
    """Build the FastAPI app. Called by uvicorn and by tests."""
    app = create_app(
        env=lambda: AriaEnv(),
        action_cls=AriaAction,
        observation_cls=AriaObservation,
        env_name="aria-personal-manager-v1",
    )

    @app.get("/", include_in_schema=False)
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "name": "aria-personal-manager-v1",
                "description": "ARIA — relationship-aware personal-manager RL environment (OpenEnv).",
                "endpoints": {
                    "POST /reset": "start an episode (stateless)",
                    "POST /step": "take one action (stateless)",
                    "GET /state": "current state (stateless)",
                    "GET /schema": "action/observation/state JSON schemas",
                    "GET /health": "liveness probe",
                    "WS /ws": "stateful multi-step session",
                    "GET /docs": "interactive OpenAPI docs",
                },
                "links": {
                    "code": "https://github.com/Indrajeet-Yadav/Aria",
                    "blog": "https://huggingface.co/blog/indra123/aria-relationship-aware-agent",
                },
            }
        )

    return app


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "env_service.server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
