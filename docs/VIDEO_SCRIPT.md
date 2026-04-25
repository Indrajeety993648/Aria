# ARIA — 90-second video script

**Total runtime target:** 88-92 seconds.
**Tone:** confident, technical, grounded. No hype.
**Capture:** 1080p, 30fps, OBS or Loom.
**Audio:** narration + subtle background pad. No music spike.

## Shot list

### 0:00 – 0:08 — HOOK (8s)

Visual:
- Open on the **boot sequence** of the Bloomberg-terminal frontend — the 7 lines printing in sequence to `SYSTEM READY. STANDBY.`
- Cut to the live UI with the Jarvis voice orb pulsing.

Narration:
> "What does your AI assistant do when your boss wants a call during your kid's school play?
> Most agents pick one. ARIA learns to keep both."

### 0:08 – 0:22 — PROBLEM (14s)

Visual:
- Show three columns of the UI: calendar with the conflict highlighted, inbox top-3 in red, reward radar at center.
- Subtle arrow appears between `Board review with Priya — 5pm` and `Riya's school play — 5:15pm`.

Narration:
> "Today's LLM agents optimise for one number — task completion. They cancel.
> They reply tersely. They ignore people. Technically optimal. Socially destructive.
> We need RL environments that teach the next-generation agent to care about consequences."

### 0:22 – 0:42 — ENVIRONMENT (20s)

Visual:
- Cut to a code overlay showing the six rubrics with their weights:
  ```python
  for name, rubric in env.rubric.named_rubrics():
      print(name, rubric.weight)
  ```
  → six lines printed.
- Then a quick three-card explainer for the novel mechanics:
  - `Hidden contact mood` (animated graph showing inferred sentiment)
  - `Cascading consequences` (animated arrow: cancel today → flexibility drop next week)
  - `Hindi-English code-mix` (Hindi text rendering)

Narration:
> "ARIA is an OpenEnv environment with a six-dimensional reward — task completion,
> relationship health, satisfaction, efficiency, conflict resolution, safety —
> assembled into a composable rubric tree. Each dimension is independently inspectable.
>
> Plus three mechanics that make reward hacking hard: hidden contact mood the agent has to
> infer, cascading consequences across future events, and Hindi-English code-mix scenarios."

### 0:42 – 1:08 — RESULTS (26s)

Visual:
- Cut to the reward curve plot. Show full-reward (solid) climbing.
- Then ablated (dashed) appears — climbing to a *different* plateau.
- Zoom to the plateau gap.
- Then a side-by-side trajectory clip: full agent picks `PROPOSE_ALTERNATIVE` on the conflict, ablated agent picks `CANCEL`.

Narration:
> "We trained Qwen 2.5 0.5B with TRL GRPO and ran an ablation: same setup, but with
> the relationship_health dimension zeroed.
>
> The two agents converge to similar task completion — but the ablated agent
> reward-hacks via unilateral cancels. Watch them on the canonical conflict.
>
> Full reward: PROPOSE_ALTERNATIVE. Both events preserved.
> Ablated: CANCEL. Calendar clean, partner sidelined.
>
> That's the failure mode every personal AI has to avoid. ARIA is the first OpenEnv
> environment that trains it out."

### 1:08 – 1:22 — CTA (14s)

Visual:
- Hosted env URL on screen
- Quick `pip install openenv-core` + Python snippet:
  ```python
  env = HTTPEnvClient("https://hf.co/spaces/<user>/aria-personal-manager-v1")
  ```
- Logo card: GitHub + HF Space + blog post links.

Narration:
> "The environment is on Hugging Face Spaces. The training script runs on a free Colab.
> The blog post has the full ablation analysis.
>
> Built for the Meta PyTorch OpenEnv Hackathon 2026. Take it, fork it, train your own
> relationship-aware agent."

### 1:22 – 1:30 — END CARD (8s)

Visual:
- ARIA logo + "Theme #3 World Modeling — Meta PyTorch OpenEnv Hackathon 2026"
- Three URLs

Audio:
- Soft outro pad fade.

## Production notes

- **Voice:** flat, slightly slow. Avoid hype words.
- **Cuts:** every 4-6 seconds, no hold longer than 8s on a static frame.
- **Lower-third overlays** for technical terms: "OpenEnv Rubric", "TRL GRPO", "LoRA on Qwen 2.5 0.5B".
- **Watermark / brand mark:** corner ARIA logo throughout.
- **No emoji.** No background music spike. No drone shots.
