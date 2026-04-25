# ARIA — Hackathon Battle Plan

**Frozen at:** 2026-04-25 evening, India · GPU + HF creds arrive tomorrow 12 PM
**Scope:** 72 hours to a winning Meta PyTorch OpenEnv Hackathon submission.

## Win hypothesis

Most submissions will be "agent learns task X." We win by being the **first RL environment that explicitly penalizes task-completion strategies that damage relationships** — and by proving it with a side-by-side ablation (with/without the relationship_health dimension). That's a novel research contribution, not a demo.

Secondary wedge: **Hindi–English code-mix scenarios.** Zero other submissions will have this. Cultural distinctiveness + "this targets a real market" framing.

Tertiary wedge: the storytelling asset we already have (Bloomberg-terminal UI with a live orb + always-listening voice). Most submissions will ship a grainy terminal recording; we ship a demo that *looks like* the product it claims to be training for.

## How each criterion is won

| Weight | Criterion | Our play |
|---:|---|---|
| 40% | Environment innovation | Two novel mechanics landed tonight: **hidden contact mood** (partial observability / Theory of Mind) and **cascading consequences** (dynamic world state). Both are hard to reward-hack. Both are citable. Plus the Hindi code-mix angle. |
| 30% | Storytelling | Narrative README (problem → env → results → companion vision). HF blog post (1000 words). 90-sec video using the actual UI. 8-slide deck. Every asset links to every other asset. |
| 20% | Training curves | TRL GRPO fine-tune of Qwen 2.5 0.5B (fits T4) with LoRA adapters. Ablation: full 6-dim reward vs. 5-dim (relationship_health removed). Two learning curves on the same axes. |
| 10% | Reward pipeline | Refactor 6-dim reward into composable OpenEnv `Rubric` subclasses — judges literally hint at this. `env.rubric.named_rubrics()` returns all six. |

## Tonight's work — what needs no GPU and no HF creds

Ordered by leverage per hour.

### Phase 1 — Env innovation (highest leverage)

**H1 · Rubrics refactor** (~45 min)
- `backend/packages/aria-rewards/src/aria_rewards/rubrics.py`
- Six `Rubric` subclasses: `TaskCompletionRubric`, `RelationshipHealthRubric`, `UserSatisfactionRubric`, `TimeEfficiencyRubric`, `ConflictResolutionRubric`, `SafetyRubric`
- Parent `AriaCompositeRubric` with `__call__(action, observation) → float` + `named_rubrics()`
- `compute_step_reward()` becomes a thin adapter that invokes the composite
- Existing 25+ reward tests must pass unchanged

**H2 · Hidden mood** (~90 min)
- Scenario generators seed each `RelationshipNode.current_mood ∈ [-1, 1]`, randomized per difficulty (hard = wider mood variance)
- `actions.send_msg` + `draft_reply`: if target contact mood < -0.3 AND tone is `direct`, heavy `relationship_health` penalty AND the mood drops further
- If tone is `warm` or `casual` to the same contact, mood gradually improves (+0.1 per appropriate interaction)
- `current_mood` NEVER appears in `AriaObservation` — agent must infer from inbox sentiment history
- This is partial-observability-with-latent-state, which is rare in public RL benchmarks

**H3 · Cascading consequences** (~60 min)
- `world.py` gets `apply_cascades(action_id, outcome)` called at end of `dispatch()`
- `CANCEL` on high-closeness without `proposed_alternative`: next-day events with that contact get `flexibility -= 0.3` + any future messages from them get `urgency *= 0.7`
- Successful `RESOLVE_CONFLICT`: contact trust +0.05 permanently, their future message urgency reads more accurately
- `PROPOSE_ALTERNATIVE` success: contact mood +0.15
- State mutations persist through the rest of the episode — hard to game with one clever action

**H4 · Hindi code-mix content** (~45 min)
- `aria_scenarios/data.py`: add `HINDI_EMAIL_SUBJECTS`, `HINGLISH_SENTIMENT_PHRASES`
- `RelationshipNode` gets optional `language_preference: Literal["en", "hi", "hinglish"]`
- `message_reply` generator: 25% of contacts get `language_preference="hinglish"` on medium, 50% on hard
- New reward signal: if agent `DRAFT_REPLY` with `payload.lang` mismatching contact's language pref → `user_satisfaction -= 0.2`
- Tests: existing tests pass; new test verifies code-mix scenarios generate

