# ARIA — Team Handbook

**For:** Anyone joining the project this week.
**Reading time:** ~15 minutes for the full doc, 5 minutes for the TL;DR.
**Last updated:** 2026-04-25 (evening, before GPU window opens 2026-04-26 12:00 IST).

---

## 0 · Read this first (the TL;DR)

We're submitting **ARIA** — an OpenEnv RL environment named `aria-personal-manager-v1` — to the **Meta PyTorch OpenEnv Hackathon 2026**, Theme #3 (World Modeling), tasks 3.1 + 3.2.

**The single sentence pitch.** Most RL agents learn to complete tasks. We built an environment that teaches an LLM agent to complete tasks **without damaging human relationships** — and we prove with an ablation study that the relationship signal actually changes agent behavior.

**The single sentence vision.** This env is the training substrate for a future product: a Hindi-English personal AI companion that knows you well enough to keep your relationships intact while running your life. The hackathon submission is the research contribution; the product follows.

**Why we'll win:**
1. **Innovation (40 % weight)** — two genuinely novel mechanics: hidden contact mood (partial observability + Theory of Mind) and cascading consequences (one bad action poisons future state). Plus Hindi-English code-mix scenarios — culturally distinctive, no other submission will have it.
2. **Storytelling (30 %)** — relationship-aware framing is concrete and emotionally grounded. We already have a Bloomberg-terminal demo UI with a live voice orb, so our video/blog will look like a product, not a research demo.
3. **Training evidence (20 %)** — TRL GRPO fine-tune of Qwen 2.5 0.5B with LoRA, plus an ablation run (relationship-health dimension removed). Two reward curves on the same axes show the mechanic isn't decorative.
4. **Reward pipeline (10 %)** — refactored into composable OpenEnv `Rubric` subclasses (judges literally hint at this in the brief). Each of the six dimensions is independently inspectable via `env.rubric.named_rubrics()`.

---

## 1 · What ARIA is, in one paragraph

`aria-personal-manager-v1` simulates one day of a knowledge worker's personal life. The agent receives an observation (calendar, inbox, contacts, pending tasks, time, location) and picks one of fifteen actions (`SEND_MSG`, `RESCHEDULE`, `DELEGATE`, `RESOLVE_CONFLICT`, `WAIT`, …). The world responds — events shift, contacts react, deadlines slip — and the agent gets a six-dimensional reward weighted into a single scalar. Episodes run up to 50 steps. The agent's goal is to navigate the day successfully, where "successfully" means **completing tasks AND preserving relationships AND staying inside its safety boundaries**, not just one of those.

---

## 2 · Why this is novel (the research story)

Existing personal-task RL benchmarks (and most LLM agent benchmarks generally) test whether the agent can complete a task. **They almost never test whether the agent can complete the task well** — without damaging trust, without ignoring loved ones, without spending money it shouldn't. Production agents (Lindy, alfred_, Motion) optimize for throughput and have to bolt on guardrails as separate systems.

ARIA puts **relationship intelligence** inside the reward function itself. Three concrete mechanics make this hard to fake:

### 2.1 Multi-dimensional reward as a `Rubric` tree

Six independent dimensions (`task_completion`, `relationship_health`, `user_satisfaction`, `time_efficiency`, `conflict_resolution`, `safety`) each implemented as an OpenEnv `Rubric` subclass. The agent can't game one dimension at the expense of others — the weighted sum, not any single signal, is the training target.

```python
env = AriaEnv()
for name, rubric in env.rubric.named_rubrics():
    print(name, rubric.last_score)
# task_completion 0.4
# relationship_health -0.6
# user_satisfaction 0.0
# time_efficiency 0.0
# conflict_resolution 0.3
# safety 0.0
```

### 2.2 Hidden contact mood (partial observability / Theory of Mind)

Each contact has a `current_mood ∈ [-1, 1]` set by the scenario generator. **The mood is a hidden variable** — agents must infer it from inbox sentiment trail and `last_contact_hours`. Sending a `direct` or `formal` reply to an upset partner is a heavy relationship penalty even when "direct" matches their stated tone preference. The reward function fires `mood_mismatch=True` from inside the action handlers.

