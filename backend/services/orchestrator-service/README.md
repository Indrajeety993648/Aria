# orchestrator-service

ARIA agent-loop microservice. Closes the loop between a user's natural-language
turn, an ARIA env action, and (stubbed) real-world tool calls.

- **Port:** 8002
- **Contracts:** `AgentTurnRequest`, `AgentTurnResponse`, `ToolCall` from `aria-contracts`
- **Upstream:** `env-service` via OpenEnv's stateful WebSocket endpoint (`/ws`)

## Endpoints

| Method | Path                     | Body / Query                          | Notes |
|--------|--------------------------|---------------------------------------|-------|
| POST   | `/turn`                  | `AgentTurnRequest`                    | Main entry point. Returns `AgentTurnResponse`. |
| POST   | `/session`               | `{seed?, category?, difficulty?}`     | Opens a new env WS session (reset). |
| DELETE | `/session/{session_id}`  | —                                     | Closes the WS session. |
| GET    | `/health`                | —                                     | `{status: "ok"}` |

## Modes

The request field `mode` selects behaviour.

### `mode="simulated"` (default)

1. `mapper.text_to_action(user_text)` → `AriaAction`.
2. `env_client.step(action)` over the env-service's persistent WebSocket session.
3. Build a `reply_text` from a small action-specific template.
4. Return `AgentTurnResponse` with `mapped_env_action` populated and `tool_calls=[]`.

### `mode="live"`

Same as simulated **plus** dispatches one or more stubbed tools
(`gmail_stub.send_email`, `calendar_stub.create_event`, `calendar_stub.reschedule_event`)
matching the action kind. Tool results are attached to `AgentTurnResponse.tool_calls`.

No real Gmail / Calendar traffic is ever sent. The stubs return canned data.

## LLM toggle

- `MOCK_LLM=1` (default, the only mode we ship): intent parsing is fully
  rule-based (`mapper.text_to_action`). Deterministic, offline, zero model weights.
- `MOCK_LLM=0` + `ANTHROPIC_API_KEY` set: optionally falls back to the
  Anthropic SDK for fuzzier parses. Import is lazy — the mock path keeps working
  even if `anthropic` is not installed.

## Environment variables

| Var                | Default                         | Meaning |
|--------------------|---------------------------------|---------|
| `ENV_SERVICE_URL`  | `http://env-service:8001`       | Base URL of env-service (WS is `ws://.../ws`). |
| `MOCK_LLM`         | `1`                             | `1` = rule-based mapper only. `0` = optional Anthropic SDK. |
| `ANTHROPIC_API_KEY`| unset                           | Required only if `MOCK_LLM=0`. |

## Run locally

```bash
pip install -e backend/packages/aria-contracts
pip install -e backend/services/orchestrator-service
MOCK_LLM=1 python -m orchestrator_service.server   # :8002
```

## Test

```bash
pytest backend/services/orchestrator-service/tests -q
```

Tests monkeypatch `EnvClient` with an in-process fake, so no env-service need
be running.
