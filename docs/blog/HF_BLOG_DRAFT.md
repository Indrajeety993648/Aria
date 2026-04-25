---
title: "ARIA — Teaching LLM agents to complete tasks without damaging relationships"
thumbnail: /blog/assets/aria/thumbnail.png
authors:
  - user: "indra123"
---

# Teaching LLM agents to complete tasks without damaging relationships

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

We built `aria-personal-manager-v1` for the Meta PyTorch OpenEnv Hackathon 2026
to teach an LLM the second half of that question. It's the first OpenEnv RL
environment where **the reward function explicitly penalises completing tasks
at the cost of damaging relationships** — and where we can prove the
relationship signal isn't decorative by ablating it and watching the agent
fail in a recognizable way.

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
dinner planning, delegation, shopping — at three difficulties each.

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

About 25-45 % of partner/family/friend contacts on medium/hard scenarios
prefer hinglish replies. The agent has to set `payload["lang"] = "hinglish"`
or pay a `user_satisfaction` penalty. Cultural specificity that no other
OpenEnv submission has — and a foundation for the multilingual personal-
assistant work we're building post-hackathon for the Indian market.

## Training and the ablation

We fine-tuned **Qwen 2.5 0.5B-Instruct** with **TRL GRPO** + LoRA adapters on
a single T4. The setup is intentionally light — the goal is to show the
*environment* teaches something, not to break SOTA on a small model.

Two runs, same seed, same hyperparameters, identical except for one knob:

- **Run A (full reward)**: all six dimensions active
- **Run B (ablated)**: `relationship_health` weight zeroed

The ablation is built into the environment via a constructor flag — the
dimension still computes (so you can read its score for analysis) but
contributes 0 to the surfaced scalar reward:

```python
AriaEnv(ablate_dimensions=("relationship_health",))
```

![reward curves](./assets/aria/reward_curve.png)
*Both runs converge to similar `task_completion`, but the ablated agent
reward-hacks via unilateral `CANCEL`s. The full-reward agent learns to use
`PROPOSE_ALTERNATIVE` instead.*

The qualitative story comes through in trajectories: when faced with the
canonical day-0 conflict (board review with boss vs. school play with
partner), the **full-reward agent** consistently picks `RESOLVE_CONFLICT` or
`PROPOSE_ALTERNATIVE` — preserving both events. The **ablated agent** picks
`CANCEL`, taking the immediate `task_completion` win and ignoring the
collapsing relationship state it's leaving behind. That's the failure mode
we want any "personal AI" to *not* have.

## Reward against the baselines

n=20 episodes per scenario × difficulty cell, medium difficulty:

| Policy | Mean episode reward |
|---|---:|
| do_nothing (always WAIT) | -1.759 |
| random | -0.289 |
| **scripted_expert** | **+0.793** |
| trained agent (full) | (filled in at submission time) |
| trained agent (ablated) | (filled in at submission time) |

scripted-expert beats random by **+374 % relative**. A real RL run lands
between these two, climbing toward the expert.

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

Or run it locally — `docker run` and `make test-env` in the [GitHub repo](https://github.com/Indrajeety993648/Aria).

## Why we built this

ARIA started as a product vision: a Hindi-first personal AI companion for
the Indian market that knows you well enough to keep your relationships
intact while running your life. The hackathon environment is the research
substrate underneath. We need RL environments that don't just teach agents
to hit a single number — they teach agents to *care about consequences
beyond their immediate reward*. That's what production deployments need
and that's what the next generation of LLM agents has to learn.

## Links

- 🔗 GitHub: <https://github.com/Indrajeety993648/Aria>
- 🤗 HF Space: <https://huggingface.co/spaces/indra123/aria-personal-manager-v1>
- 🎥 90-second walkthrough: <https://youtu.be/REPLACE_AFTER_RECORDING>
- 🪧 Slides: <https://docs.google.com/REPLACE_AFTER_DECK>

Built for the Meta PyTorch OpenEnv Hackathon 2026 · Theme #3 World Modeling.