This is a **Theory-of-Mind RL benchmark**: the agent has to model the latent emotional state of other agents in the world to act correctly. Public benchmarks for this are rare. Citable.

We have a unit test that proves a tone-blind agent loses to a sentiment-aware agent on the same scenario — see `backend/tests/env/test_hidden_mood.py::test_optimal_inferring_agent_outscores_naive_agent`. That's the seed of the "money plot" for the write-up.

### 2.3 Cascading consequences

Actions have second-order effects on later state. Cancelling a high-closeness event without proposing an alternative drops that contact's flexibility on **future** events and lowers the urgency markings on **future** messages from them — a passive-aggressive simulation. Successful conflict resolution permanently raises trust, which makes future cooperation cheaper.

These long-horizon dynamics make reward hacking hard. An agent can't pick one clever action and win — it has to plan.

### 2.4 Hindi-English code-mix scenarios

A subset of `message_reply` scenarios produce contacts whose `language_preference` is `"hinglish"`, with subjects and sentiment tags carrying Hindi-script content. The reward penalizes language mismatches. **Zero other OpenEnv submissions will model this.** Cultural distinctiveness costs little but separates us from the pack.

---

## 3 · The status board

### 3.1 Done (committed, tested)

| Lane | Description | Files | Tests |
|---|---|---|---|
| Contracts | Pydantic schemas for action/observation/state, six-dimension reward, voice/agent/memory/gateway DTOs | `backend/packages/aria-contracts/` | 17 ✅ |
| Scenarios | 6 categories × 3 difficulties, deterministic seeded generators, hidden mood populated | `backend/packages/aria-scenarios/` | 60 ✅ |
| Rewards | 6-dim function + terminal-step adjustments + composable Rubric tree + ablation flag | `backend/packages/aria-rewards/` | 40 ✅ |
| Env | `AriaEnv` (OpenEnv `Environment` subclass), `WorldModel`, 15 action handlers, `RelationshipModel` extracted | `backend/services/env-service/` | 12 ✅ |
| Hidden mood | Wired through `send_msg` + `draft_reply`, infer-from-sentiment tests | `actions.py`, `_common.py` | 8 ✅ |
| Judge tests | spaces, determinism, scenario invariants, reward shaping, episode bounds, HTTP/WS, grader compat | `backend/tests/env/` | 47 ✅ + 5 HTTP-gated |
| Baselines | random / do_nothing / scripted_expert. Expert beats random by **+374 %** mean reward | `backend/baselines/` | committed metrics JSON |
| Microservices | env / orchestrator / voice / memory / gateway behind FastAPI, Docker-compose topology | `backend/services/` | 75 ✅ across services |
| Voice mocks | Whisper + Piper + ElevenLabs + mock TTS backends, energy-gate + phrase wake-word | `voice-service/` | 24 ✅ |
| Frontend | Next.js 15 Bloomberg-terminal UI with always-listening voice orb, boot sequence, panel grid | `frontend/` | builds clean (117 KB first-load) |
| E2E | gateway → orchestrator → env via in-process ASGI transport | `backend/tests/integration/` | 2 ✅ |
| Latency | Stage-wise benchmark; in-proc p95 0.46 ms, derived e2e p95 ~210 ms | `backend/bench/`, `docs/LATENCY.md` | committed PNG |

**Test totals as of this writing:** 173 backend tests passing, 5 HTTP-gated skipped. Frontend builds clean, no TypeScript errors.

### 3.2 To do tomorrow (the critical path)

Ordered by what unlocks what.

