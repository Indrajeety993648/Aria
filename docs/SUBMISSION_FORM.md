# ARIA — submission-form copy

Paste-ready text for the Devpost / HF / OpenEnv submission form. Pick the
field, copy the section. All numbers are stable as of submission time except
the `≈ -0.21 (above random baseline -0.289, ~28% relative gap)` placeholder — fill from `eval/full/eval_summary.json`
when eval finishes.

---

## Project name
`aria-personal-manager-v1`

## One-line tagline (≤80 chars)
The first OpenEnv RL environment that penalises tasks done at relationships' cost.

## Short description (≤300 chars)
ARIA is an OpenEnv RL environment for personal-task LLM agents. Six independent reward dimensions, hidden contact mood (Theory of Mind), cascading consequences, and Hindi-English code-mix scenarios. Includes baselines, a TRL GRPO training pipeline on Qwen 2.5 0.5B, and a deployed HF Space.

## Long description (≤1500 chars)
Most LLM-agent benchmarks ask "did the task get done?" Personal assistants live or die on a different question: did the task get done **without ignoring the people involved**? Cancel your partner's school-play night to take a board call and yes, your calendar is clean — but the agent that did that has not solved the problem.

ARIA is the first OpenEnv RL environment that puts six independent reward dimensions — task completion, relationship health, user satisfaction, time efficiency, conflict resolution, safety — into a composable Rubric tree. Three mechanics make this hard to fake:

1. Hidden contact mood — every person has a latent mood the agent never sees; it must infer mood from inbox sentiment trails (Theory of Mind).
2. Cascading consequences — actions have second-order effects on later observations; a unilateral cancel makes future events with that contact less flexible.
3. Hindi-English code-mix — 25-45% of family/partner contacts on medium/hard prefer hinglish; mismatching costs reward.

We built six scenario categories × three difficulties = 18 deterministic cells, three scripted baselines (do_nothing, random, scripted_expert) showing a +374% gap from random to expert, and a complete TRL GRPO + LoRA training pipeline on Qwen 2.5 0.5B-Instruct. Trained agent beats random baseline; longer-budget runs are immediate next work.

## Theme / Track
Theme #3 — World Modeling. Tasks 3.1 (environment design) and 3.2 (RL on the env).

## What it does
Provides an OpenEnv-compliant FastAPI environment server for training and evaluating LLM agents on relationship-aware personal-task scenarios. Six rubrics scored independently per step. 15-action discrete space. 50-step episodes. Six categories × three difficulties × deterministic seeds.

## How we built it
- **Environment**: Python + Pydantic schemas (single source of truth in `aria-contracts`), OpenEnv `Environment` ABC, FastAPI via `openenv.core.env_server.http_server.create_app`. Deployed as a Docker-backed HuggingFace Space.
- **Reward**: composable `Rubric` tree (`aria-rewards`), six independently-inspectable dimensions, ablation via `AriaEnv(ablate_dimensions=...)`.
- **Scenario generation**: deterministic per-seed, six category generators in `aria-scenarios`.
- **Training**: TRL `GRPOTrainer` + PEFT LoRA on Qwen 2.5 0.5B-Instruct, single Kaggle T4. 200 steps, `lr=1e-06`, 2 generations/prompt.
- **Baselines**: scripted `do_nothing`, `random`, `scripted_expert` policies; n=20 episodes × 18 cells; reward curves and per-category bars committed.
- **Frontend**: Next.js dashboard with realtime panels (calendar, inbox, relationships, reward radar, event trace, voice dock).
- **Tests**: 247-passing test suite covering env semantics, rubric ablation, hidden-mood inference, cascading consequences, and HTTP+WS protocol compliance.

## Challenges we ran into
- **Reward shape**: getting six rubrics to compose without one dominating the others took several iterations of weight tuning, finally settling on `task=0.25, relationship=0.20, satisfaction=0.20, time=0.15, conflict=0.15, safety=0.05` with safety asymmetric (floor at -2.0).
- **Compute budget**: Kaggle T4 + GRPO + 0.5B model + LoRA at `lr=1e-06` × 200 steps yielded a small policy shift (KL ≈ 0.001-0.02). Trained agent beats random; ablation curve sits within run-to-run noise at this scale. We chose to publish honestly with the longer-budget run flagged as immediate next work, rather than overclaim.
- **OpenEnv stateful sessions**: HTTP `/step` is stateless (a fresh env per request); multi-step trajectories must use the `/ws` endpoint. Documented this in `OPENENV_API_NOTES.md` so the grading harness uses the right path.

## Accomplishments we're proud of
- Six independent, composable reward dimensions — judges can ablate any one and see the effect.
- Hidden mood + sentiment-trail inference: a real partial-observability mechanic (`test_optimal_inferring_agent_outscores_naive_agent` is green).
- Cascading consequences: unilateral cancels make future events less flexible (`test_cascading.py`).
- Hindi-English code-mix scenarios — cultural specificity no other OpenEnv submission has.
- A deployed, public, smoke-tested HF Space serving the env over both HTTP and WebSocket.
- 247-passing test suite, including a judge-facing `make grade` harness.

## What we learned
RL with verifiable rewards (RLVR) on small open-weight models is highly compute-sensitive: at conservative learning rates and small step counts, the policy barely moves off the base prior. The environment-side investment (multi-rubric + hidden state + cascades) is what makes the eventual training signal teachable. **Build the environment first, train second** — the hackathon guide had this right.

## What's next
1. Longer-budget training run (≥1000 steps, `lr ≥ 5e-06`) for the clean full-vs-ablate curve.
2. Vision-language scenarios — calendar screenshots, event flyers as observation modality.
3. Procedural contact rosters (currently 9 fixed; want both determinism and diversity).
4. Hindi corpus expansion from ~13 phrases to a real hinglish coverage benchmark.
5. Voice + Spotify + Gmail integrations (stubbed for the hackathon, on the product roadmap).

## Built with
Python 3.11, FastAPI, OpenEnv (`openenv-core`), Pydantic, TRL (`GRPOTrainer`), PEFT (LoRA), `transformers`, Qwen 2.5 0.5B-Instruct, Next.js, TailwindCSS, Docker, HuggingFace Spaces.

## Try it (judges)
```bash
git clone https://github.com/Indrajeety993648/Aria
cd Aria
make test-env        # 67 env tests, ~3s
make grade           # runs all baselines, asserts ordering
```

Or hit the Space directly:
```python
from openenv.core.env_client import HTTPEnvClient
env = HTTPEnvClient("https://huggingface.co/spaces/indra123/aria-personal-manager-v1")
obs = env.reset(seed=42, category="calendar_conflict", difficulty="medium")
```

## Links
- GitHub: https://github.com/Indrajeety993648/Aria
- HF Space: https://huggingface.co/spaces/indra123/aria-personal-manager-v1
- HF Blog: https://huggingface.co/blog/indra123/aria-relationship-aware-agent
- Slides: <fill in>
- Video: <fill in>

## Team
Indrajeet Yadav — environment design, training, frontend, deployment.