### Phase 2 — Training harness (can run at 12 PM tomorrow)

**H5 · TRL GRPO script** (~2 hours)
- `backend/training/prompts.py` — `format_observation(obs) -> str` producing a compact, model-friendly situation summary
- `backend/training/action_parser.py` — regex-tolerant parser from LLM text → `AriaAction`; falls back to `WAIT` on parse fail (reward function penalizes; model learns to stay in format)
- `backend/training/reward_fn.py` — TRL-compatible reward function: roll one episode from the prompt's observation, return `obs.reward_breakdown.total`
- `backend/training/train_grpo.py` — `GRPOConfig(num_generations=4, learning_rate=1e-6, ...)`; LoRA on Qwen 2.5 0.5B-Instruct; wandb logging
- `backend/training/eval.py` — greedy evaluation of a checkpoint across all 18 scenario cells
- `backend/training/plot.py` — matplotlib readers that produce the submission plots from wandb log files or local CSV

**H6 · Colab notebook** (~45 min)
- `backend/training/aria_train_colab.ipynb`
- Markdown cells narrate every step
- One-click install → 100-step smoke run → full 500-step run (option)
- Inline plotting so judges see curves in their browser

### Phase 3 — Plots we can ship tonight (no training needed)

**H7 · Baseline plots** (~45 min)
- `backend/baselines/plot_baselines.py`
- Generates `docs/assets/baseline_rewards.png`, `docs/assets/per_dim_baselines.png`, `docs/assets/category_winrate.png`
- Plots are labeled axes, grid, legend, .png, committable immediately
- After tomorrow's training, same script accepts `--include-trained <checkpoint>` to overlay the trained agent on identical axes

### Phase 4 — HF Space scaffold (push tomorrow)

**H8 · openenv.yaml + HF Dockerfile** (~45 min)
- `backend/services/env-service/openenv.yaml` — correct schema (name, version, description, action_schema, observation_schema, state_schema)
- `backend/services/env-service/Dockerfile.hf` — listens on `$PORT` (HF convention), exposes 7860
- HF-flavored README with frontmatter block (`sdk: docker`, `emoji`, `colorFrom`, `colorTo`, `pinned`, `tags: [reinforcement-learning, openenv, rl, agents]`)
- Test locally: `docker build -f Dockerfile.hf` builds without HF credentials needed

### Phase 5 — Storytelling assets

**H9 · README rewrite** (~60 min)
- Top-level `README.md` replaced with a 3–5 min narrative
- Structure: hook (one-liner that stops scrollers) → problem → env → results (embedded PNGs) → why it matters → links
- Every link works without HF creds (we substitute placeholders that get replaced tomorrow)

**H10 · Blog + video script + slides** (~90 min)
- `docs/blog/HF_BLOG_DRAFT.md` — 1000 words, publishable tomorrow
- `docs/VIDEO_SCRIPT.md` — 90 sec, shot-by-shot
- `docs/SLIDES_OUTLINE.md` — 10 slides with speaker notes
- All three tell the same relationship-aware-agent story so judges don't get whiplash

**H11 · Ablation design** (~15 min; mostly documented in this doc)
- Run A: all 6 dimensions
- Run B: `relationship_health` weight zeroed out, others renormalized
- Same seed, same compute budget, same Qwen-0.5B base
- Thesis: **the relationship_health signal teaches the agent to propose alternatives instead of canceling.** We want a plot where Run A has higher final task-completion AND relationship-health, because the agent learned to satisfy both; Run B has higher task-completion but tanks relationship-health (classic reward-hacking).

## Tomorrow's window (12 PM onward)