| ID | Task | Window | Dep |
|---|---|---|---|
| **H3** | Cascading consequences — `_apply_cascades` in dispatch, future-state mutations, tests | Tonight (in progress) | Already started; cancel handler now exposes `cancel_participants` |
| **H4** | Hindi/English code-mix scenarios — Hindi `EMAIL_SUBJECTS`, `language_preference`, reward penalty for mismatched language | Tonight | None |
| **H5** | TRL GRPO training harness — Qwen 2.5 0.5B, LoRA, prompt formatter, action parser, reward fn, wandb hookup | Tonight (write) → 12:30 PM tomorrow (run) | GPU |
| **H6** | Colab-ready notebook wrapping H5 | Tonight | H5 |
| **H7** | Baseline plots: reward-vs-episode, per-dim breakdown, category winrate. PNGs committed to `docs/assets/` | Tonight | None |
| **H8** | `openenv.yaml` manifest + HF-flavored Dockerfile + HF README frontmatter | Tonight | None |
| **H9** | Story-forward top-level README rewrite | Tonight | H7 plot paths |
| **H10** | HF blog draft (1000 words), 90-second video script, 10-slide deck outline | Tonight | None |
| **H11** | Ablation study spec — full 6-dim run vs. relationship-health-removed run, on shared axes | Tonight (design) → tomorrow (execute) | H5 |
| **HF push** | Upload env-service to a HF Space when creds arrive (~12 PM tomorrow) | Tomorrow PM | H8 + creds |
| **Train** | 500-step run + 500-step ablation run on T4, ~6 h each, can pipeline | Tomorrow afternoon | H5 + GPU |
| **Plots overlay** | After training, overlay trained-agent line on baseline plots | Tomorrow evening | Train + H7 |
| **Video** | Record 90-sec walkthrough using actual UI + trained-agent trajectories | Tomorrow night | Train |

### 3.3 Out of scope (consciously deferred to post-hackathon)

- Sarvam Bulbul TTS / ElevenLabs v3 emotional voice integration
- Spotify / Gmail / Calendar / WhatsApp / YouTube real OAuth
- Memory service summarization jobs and personalization extractors
- Mobile app
- Fully on-device / federated mode
- Voice cloning

These all live in [`docs/PRODUCT_ROADMAP.md`](./PRODUCT_ROADMAP.md). After the hackathon they become Tier 1 product work.

---

## 4 · Repository tour

