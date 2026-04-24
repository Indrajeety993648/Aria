# ARIA — Agentic Real-time Intelligent Assistant

> **Your AI Chief of Staff, not another chatbot.** Built for **Meta PyTorch OpenEnv Hackathon 2026**, Theme #3 (World Modeling) — tasks 3.1 Professional + 3.2 Personalized.

ARIA is a voice-first personal manager shipped as both **a product** and **an OpenEnv RL environment**. The environment — `aria-personal-manager-v1` — is the headline deliverable: judges can `POST /reset` → `POST /step` → `GET /state` against a Docker container without reading a line of our code.

## Repository layout

```
Aria/
├── backend/
│   ├── services/              # 5 microservices
│   │   ├── env-service/         # OpenEnv server — THE deliverable
│   │   ├── orchestrator-service/# Agent loop + tool dispatch
│   │   ├── voice-service/       # STT (Whisper) + TTS (Piper)
│   │   ├── memory-service/      # Qdrant + SQLite
│   │   └── gateway-service/     # Public REST/WS door
│   ├── packages/              # Shared Python libraries
│   │   ├── aria-contracts/      # Pydantic schemas (the contract)
│   │   ├── aria-scenarios/      # Deterministic scenario generators
│   │   └── aria-rewards/        # 6-dim reward function
│   ├── tests/                 # Env tests + fixtures + baselines
│   ├── baselines/             # random / expert / do-nothing policies
│   └── docker-compose.yml     # Topology
├── frontend/                  # Next.js 15 voice-first UI
├── skills.md                  # Sub-team lanes (read this first)
└── Makefile                   # Developer entrypoint
```

## Quick start

```bash
cp .env.example .env
make build         # docker compose build
make up            # docker compose up -d
```

Visit `http://localhost:3000` for the frontend, `http://localhost:8001/docs` for the env OpenAPI, and `http://localhost:8000/docs` for the gateway.

**Mock mode (default):** no API keys, no model downloads. Everything runs offline. Set `MOCK_VOICE=0` and `MOCK_LLM=0` in `.env` (plus `ARIA_DOWNLOAD_MODELS=1`) to switch to real models.

## Running the env by itself (how judges will)

```bash
docker build -t aria-env backend/services/env-service
docker run -p 8001:8001 aria-env
curl -X POST http://localhost:8001/reset -H 'Content-Type: application/json' -d '{"seed": 42}'
```

## Env specification

- **Name:** `aria-personal-manager-v1`
- **Observation:** Pydantic `AriaObservation` with `calendar` (30-day × 24-hour matrix), `inbox` (priority queue), `relationships` (graph), `preferences` (vector), `pending_tasks`, `time`, `location`. Inherits `done`, `reward`, `metadata` from OpenEnv's `Observation`.
- **Action:** Pydantic `AriaAction` with `action_id: int ∈ [0,14]` mapped to an `ActionId` IntEnum (see `aria-contracts`), plus optional `target_id` and free-form `payload`.
- **State:** Pydantic `AriaState` with `scenario_category`, `difficulty`, `seed`, `step_count`, `max_steps=50`, and a live `reward_so_far: RewardBreakdown`.
- **Reward:** weighted sum of six dimensions — task completion (0.25), relationship health (0.20), user satisfaction (0.20), time efficiency (0.15), conflict resolution (0.15), safety (0.05). See `aria-rewards/compute.py` for the formula.
- **Scenarios:** 6 categories × 3 difficulties, all deterministic from seed. Generators in `aria-scenarios/generators/`.

## What judges should run

```bash
make test-env           # full env grader suite (<60s, no containers required)
make grade              # runs random + scripted-expert + do-nothing baselines,
                        # prints reward table — expected: expert > random > nothing
```

## Honest limitations

- **No trained policy.** We ship scripted baselines, not a PPO-trained agent. Training needs GPU hours outside this repo's scope. The env is fully learnable; we welcome judges training their own.
- **Voice pipeline** defaults to mock; real models run when `ARIA_DOWNLOAD_MODELS=1`.
- **Gmail / Calendar integrations** are stubbed. Real OAuth is out of scope for hackathon judging and would break reproducibility on graders' machines.

## Development

Start here → [skills.md](./skills.md). Every contributor and every sub-agent reads it first.

---

*Built for Meta PyTorch OpenEnv Hackathon 2026 · Theme #3 · April 2026*
# Aria
