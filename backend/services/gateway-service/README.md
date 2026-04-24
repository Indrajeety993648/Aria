# gateway-service

Single public door for ARIA. REST + WebSocket fan-out to the internal services.
**No business logic lives here.** Every endpoint proxies or multiplexes.

## What

- `POST /session`, `DELETE /session/{id}`, `POST /turn` — proxied to orchestrator
- `WS /ws/session/{session_id}` — multiplexes voice + orchestrator events into a
  single `GwAgentEvent` stream for the frontend
- `GET /health` — reports liveness of each upstream
- `GET /docs` — OpenAPI
- CORS open for `CORS_ORIGINS` (comma-separated env var, defaults to
  `http://localhost:3000`)

## Env vars

| Var | Default | Purpose |
| --- | --- | --- |
| `ORCHESTRATOR_URL` | `http://orchestrator-service:8002` | Orchestrator REST base URL |
| `VOICE_URL` | `http://voice-service:8003` | Voice service base URL |
| `ENV_URL` | `http://env-service:8001` | Env service base URL |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list |

## Run

```bash
pip install -e backend/services/gateway-service
python -m uvicorn gateway_service.server:app --port 8000
```

## Test

```bash
pytest backend/services/gateway-service/tests -q
```