```
Aria/
├── backend/
│   ├── packages/                         # shared Python libraries
│   │   ├── aria-contracts/               # ⭐ Pydantic schemas — single source of truth for inter-service data
│   │   │   └── src/aria_contracts/
│   │   │       ├── env.py                # AriaAction, AriaObservation, AriaState + sub-models
│   │   │       ├── reward.py             # RewardBreakdown, REWARD_WEIGHTS, REWARD_PER_STEP_MAX
│   │   │       ├── voice.py              # VoiceTranscript, TTSRequest, VoiceChunk
│   │   │       ├── agent.py              # AgentTurnRequest/Response (orchestrator)
│   │   │       ├── memory.py             # MemoryWrite/Query/Hit
│   │   │       └── gateway.py            # GwAgentEvent (WS)
│   │   ├── aria-scenarios/               # ⭐ deterministic scenario generators
│   │   │   └── src/aria_scenarios/generators/
│   │   │       ├── _common.py            # build_relationships (← hidden mood lives here)
│   │   │       ├── calendar_conflict.py  # forced day-0 overlap
│   │   │       ├── email_triage.py       # urgent + noise mix
│   │   │       ├── message_reply.py      # negative-sentiment loaded contacts
│   │   │       ├── dinner_planning.py    # multi-constraint coordination
│   │   │       ├── delegation.py         # delegatable vs not
│   │   │       └── shopping.py           # budget gate
│   │   └── aria-rewards/                 # ⭐ reward math + Rubric tree
│   │       └── src/aria_rewards/
│   │           ├── compute.py            # legacy per-dim functions (still used by rubrics)
│   │           ├── terminal.py           # end-of-episode adjustments
│   │           └── rubrics.py            # NEW: AriaCompositeRubric + 6 dimension Rubric subclasses
│   ├── services/
│   │   ├── env-service/                  # ⭐ THE hackathon deliverable — OpenEnv FastAPI server
│   │   │   ├── src/env_service/
│   │   │   │   ├── aria_env.py           # AriaEnv(Environment[...]) — uses self.rubric (composite)
│   │   │   │   ├── world.py              # WorldModel — episode mutable state
│   │   │   │   ├── actions.py            # 15 action handlers, dispatch, hidden-mood logic
│   │   │   │   ├── relationship_model.py # tone calibration + post-interaction updates
│   │   │   │   ├── observation.py        # WorldModel → AriaObservation
│   │   │   │   └── server.py             # uses openenv create_app
│   │   │   ├── tests/                    # service-local tests
│   │   │   ├── Dockerfile                # vanilla
│   │   │   ├── Dockerfile.hf             # HuggingFace-flavored (port 7860) — to be added (H8)
│   │   │   ├── openenv.yaml              # HF Space manifest — to be added (H8)
│   │   │   └── OPENENV_API_NOTES.md      # documents which OpenEnv API we use, gotchas
│   │   ├── orchestrator-service/         # agent loop, intent classifier, decision engine, action validator
│   │   ├── voice-service/                # STT (Whisper) + TTS (Piper / ElevenLabs / mock) + VAD + wake-word
│   │   ├── memory-service/               # Qdrant + SQLite, four namespaces, in-memory fallback
│   │   └── gateway-service/              # Public REST + WS fan-out, the only public door
│   ├── baselines/
│   │   ├── policies.py                   # random_policy, do_nothing_policy, scripted_expert
│   │   ├── run_grade.py                  # `make grade` — the judge-facing baseline runner
│   │   ├── baseline_metrics.json         # committed reference numbers
│   │   ├── train_ppo.py                  # SB3 PPO stub (gym wrapper); kept for completeness
│   │   └── train_grpo.py                 # NEW: TRL GRPO harness (H5)
│   ├── tests/
│   │   ├── env/                          # ⭐ judge-facing test suite — 47 + 5 HTTP-gated
│   │   ├── env/test_hidden_mood.py       # NEW: Theory-of-Mind tests
│   │   ├── env/test_cascading.py         # NEW (H3): cascade tests
│   │   ├── integration/                  # gateway→orch→env e2e
│   │   └── fixtures/                     # golden episodes (placeholder dir)
│   ├── bench/
│   │   └── latency.py                    # stage-wise latency benchmark
│   ├── training/                         # NEW (H5): TRL GRPO pipeline
│   │   ├── prompts.py                    # AriaObservation → prompt
│   │   ├── action_parser.py              # LLM text → AriaAction
│   │   ├── reward_fn.py                  # TRL-compatible reward function
│   │   ├── train_grpo.py                 # main training entrypoint
│   │   ├── eval.py                       # post-training evaluation
│   │   ├── plot.py                       # plot generator (matplotlib)
│   │   └── aria_train_colab.ipynb        # one-click Colab
│   └── docker-compose.yml                # full topology (env, orchestrator, voice, memory, gateway, frontend, qdrant)
├── frontend/                             # Next.js 15 demo UI
│   ├── app/page.tsx                      # main page (boot sequence + 3-6-3 grid)
│   ├── components/                       # Panel, Header, Ticker, StatusBar, BootSequence, VoiceOrb,
│   │                                     # VoiceDock, CalendarPanel, InboxPanel, TasksPanel,
│   │                                     # RelationshipsPanel, RewardRadar, EventTrace
│   ├── lib/
│   │   ├── ws.ts                         # useSession() — WS lifecycle + always-listening mic
│   │   └── contracts/                    # TypeScript mirrors of aria-contracts
│   └── public/voice/                     # legacy purple-orb video assets (no longer used)
├── docs/
│   ├── HACKATHON_BATTLE_PLAN.md          # internal strategy doc — read before changing the plan
│   ├── HACKATHON_SUBMISSION.md           # judges-facing notes (technical, terse)
│   ├── PRODUCT_ROADMAP.md                # post-hackathon product plan (alpha → beta → GA → scale)
│   ├── LATENCY.md                        # latency benchmark output
│   ├── TEAM_HANDBOOK.md                  # ⭐ this doc
│   └── assets/                           # PNGs for blog/README (to be populated by H7)
├── skills.md                             # service-lane boundaries (still valid)
├── README.md                             # top-level — to be rewritten as narrative (H9)
└── Makefile                              # `make build`, `make grade`, `make test-env`, etc.
```