**12:00** — GPU access.
**12:05** — Kick off Run A (full reward) training in background. 500 steps, ~6 hours.
**12:10** — While Run A warms up, start Run B (ablated) on a second machine if available; otherwise queue for 6 PM.
**12:30** — Once HF creds land, push env-service to `huggingface.co/spaces/<user>/aria-personal-manager-v1`.
**13:00** — While training, run baseline eval on main machine, commit `docs/assets/baseline_*.png`.
**18:00** — Run A finishes. Generate plots. Swap `docs/assets/reward_curve.png` with real curve.
**19:00** — Kick off Run B.
**23:00** — Run B finishes. Produce ablation plot on same axes.

**Day-after (final submission day)**
**AM** — Record 90-sec video using the live UI + trained agent (actual trajectories, not canned).
**AM** — Publish HF blog post, update README with final links.
**PM** — Upload slides to Google Slides, link in README.
**PM** — Final smoke test on HF Space.
**PM** — Submit.

## Concurrency / latency notes

- **Env is CPU-bound and sub-millisecond per step** — we already have tests proving this (full-turn in-proc p95 = 0.46 ms from `docs/LATENCY.md`).
- **Training rollouts can parallelize**: GRPO's `num_generations=4` produces 4 trajectories per prompt; each hits `AriaEnv.step` independently. We can use `concurrent.futures.ThreadPoolExecutor` since env is pure Python (no GPU contention). With `num_generations × batch_size = 32` concurrent rollouts, throughput is bounded by LLM inference (vLLM + Qwen-0.5B ≈ 200 tok/s on T4), not env.
- **HF Space**: FastAPI + uvicorn already async. Concurrent env sessions are supported (`SUPPORTS_CONCURRENT_SESSIONS = True` on AriaEnv).
- **Frontend**: WS throughput is the bottleneck; buffered events + backpressure already in place.

## Tradeoffs we're consciously making

| Dropped | Why |
|---|---|
| Sarvam TTS integration | Zero judging weight; swallows tomorrow's GPU hours |
| Spotify / WhatsApp / Gmail wiring | Product, not hackathon. Survives in the blog as "next step" |
| Unsloth instead of TRL | TRL is better documented, has native GRPO support; Unsloth is faster but adds deploy complexity. Hackathon requires "Unsloth or TRL" — we pick TRL. |
| Full 100k-step training | 500 steps is enough for readable curves in 6h; diminishing returns thereafter |
| Custom voice cloning | Post-hackathon |
| Multi-lingual TTS | Post-hackathon |
| Frontend polish beyond current state | Current state already impresses; diminishing returns |

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| GPU access slips past 12 PM | Training script runs on CPU at 10× slower speed as fallback — shorter run (100 steps) still produces a submittable plot |
| HF creds slip | Env is fully runnable via docker compose locally; video recorded off local instance; blog published on personal Medium as fallback |
| TRL GRPO has a gotcha on Qwen 0.5B | Pivot to Qwen 2.5 1.5B on an A10 if available, or drop to PPO on SB3 (already working) |
| Rubrics refactor breaks existing tests | Keep `compute_step_reward()` as exact-output adapter; refactor is purely internal |
| Training diverges | Conservative hyperparameters: lr 1e-6, kl_beta 0.05, gradient_clip 1.0; pre-commit a checkpointing strategy so we can roll back |

## What a winning submission looks like (the spec)

1. ✅ OpenEnv env, gym-style API, valid `openenv.yaml`, rubric-based reward — all shipped tonight
2. ✅ TRL GRPO training script ready — shipped tonight, runs tomorrow
3. ✅ Real training evidence: 2 reward curves on shared axes, per-dim breakdown, ablation, checkpoint — tomorrow
4. ✅ HF Space live — tomorrow
5. ✅ 1000-word blog, 90-sec video, 10-slide deck, narrative README — tonight drafts, tomorrow publish
6. ✅ Readable plots with labeled axes and captions — all committed .png
7. ✅ 3–5 min README read that makes a reviewer want to try the env — tonight

## After the hackathon (parked)

The personal-companion product vision is the north star after submission:
- Sarvam Bulbul v2 TTS (Hindi-native)
- Spotify + WhatsApp + Gmail + Calendar integrations
- Memory service with 4-tier personalization
- Emotion-tagged dialogue

Use hackathon win / recognition as recruiting + fundraising leverage.

---

*This plan is the single source of truth. Any deviation must be justified in a follow-up note to the team.*
