---
title: "ARIA — A relationship-aware OpenEnv RL environment for personal-task LLM agents"
thumbnail: /blog/assets/aria/thumbnail.png
authors:
  - user: "indra123"
---

# ARIA — A relationship-aware OpenEnv RL environment for personal-task LLM agents

> An OpenEnv RL environment where `cancel my partner's school-play night for the
> board call` is the wrong answer — even though it cleared the calendar.

Most personal-task agent benchmarks ask one question: *did the task get done?*
Real personal assistants live or die on a different one: *did the task get done
**without ignoring the people involved**?* In a typical day a knowledge worker
makes thirty calendar-versus-relationship trade-offs — reschedule with the boss
or the partner, reply now or wait, decline politely or escalate, push back on a
deadline or suck it up. None of these are pure throughput problems. The agent
that just maximises "tasks completed" learns to cancel everything, archive
everything, and never engage. Technically optimal. Socially destructive.

We built `aria-personal-manager-v1` for the **Meta PyTorch OpenEnv Hackathon
2026** to teach an LLM the second half of that question. It's an OpenEnv RL
environment where **the reward function explicitly penalises completing tasks
at the cost of damaging relationships** — built around six independent reward
dimensions, hidden contact mood, cascading consequences, and Hindi-English
code-mix.

This post walks through what the environment models, how it's wired, and what
a small Qwen 2.5 0.5B agent learns when you fine-tune it on the env with TRL
GRPO.

## The shape of the problem

Each episode is one simulated day. The agent receives an observation
containing:

- **Calendar** — events over the next 30 days, each with a priority and a
  flexibility score plus the participants
- **Inbox** — priority-ordered messages with sentiment and age
- **Relationships** — per-contact closeness, trust, last-contact-hours, tone
  preference, and (sometimes) a language preference
- **Pending tasks** — priority, deadline, delegatable flag
- **Time, location, preferences vector**

The action space is 15 discrete actions (`SEND_MSG`, `RESCHEDULE`, `CANCEL`,
`DELEGATE`, `RESOLVE_CONFLICT`, `WAIT`, …) with optional `target_id` and
free-form `payload` (tone, language, amount, etc). Up to 50 steps per episode.
Six scenario categories — calendar conflicts, email triage, message replies,
dinner planning, delegation, shopping — at three difficulties each. **18
deterministic (category, difficulty) cells in total**, each seeded for
reproducibility.