⭐ = files that matter most for the hackathon submission.

---

## 5 · How to run things locally

### 5.1 Backend — full stack

```bash
# Once
cp .env.example .env
make install                          # creates .venv and installs all packages

# Run everything in Docker
make build                            # ~5 min cold, <1 min warm
make up
# Frontend: http://localhost:3000
# Env API:  http://localhost:8001/docs
# Gateway:  http://localhost:8000/docs

# Tear down
make down
```

### 5.2 Just the env (the hackathon deliverable)

```bash
docker build -t aria-env -f backend/services/env-service/Dockerfile .
docker run --rm -p 8001:8001 aria-env

# in another shell
curl -X POST http://localhost:8001/reset \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42, "category": "calendar_conflict", "difficulty": "medium"}'
```

⚠ **Important:** OpenEnv's HTTP `/reset` and `/step` endpoints are **stateless** — every request creates a fresh env via the factory. Multi-step interaction uses the WebSocket `/ws` endpoint. See `OPENENV_API_NOTES.md`.

### 5.3 Tests

```bash
make test-env           # 47 env-grader tests, ~3 s
make test-env-full      # adds 5 HTTP+WS tests via TestClient, ~5 s
make test               # all package tests (contracts, rewards, scenarios) ~3 s

# everything, including service-local tests
PYTHONPATH=backend pytest backend
```

### 5.4 Run the baselines

```bash
PYTHONPATH=backend python backend/baselines/run_grade.py --n 20
# Prints a reward table. Last line should read:
#   PASS: expert beats random by the required margin
```

### 5.5 Frontend dev

```bash
cd frontend
npm install
npm run dev
# Then http://localhost:3000
# UI works in offline (mock) mode if no backend is running
```

---

## 6 · How tomorrow goes (timeline)

All times IST.

| Time | What happens | Owner | Output |
|---|---|---|---|
| 12:00 | GPU access opens | (you) | Confirmed access to T4-or-better |
| 12:05 | `python backend/training/train_grpo.py --run-name full --steps 500` | me | Run A starts in background, wandb begins logging |
| 12:30 | HF creds available | (you) | Push env-service to `hf.co/spaces/<user>/aria-personal-manager-v1` |
| 13:00 | While Run A trains, ship: baseline plots, README rewrite, blog draft | me | `docs/assets/*.png`, draft `README.md`, draft blog post |
| 18:00 | Run A finishes (~6 h on T4) | me | Trained checkpoint, reward curve PNG |
| 18:15 | Kick off Run B (ablated reward) | me | Second wandb run |
| 18:30 | Generate first cut of "money plot": full vs. ablated | me | `docs/assets/ablation_curve.png` |
| 19:00 | Final README pass with real plot paths | me | Story-forward narrative + embedded PNGs |
| 23:00 | Run B finishes | me | Final ablation plot updated |

Day-after (final submission day):
- AM: record 90-second video using the live UI replaying trained-agent trajectories
- AM: publish HF blog post; embed video; update README
- AM: smoke-test the HF Space one final time
- PM: final repo cleanup, sanity check links, submit

---

## 7 · How to read the test suite (essential context)

The judge-facing test directory is `backend/tests/env/`. Each file has a clear purpose:

| File | What it proves |
|---|---|
| `test_spaces.py` | Action / observation / state schemas match the documented spec; `extra="forbid"` enforced |
| `test_determinism.py` | Same seed → byte-identical observation; sha256 hashes of `model_dump_json` match across two `AriaEnv` instances |
| `test_scenario_categories.py` | Each scenario family generates correct invariants (e.g., calendar_conflict produces ≥1 day-0 overlap; email_triage has ≥2 urgent items) |
| `test_reward_shaping.py` | Optimal action sequences out-score pathological ones for each scenario family. Includes `test_per_step_reward_bounded_across_trajectories` |
| `test_episode_bounds.py` | `done=True` after 50 steps OR objectives met; reset clears state; pre-reset `state` access raises |
| `test_openenv_http.py` | OpenEnv HTTP / WS endpoints work via FastAPI TestClient (gated by `--run-http`) |
| `test_grader_compatibility.py` | The exact shape a grader script would take: random/expert/do_nothing baselines on each category |
| `test_hidden_mood.py` | NEW: hidden-mood mechanic, including `test_optimal_inferring_agent_outscores_naive_agent` |
| `test_cascading.py` | NEW (H3, in progress): one cancel poisons future flexibility + urgency |

