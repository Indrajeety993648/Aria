# ARIA — Sub-Team Skills & Lanes

> This file is the constitution. Every sub-agent reads it before touching code. Violations (owning someone else's files, duplicating logic, importing across lanes) are reverts, not debates.

## Principles (apply to all lanes)

1. **Environment-first.** The OpenEnv env is what judges grade. Polish it before anything else.
2. **Contracts in, implementation out.** Every service imports `aria-contracts`. No hand-rolled DTOs crossing service boundaries.
3. **Mock by default.** Nothing requires external credentials or downloaded model weights for `docker compose up` to succeed. Real modes are opt-in via env flags.
4. **No dead code.** If a file isn't imported, delete it. If a feature isn't tested, it isn't done.
5. **Determinism is sacred for the env.** Same seed → byte-identical observations. Always.
6. **Write for the next agent.** Imperative commit subjects, docstrings on public APIs only, README per service with "what, how to run, how to test".

---

## Architecture (sole owner; shepherd of contracts)

**Mission:** Guard the shared contracts, the docker-compose topology, and the "no two services own the same thing" rule.

**Owns:**
- `backend/docker-compose.yml`
- Root `Makefile`
- `backend/packages/aria-contracts/**`
- `skills.md` (this file)
- Root `README.md`, `.env.example`, `.gitignore`
- `.github/workflows/**`

**Never touches:** service internals beyond their Dockerfile and port numbers.

**Definition of done:**
- `docker compose -f backend/docker-compose.yml build` completes on a clean machine in <10 min
- Every service imports `aria-contracts` and no other cross-service module
- `.github/workflows/ci.yml` green on main (tests + grade baseline)

---

## Env (highest-priority lane — this is what we're graded on)

**Mission:** Ship an OpenEnv-compliant `aria-personal-manager-v1` environment that a grader can `POST /reset` → `POST /step` → `GET /state` against without reading our code.

**Owns:**
- `backend/services/env-service/**`
- `backend/packages/aria-scenarios/**`
- `backend/packages/aria-rewards/**`
- `backend/tests/env/**`
- `backend/baselines/**`
- `backend/tests/fixtures/golden_episodes/**`

**Never touches:** voice, LLMs, frontend, orchestrator.

**Key files:**
- `env-service/src/env_service/aria_env.py` — `AriaEnv(Environment[AriaAction, AriaObservation, AriaState])`
- `env-service/src/env_service/server.py` — uses `openenv.core.env_server.http_server.create_app`
- `env-service/src/env_service/world.py` — `WorldModel` class (calendar, inbox, relationships)
- `env-service/src/env_service/actions.py` — 15 action handlers
- `aria_scenarios/generators/*.py` — one module per category
- `aria_rewards/compute.py` — 6-dim reward math

**Definition of done:**
- All tests in `backend/tests/env/` green
- Scripted-expert baseline mean reward > random baseline by ≥30% on medium difficulty
- Env container starts in <3 s
- `GET /schema` returns valid JSON schemas for action + observation + state
- `OPENENV_API_NOTES.md` in env-service documenting the installed OpenEnv version and API

---

## Backend-Orchestrator

**Mission:** Close the loop between a user's natural-language turn, an env action, and (stubbed) real-world tool calls.

**Owns:**
- `backend/services/orchestrator-service/**`

**Never touches:** env internals, reward math, STT/TTS models, UI.

**Key files:**
- `orchestrator-service/src/orchestrator_service/agent.py` — single agent loop
- `orchestrator-service/src/orchestrator_service/tools/` — `env_client.py`, `gmail_stub.py`, `calendar_stub.py`
- `orchestrator-service/src/orchestrator_service/mapper.py` — intent text → `AriaAction`

**Definition of done:**
- `POST /turn` converts text to `AgentTurnResponse` with both `reply_text` and `mapped_env_action`
- When `MOCK_LLM=1`, a deterministic rule-based mapper handles all 15 action keywords
- Round-trip <400 ms excluding LLM latency

---

## Voice

**Mission:** Sub-500 ms mic-in → text-out → speech-out pipeline with a mock mode that works offline.

**Owns:**
- `backend/services/voice-service/**`

**Never touches:** agent logic, env.

**Key files:**
- `voice-service/src/voice_service/stt.py` — `faster-whisper` wrapper with streaming
- `voice-service/src/voice_service/tts.py` — Piper wrapper
- `voice-service/src/voice_service/ws.py` — streaming WebSocket endpoint
- `voice-service/src/voice_service/mock.py` — returns canned `VoiceTranscript` + silent WAV

**Definition of done:**
- WS endpoint yields partial transcripts within 200 ms of speech end (real mode)
- TTS first byte <150 ms
- `MOCK_VOICE=1` path works with no model files present

---

## Memory

**Mission:** Persist and retrieve four namespaces — episodic, semantic, relationship, preference — across services.

**Owns:**
- `backend/services/memory-service/**`
- Qdrant sidecar config in `backend/docker-compose.yml` (coordinate with Architecture)

**Never touches:** anything else.

**Key files:**
- `memory-service/src/memory_service/vector.py` — Qdrant client wrapper
- `memory-service/src/memory_service/graph.py` — SQLite + NetworkX relationship graph
- `memory-service/src/memory_service/api.py` — FastAPI routes implementing `MemoryWrite` / `MemoryQuery`

**Definition of done:**
- Four namespaces readable/writable via the contracts
- p95 query latency <30 ms on 10 k items
- Falls back to in-memory stores if Qdrant is unreachable (logs a warning)

---

## Gateway

**Mission:** Single public door — REST + WS fan-out + CORS. Boring by design.

**Owns:**
- `backend/services/gateway-service/**`

**Never touches:** any business logic. If you feel a decision starting, push it into the orchestrator.

**Key files:**
- `gateway-service/src/gateway_service/main.py` — FastAPI app
- `gateway-service/src/gateway_service/ws_mux.py` — multiplexes voice + orchestrator + env events

**Definition of done:**
- `/ws/session/{id}` emits `GwAgentEvent` stream combining upstream events
- CORS open for `NEXT_PUBLIC_GATEWAY_URL`
- OpenAPI docs available at `/docs`

---

## Frontend

**Mission:** Voice-first UI that shows live transcript, agent reasoning trace, env state, and reward breakdown.

**Owns:**
- `/frontend/**`

**Never touches:** any `/backend` file. If a TS type is wrong, fix it in `aria-contracts` and regenerate.

**Key files:**
- `frontend/app/page.tsx` — single-page demo
- `frontend/components/VoiceDock.tsx` — push-to-talk + waveform
- `frontend/components/EnvInspector.tsx` — calendar + inbox view of current observation
- `frontend/components/RewardRadar.tsx` — live 6-dim reward radar chart
- `frontend/lib/ws.ts` — gateway WS client
- `frontend/lib/contracts/` — generated TS types mirroring `aria-contracts`

**Definition of done:**
- Connects to gateway WS, renders streaming transcript + live `RewardBreakdown`
- Runs with `npm run dev` against a mocked gateway if backend is down
- Deploys to Vercel from `/frontend` with no config hacks

---

## Testing

**Mission:** Make the env look bulletproof to a grader who has never seen our code. Write tests a stranger would trust.

**Owns:**
- `backend/tests/**` (except `env/` which the Env lane owns as DoD)
- `backend/tests/fixtures/**`

**Never touches:** implementation files (may read them).

**Definition of done:**
- `make grade` runs a mock judge that speaks only HTTP and prints a reward table
- Golden-episode fixtures committed and stable across Python minor versions