The reward is **six independent dimensions** assembled into a composable
[`Rubric`](https://meta-pytorch.org/OpenEnv/core.html#rubric) tree:

| Dimension | Weight | Captures |
|---|---:|---|
| `task_completion` | 0.25 | tasks done before deadline |
| `relationship_health` | 0.20 | net change in closeness/trust across affected contacts |
| `user_satisfaction` | 0.20 | did the action serve the latent scenario objective? |
| `time_efficiency` | 0.15 | batching, prioritization, not wasting steps |
| `conflict_resolution` | 0.15 | did calendar conflicts resolve win-win? |
| `safety` | 0.05 (asymmetric, can hit -2.0) | unauthorized spend, sending without approval |

That last column is what makes single-dimension optimisation losing. The agent
can't max `task_completion` by spamming `CANCEL` — `relationship_health` will
drop and `safety` will fire if any of the cancels involved spending or sending
without approval.

```python
env = AriaEnv()
for name, rubric in env.rubric.named_rubrics():
    print(name, "weight:", rubric.weight)
```

Each rubric is independently inspectable, hookable, and **ablatable** — judges
can zero one out and see the effect on agent behaviour:

```python
# Train an "ablated" agent that doesn't see the relationship signal:
env_abl = AriaEnv(ablate_dimensions=("relationship_health",))
```

## What's novel

### 1. Hidden contact mood (Theory of Mind)

Every person in the world has a `current_mood ∈ [-1, 1]` set by the scenario
generator. **The agent never sees the mood directly.** It must infer it from
the trail of inbox sentiment values from that contact. Sending a *direct*
tone reply to an upset partner is a heavy `relationship_health` penalty even
when "direct" matches their stated `tone_preference` — because the *mood*,
not the preference, is what drives the negative outcome.

This makes ARIA a **partial-observability benchmark** with a latent emotional
state agents have to model. We have a unit test that proves a tone-blind
agent loses to a sentiment-aware one on the same scenarios:

```
test_optimal_inferring_agent_outscores_naive_agent: PASSED
```

### 2. Cascading consequences

Actions have second-order effects on later observations. Cancel a high-
closeness event without proposing an alternative and that contact's *future*
events lose flexibility while their messages arrive at lower urgency — a
passive-aggressive simulation. Successful conflict resolution permanently
raises trust, making future cooperation cheaper. These long-horizon dynamics
make reward hacking hard: an agent can't pick one clever action and win,
it has to plan.

### 3. Hindi-English code-mix

About 25–45 % of partner/family/friend contacts on medium/hard scenarios
prefer hinglish replies. The agent has to set `payload["lang"] = "hinglish"`
or pay a `user_satisfaction` penalty. Cultural specificity that no other
OpenEnv submission has — and a foundation for the multilingual personal-
assistant work we're building post-hackathon for the Indian market.

### 4. Reward-hacking guards by design

The hackathon guide is explicit about reward hacking being one of the biggest
RL failure modes. ARIA mitigates it on three axes:

- **Multiple independent rubrics**, not one scalar. Optimising one dimension
  at the cost of others is detectable in the per-dim breakdown.
- **Episode termination at 50 steps** with action-validity enforced at the env
  layer (`dispatch(world, action)` rejects invalid targets).
- **A dedicated `safety` dimension** with asymmetric down-weight (–2.0 floor)
  that fires on unauthorized spend or unapproved sends.

## Baselines: the env produces a strong reward signal

Before training anything, we ran three scripted baselines across all 18
(category, difficulty) cells, 20 episodes each:

| Policy | Mean episode reward | Beats random by |
|---|---:|---:|
| `do_nothing` (always WAIT) | **−1.759** | — |
| `random` | **−0.289** | — |
| **`scripted_expert`** | **+0.793** | **+374 %** |

The four-fold gap from random to scripted-expert is the property you need for
RL to work: the reward function distinguishes good behaviour from arbitrary
behaviour by a wide margin. If the baseline gap had been small, no amount of
GRPO would have produced learning.

![baseline per-dimension](./assets/aria/baseline_per_dim.png)
*Per-dimension reward by baseline policy. The scripted expert wins on every
dimension; the random agent achieves middling task_completion but tanks safety
— the classic single-objective failure mode the rubric tree is designed to
expose.*

## Training a small agent with TRL GRPO

We fine-tuned **Qwen 2.5 0.5B-Instruct** with **TRL GRPO** + LoRA adapters on
a single Kaggle T4. The setup is intentionally light — the goal is to show the
**environment teaches an LLM something measurable**, not to break SOTA on a
small model.

```bash
python backend/training/train_grpo.py --run-name aria-full \
    --steps 200 --num-generations 2 \
    --max-completion-len 64 --max-prompt-len 768
```

Two runs, same seed, same hyperparameters, identical except for one knob:

- **Run A (full reward)**: all six dimensions active
- **Run B (ablated)**: `relationship_health` weight zeroed via
  `AriaEnv(ablate_dimensions=("relationship_health",))`

Both runs completed cleanly (200 steps each, ~23 min on T4, no OOM, no policy
collapse — KL divergence stayed at ~0.001–0.02 throughout).

![reward curves](./assets/aria/reward_curve.png)
*GRPO training reward over the 50 → 200 step window, 10-step rolling mean.
Both runs rise from ≈ -0.245 to ≈ -0.21 — measurable learning above the random
baseline (-0.289). The two curves overlap within run-to-run noise at this
compute budget.*

### Honest read of the ablation

Both curves show real learning — episode reward improves by ≈ 0.04 over 150
GRPO steps in each run, which is what you want to see early in training: the
multi-rubric signal *teaches* the LLM something. But the curves overlap, so
the **full vs. ablated comparison doesn't separate at this scale**. Two
interpretations are consistent with what we observed:

1. **Compute-bounded ablation.** With KL divergence stuck at ~0.001–0.02, the
   LoRA-adapted policy never moved meaningfully off the base Qwen-Instruct
   prior in either run. Ablating one rubric dimension can't differentiate two
   policies that are still essentially the base model.
2. **Hyperparameter-bounded ablation.** `lr=1e-06` × 200 steps × 0.4 epochs is
   a conservative budget. The ablation comparison is the headline result the
   env was *built for* — we expect it to show clear daylight at ≥1000 steps
   with `lr ≥ 5e-06`.

We're publishing the small-run honestly rather than overclaiming. The
environment supports the ablation cleanly via the constructor flag, the test
suite covers it (`test_ablation_zeros_dimension_contribution`), and the next
phase of work is the longer-budget training run that we expect will produce
the clear separation.

### What the trained agent does qualitatively

Inspecting trajectories on the canonical day-0 conflict scenario (board review
with boss vs. school play with partner), the trained agent — even at this
small scale — favors `RESOLVE_CONFLICT` and `PROPOSE_ALTERNATIVE` over
unilateral `CANCEL`, matching the structure of the scripted-expert behaviour.
The full per-category trajectories are committed in `eval/full/trajectories/`
for review.

## Why we built this

ARIA started as a product vision: a Hindi-first personal AI companion for
the Indian market that knows you well enough to keep your relationships
intact while running your life. The hackathon environment is the research
substrate underneath. We need RL environments that don't just teach agents
to hit a single number — they teach agents to *care about consequences
beyond their immediate reward*. That's what production deployments need
and that's what the next generation of LLM agents has to learn.

## Try it

The env is hosted as a HuggingFace Space (Docker-backed):

```bash
pip install openenv-core
```

```python
from openenv.core.env_client import HTTPEnvClient
env = HTTPEnvClient("https://huggingface.co/spaces/indra123/aria-personal-manager-v1")
obs = env.reset(seed=42, category="calendar_conflict", difficulty="medium")
out = env.step({"action_id": 8, "target_id": "conflict_personal"})  # RESOLVE_CONFLICT
print(out.reward)
```

Or run it locally — `docker run` and `make test-env` in the
[GitHub repo](https://github.com/Indrajeety993648/Aria).

## What's next

- **Longer training run** (≥1000 steps, `lr ≥ 5e-06`) for the full vs ablated
  curve we expect to differentiate clearly.
- **Vision-language scenarios** — calendar screenshots and event flyers as
  observation modality.
- **Procedural contact rosters** — the current 9-person fixed roster trades
  off determinism for diversity; we want both.
- **Hindi corpus expansion** — currently ~13 phrases as a proof-of-concept;
  the production direction needs full hinglish coverage.

## Links

- 🔗 GitHub: <https://github.com/Indrajeety993648/Aria>
- 🤗 HF Space: <https://huggingface.co/spaces/indra123/aria-personal-manager-v1>
- 🎥 90-second walkthrough: <https://youtu.be/REPLACE_AFTER_RECORDING>
- 🪧 Slides: <https://docs.google.com/REPLACE_AFTER_DECK>

Built for the Meta PyTorch OpenEnv Hackathon 2026 · Theme #3 World Modeling.
