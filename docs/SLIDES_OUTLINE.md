# ARIA — Slide deck outline

**Format:** 16:9, dark theme matching the Bloomberg-terminal aesthetic.
**Slides:** 10 total + title + thank-you = 12.
**Speaker time:** 4-5 minutes including transitions.

---

## Slide 1 — Title

```
ARIA · aria-personal-manager-v1
The first OpenEnv RL env that penalises completing tasks at the cost of relationships.

Meta PyTorch OpenEnv Hackathon 2026 · Theme #3 World Modeling
[author handles]
```

Visual: ARIA logo + boot-sequence still on right.

---

## Slide 2 — The problem

```
Today's LLM agents optimise for one number.

CANCEL → task_completion ↑ (technically optimal)
       → relationship_health ↓ (socially destructive)

Real personal assistants make 30 of these trade-offs a day.
```

Visual: bar chart showing one tall green bar (task_completion) and several dipping red bars (relationship/safety) for an "agent that only optimises task_completion."

---

## Slide 3 — Our claim

```
The environment teaches the trade-off.

We built the first OpenEnv RL env where the reward function explicitly
penalises task-completion strategies that damage human relationships.
```

Visual: split screen — the same observation, two agents, two different actions, two different reward breakdowns.

---

## Slide 4 — Environment shape

```
1 episode = 1 simulated day · up to 50 steps
6 scenario categories × 3 difficulties · 18 cells
15 discrete actions
```

Visual: action wheel (15 segments) + scenario grid 6×3.

---

## Slide 5 — Six-dimensional reward as a Rubric tree

```
env.rubric.named_rubrics()
  task_completion        weight 0.25
  relationship_health    weight 0.20
  user_satisfaction      weight 0.20
  time_efficiency        weight 0.15
  conflict_resolution    weight 0.15
  safety                 weight 0.05  (asymmetric, can hit -2.0)

Each dimension is an independently-inspectable Rubric subclass.
Ablate any one for an experiment:
  AriaEnv(ablate_dimensions=("relationship_health",))
```

Visual: tree diagram — root `AriaCompositeRubric`, six children labeled with weights.

---

## Slide 6 — Three novel mechanics

```
1. Hidden contact mood (Theory of Mind)
   Mood is never in the observation. Agent infers from inbox sentiment.

2. Cascading consequences
   Cancel today → next week's events lose flexibility AND messages arrive at muted urgency.

3. Hindi-English code-mix scenarios
   25-45% of close contacts prefer hinglish replies. Mismatching costs reward.
```

Visual: three icons + one-line each. Pull quote from `test_optimal_inferring_agent_outscores_naive_agent`.

---

## Slide 7 — Training: TRL GRPO on Qwen 2.5 0.5B

```
Base:    Qwen/Qwen2.5-0.5B-Instruct (T4-friendly with LoRA)
Method:  TRL GRPOTrainer · 4 generations per prompt · KL β=0.04
Adapters: LoRA r=16, α=32 on attention proj layers
Steps:    500 · ~6h on T4
Reward:   single scalar from AriaCompositeRubric
Two runs: full reward · relationship_health ablated
```

Visual: the action loop diagram — observation → format prompt → LLM generate → parse action → env step → reward → GRPO update.

---

## Slide 8 — Results: the money plot

```
Reward curves: full-reward agent vs. relationship-health-ablated agent.
Same hyperparameters. Only difference: one dimension's contribution.

The ablated agent reward-hacks via unilateral CANCELs.
```

Visual: the actual `docs/assets/reward_curve.png` plot, full-screen.

---

## Slide 9 — Qualitative comparison

```
Canonical conflict scenario · seed 42 · medium

Full-reward agent → PROPOSE_ALTERNATIVE → +0.65 step reward
                                        → both events preserved
                                        → mood +0.15 on partner

Ablated agent     → CANCEL              → +0.20 step reward
                                        → partner event removed
                                        → flexibility drop on Day-2 events
                                        → message urgency from partner halved next 5 inbox events
```

Visual: side-by-side trajectory cards.

---

## Slide 10 — Reward against baselines

```
n=20 episodes/cell · medium difficulty

  do_nothing      -1.759
  random          -0.289
  scripted_expert +0.793         (+374% over random)
  trained-full    +TBD
  trained-ablated +TBD
```

Visual: per-category bar chart from `docs/assets/baseline_category_means.png`, with trained-agent overlay.

---

## Slide 11 — Try it

```
HF Space:  huggingface.co/spaces/<TBD>/aria-personal-manager-v1
GitHub:    github.com/Indrajeety993648/Aria
Colab:     backend/training/aria_train_colab.ipynb
Blog:      huggingface.co/blog/<TBD>/aria
```

Visual: QR code linking to HF Space.

---

## Slide 12 — Thank you

```
Built for the Meta PyTorch OpenEnv Hackathon 2026
Theme #3 World Modeling · Tasks 3.1 + 3.2

Questions: <handles>
```

Visual: ARIA logo + boot-sequence still + three URLs.
