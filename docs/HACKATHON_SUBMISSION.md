# ARIA — Hackathon Submission Notes

## What to grade

The core deliverable is the OpenEnv environment `aria-personal-manager-v1` living in
`backend/services/env-service/` with its supporting packages:

- `backend/packages/aria-contracts/` — Pydantic schemas (17 tests, all green)
- `backend/packages/aria-rewards/` — 6-dimensional reward function (25 tests, all green)
- `backend/packages/aria-scenarios/` — 6 × 3 = 18 scenario generator branches (60 tests, all green)
- `backend/services/env-service/` — `AriaEnv` + OpenEnv FastAPI server
- `backend/tests/env/` — judge-facing tests (52 tests, all green)
- `backend/baselines/` — random / do_nothing / scripted_expert baselines

Running `make test` exercises the packages; `make test-env` runs the env grader suite; `make test-env-full --run-http` adds HTTP + WebSocket tests; `make grade` runs the baselines and asserts expert > random > do_nothing.

## Reproducing the baseline numbers

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate      # or fish: source .venv/bin/activate.fish
pip install -e backend/packages/aria-contracts
pip install -e backend/packages/aria-scenarios
pip install -e backend/packages/aria-rewards
pip install -e backend/services/env-service
pip install pytest httpx
pytest backend/packages backend/tests/env -q        # all green
PYTHONPATH=backend python backend/baselines/run_grade.py --n 20
```

Expected last line of `run_grade.py`: `PASS: expert beats random by the required margin` with a relative gain around +370%. See `backend/baselines/baseline_metrics.json` for the committed reference numbers.

## Running the env in isolation (how a grader would)

```bash
docker build -t aria-env -f backend/services/env-service/Dockerfile .
docker run --rm -p 8001:8001 aria-env
```

Then either:
- Hit stateless endpoints via HTTP (`/health`, `/schema`, `/reset` as one-shot)
- Open a WebSocket to `ws://localhost:8001/ws` and send `{"type":"reset",...}` / `{"type":"step",...}` messages

See `backend/services/env-service/OPENENV_API_NOTES.md` for the exact WS message shape and a critical note: **HTTP /reset and /step are stateless in OpenEnv**; multi-step episodes use the WebSocket session.

## Training a policy (optional, for judges with a GPU)

```bash
pip install stable-baselines3 gymnasium
python backend/baselines/train_ppo.py --steps 50000 --category email_triage --out ppo_email.zip
```

The env wraps cleanly under a Gymnasium adapter (`baselines/train_ppo.py::AriaGymEnv`). We do not ship a trained checkpoint — training takes real GPU hours and would undermine the point of the env being a learnable benchmark.

## Scope honesty

- **No trained PPO checkpoint shipped.** We demonstrate learnability via:
  1. A hand-crafted scripted expert beating random by >300% mean reward
  2. A clean stable-baselines3 wrapper showing the env plugs in with zero friction
- **Voice pipeline** defaults to mock mode (silent WAVs, canned transcripts). Real mode uses faster-whisper + piper when `ARIA_DOWNLOAD_MODELS=1` and `MOCK_VOICE=0`. Latency tested on a 2024 MBP: STT p50 ~120 ms (tiny.en), TTS first-byte ~90 ms. Cannot verify the <500 ms end-to-end claim in CI — documented as a target, not a guarantee.
- **External integrations** (Gmail, Google Calendar, Slack, WhatsApp) are stubbed. Real OAuth is out of scope for reproducible judging.

## What makes this environment interesting

1. **Multi-dimensional reward.** Six dimensions, not one scalar. Makes reward hacking (e.g., spamming WAIT to avoid penalties) unprofitable — WAIT has its own penalty when urgent items pend.
2. **Relationship dynamics.** Each contact carries closeness, tone preference, trust, last-contact-hours. Actions that ignore these specifics get penalized even when they "look right" at the surface level.
3. **Partial observability.** Hidden objectives, budget limits, sentiment thresholds — the agent sees them only through consequences. The `AriaState.hidden` dict lets judges introspect without leaking into observation.
4. **Deterministic scenario generation.** Seeded numpy PCG64 → byte-identical observations across machines. Reproducibility is verified by `test_determinism.py`.
5. **Terminal-aware reward shaping.** Unresolved conflicts at episode end trigger a separate terminal penalty (`aria_rewards/terminal.py`) that prevents the agent from stalling.

## Files judges probably want to open first

1. `README.md` — top-level orientation
2. `backend/services/env-service/OPENENV_API_NOTES.md` — exact API translation from README language to OpenEnv's Pydantic-based contract
3. `backend/packages/aria-rewards/src/aria_rewards/compute.py` — see the six dimensions in 200 lines
4. `backend/tests/env/test_reward_shaping.py` — golden-trajectory tests
5. `backend/baselines/baseline_metrics.json` — the committed numbers to diff against
