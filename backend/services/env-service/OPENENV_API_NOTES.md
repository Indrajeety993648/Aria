# OpenEnv API notes (verified 2026-04-24)

These notes capture exactly what we're committing to, so a future change in
`openenv-core` doesn't silently break things.

## Package

```
pip install openenv-core
```

Verified version: whichever the env-service Dockerfile pins (see that file).

## Imports we use

```python
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Action, Observation, State
from openenv.core.env_server.http_server import create_app
```

## Key contract

- `Environment[ActT, ObsT, StateT]` is a generic ABC.
- Abstract methods:
  - `reset(seed: int | None = None, episode_id: str | None = None, **kwargs) -> ObsT`
  - `step(action: ActT, timeout_s: float | None = None, **kwargs) -> ObsT`
  - `state: StateT` (property)
- `step()` returns **a single observation**, NOT a `(obs, reward, done, truncated, info)` tuple.
  The observation itself carries `done: bool` and `reward: float | None` (inherited from the
  `Observation` base class).
- `Action` and `Observation` are Pydantic `BaseModel` subclasses with `extra="forbid"` —
  every field must be declared.
- `State` has `extra="allow"` — subclasses can add fields freely.

## HTTP server

```python
app = create_app(
    env=lambda: AriaEnv(),            # factory, not instance
    action_cls=AriaAction,
    observation_cls=AriaObservation,
    env_name="aria-personal-manager-v1",
)
```

Returns a `FastAPI` app with routes:
- `POST /reset` — body `{seed?, episode_id?}`, returns `{observation, reward, done}` (stateless)
- `POST /step` — body `{action: {...}, timeout_s?}`, returns `{observation, reward, done}` (stateless)
- `GET /state` — returns current `State` dict (stateless)
- `GET /health` — returns `{status}`
- `GET /schema` — returns JSON schemas for action/observation/state
- `WS /ws` — **stateful session for multi-step episodes**

## Critical: HTTP is stateless, WebSocket is stateful

Every `POST /reset`, `POST /step`, `GET /state` request spins up a **fresh
Environment instance via the factory**. This means you cannot `POST /reset`
and then `POST /step` and expect the step to see the reset state.

For episodes spanning multiple steps, grader and training scripts must use the
`/ws` WebSocket endpoint. Messages follow this shape (see `openenv.core.env_server.types`):

```json
{"type": "reset", "data": {"seed": 42}}
{"type": "step",  "data": {"action_id": 8, "target_id": "conflict_personal"}}
{"type": "state"}
{"type": "close"}
```

Server replies with `{"type": "observation", "data": {...}}`, `{"type": "state", ...}`,
or `{"type": "error", ...}`. See `backend/tests/env/test_openenv_http.py` for an
executable example.

## Translation from README language

| README says | OpenEnv actually wants |
|---|---|
| `Discrete(15)` action space | `AriaAction(BaseModel)` with `action_id: int = Field(ge=0, le=14)` |
| Dict observation space | `AriaObservation(BaseModel)` with typed fields |
| `step()` returns `(obs, reward, done, truncated, info)` | `step()` returns `AriaObservation` with `done` and `reward` set on it |

Documented here so the hackathon write-up is accurate.