Reading these is the fastest way to understand the env's behavior.

---

## 8 · Rubric API — the 10 % weighted detail

The judging brief explicitly says "composable rubrics > monolithic scoring". We satisfy this by exposing the six reward dimensions as independently-inspectable `Rubric` subclasses. From the env:

```python
env = AriaEnv()                                      # default: full reward
env_abl = AriaEnv(ablate_dimensions=("relationship_health",))  # ablation
for name, r in env.rubric.named_rubrics():
    print(name, "weight:", r.weight)
```

Outputs:
```
task_completion        weight: 0.25
relationship_health    weight: 0.20
user_satisfaction      weight: 0.20
time_efficiency        weight: 0.15
conflict_resolution    weight: 0.15
safety                 weight: 0.05
```

The `ablate_dimensions` flag is what makes the ablation study work end-to-end: with the flag set, `relationship_health` still computes (so its `last_score` is observable for analysis) but contributes 0 to the surfaced `observation.reward`. Tomorrow we train one model with ablation off, one with ablation on, and plot both.

---

## 9 · The training story (the 20 % weighted detail)

We use **TRL's `GRPOTrainer`** — Group Relative Policy Optimization, the algorithm behind DeepSeek-R1 and the de-facto standard for LLM RL in 2025. Hackathon brief allows Unsloth or TRL; TRL is better documented and integrates cleanly.

**Why GRPO over PPO:** GRPO needs no value model (a value head on Qwen 0.5B trains poorly anyway); it does multiple rollouts per prompt and uses relative advantages. Ideal for our episodic reward and our compute budget.

**Architecture:**
- Base model: `Qwen/Qwen2.5-0.5B-Instruct` (fits a T4 comfortably with LoRA adapters).
- Action loop: env returns observation → we format as a prompt ("Current situation: …; Available actions: …") → LLM generates `ACTION: <name>\nTARGET: <id>\nPAYLOAD: {...}` → we parse → step env → return reward.
- Reward signal: total scalar from `observation.reward` (which is the weighted sum of the six Rubrics).
- LoRA: `r=16`, `alpha=32` on attention proj layers — small, T4-friendly.
- Steps: ~500 with `num_generations=4`, batch size 2 → 4000 rollouts = ~6 hours on T4.

**Ablation pair:**
- Run A: `AriaEnv()` — full reward
- Run B: `AriaEnv(ablate_dimensions=("relationship_health",))` — same env, same seed, same hyperparameters, only difference is the relationship-health dimension is zeroed
- Plot: episode reward mean (window=20) vs. training step, both lines on the same axes
- Hypothesis: Run A's agent learns to **propose alternatives** instead of cancelling — leaving task_completion roughly equal but relationship_health far higher. Run B's agent reward-hacks: cancels everything to clear the calendar quickly.

This is the "money plot" — it proves the relationship-health signal isn't decorative.

---

## 10 · Frontend / demo (storytelling asset)

The terminal-style demo UI at `frontend/` is a Bloomberg + hacker aesthetic — JetBrains Mono + amber-on-black, panel grid, always-listening Jarvis-style voice orb at the centre, calendar / inbox / reward radar / event trace around it. There's a 4-second boot sequence on first paint and CRT scanlines on a fixed overlay. It's not load-bearing for the hackathon submission, but it makes the video look like a product instead of a research demo.

When recording the 90-second video:
1. Start with the boot sequence
2. Show the env state on the panels (real data from the trained agent if possible, otherwise mock)
3. Voice query → agent action → state update → reward radar morphing
4. Quick cut to the reward curves on screen
5. Closing slide with HF Space link

---

## 11 · Risks + how we mitigate

| Risk | Likelihood | Mitigation |
|---|---|---|
| GPU access slips past 12 PM | M | Training script also runs on CPU at ~10× slowdown; 100-step CPU run is enough for a submittable curve if absolutely necessary. |
| TRL GRPO has a gotcha on Qwen 0.5B | M | Pivot to `Qwen2.5-1.5B-Instruct` on an A10 if available; absolute fallback is the SB3 PPO baseline we already have working. |
| HF creds slip | L | All assets push-ready locally; submission can use repo URL + Vercel-hosted demo if HF Space is delayed. |
| Training diverges | L | Conservative hyperparams: lr 1e-6, kl_beta 0.04, max_grad_norm 1.0, warmup 50 steps, checkpoint every 50. |
| Ablation runs show no difference | L | Worst-case storytelling angle: "we observe the agent eventually learns to game the ablated reward, here's the failure mode" — still a publishable finding. |
| Last-mile bug in env on HF Space | M | Smoke test the HF Space immediately after first push; have a known-good Docker image tagged `0.1.0` ready to roll back to. |

---

## 12 · How to help (for teammates)

If you have **30 minutes**:
- Read `README.md`, `docs/HACKATHON_BATTLE_PLAN.md`, this doc.
- Skim `backend/tests/env/test_reward_shaping.py` and `backend/tests/env/test_hidden_mood.py`.
- Run `make test-env` locally and confirm it passes.

If you have **2 hours and a GPU**:
- Pick up H5 / H6 — the TRL GRPO training script + Colab notebook. They're independent of cascade work.

If you have **half a day**:
- Pick up H10 — record the video, draft the blog, create the slides.
- Or H7 — generate baseline PNGs and embed them in `README.md`.

If you're a **designer**:
- The frontend at `frontend/` could use a polish pass on the boot sequence styling and a final go-over of the panel typography.

If you're a **storyteller**:
- The HF blog draft (`docs/blog/HF_BLOG_DRAFT.md`, to be created in H10) is the highest-leverage writing slot. 1000 words. Tell the story of the relationship-aware agent.

---

## 13 · Glossary

- **OpenEnv** — Meta's RL environment framework. We subclass `Environment[ActT, ObsT, StateT]`.
- **Rubric** — OpenEnv's composable reward primitive. `Rubric.forward(action, observation) -> float`. Children auto-register via `__setattr__`.
- **GRPO** — Group Relative Policy Optimization. Lightweight RL algorithm for LLMs; no value head needed.
- **LoRA** — Low-Rank Adapters. Train only ~1 % of parameters; lets us fine-tune Qwen 0.5B on a T4.
- **TRL** — Transformer Reinforcement Learning. HuggingFace's training library; ships `GRPOTrainer`, `PPOTrainer`, etc.
- **Theory of Mind** — the agent reasoning about other agents' latent mental states (mood, beliefs).
- **Reward hacking** — agent finds a strategy that scores high without solving the intended task.
- **HF Space** — Hugging Face hosting platform; we'll deploy the env-service there as a Docker Space.

---

## 14 · One-page submission spec (what we're submitting)

When the hackathon submission form opens:

| Field | Value |
|---|---|
| Project name | ARIA — `aria-personal-manager-v1` |
| Theme | #3 World Modeling, tasks 3.1 + 3.2 |
| Repository | github.com/Indrajeety993648/Aria |
| HF Space | huggingface.co/spaces/<user>/aria-personal-manager-v1 (live tomorrow) |
| HF Blog | huggingface.co/blog/<user>/aria-relationship-aware-agent (published tomorrow) |
| Video | youtu.be/… (90 sec, recorded tomorrow) |
| Slides | docs.google.com/… (10 slides, drafted tonight) |
| One-line description | An OpenEnv RL environment that teaches LLM agents to complete personal tasks without damaging human relationships. |
| Submitted by | Indrajeety + team |

---

*This is a living document. Edit under version control; PR any meaningful change. Direct questions to whoever owns the relevant lane (see §12). Good luck.*
