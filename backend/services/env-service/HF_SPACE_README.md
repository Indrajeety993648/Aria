---
title: ARIA — aria-personal-manager-v1
emoji: 🧠
colorFrom: yellow
colorTo: gray
sdk: docker
pinned: true
license: apache-2.0
short_description: Relationship-aware personal-task RL env for LLM agents
tags:
  - reinforcement-learning
  - openenv
  - llm-agents
  - personal-assistant
  - theory-of-mind
  - multilingual
---

# ARIA — `aria-personal-manager-v1`

The first OpenEnv RL environment that **penalizes task completion strategies
which damage human relationships**.

Built for the **Meta PyTorch OpenEnv Hackathon 2026**, Theme #3 (World Modeling).

## What it teaches an LLM agent

Most personal-task agent benchmarks reward "did the task get done?" ARIA
asks a different question: *did the task get done **without ignoring the
people involved**?* It does this by composing six independently-inspectable
reward rubrics — task completion, relationship health, user satisfaction,
time efficiency, conflict resolution, and safety — into a single weighted
signal.

Three novel mechanics make it hard to game:

1. **Hidden contact mood** — every person in the world has a `current_mood`
   the agent never directly sees. It must be inferred from inbox sentiment
   trails and `last_contact_hours`. Sending a "direct" tone reply to an
   upset partner is heavily penalised even if "direct" matches their stated
   tone preference. (Theory of Mind axis.)
2. **Cascading consequences** — cancel a high-closeness event without
   proposing an alternative and that contact's *future* events become less
   flexible AND their future messages arrive with muted urgency. Long-horizon
   cause and effect, not single-step reward.
3. **Hindi-English code-mix** — 25–45 % of partner/family/friend contacts on
   medium/hard prefer hinglish replies. Mismatching the language costs reward.

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/reset` | `{seed?, episode_id?, category?, difficulty?}` | initial observation |
| `POST` | `/step` | `{action: {action_id, target_id?, payload?}}` | next observation + reward |
| `GET` | `/state` | — | full state (judges may inspect hidden vars) |
| `GET` | `/schema` | — | JSON schemas for action / observation / state |
| `GET` | `/health` | — | `{status: "healthy"}` |
| `WS` | `/ws` | reset/step messages | stateful multi-step session |

⚠ HTTP `/reset` and `/step` are **stateless** in OpenEnv — every request
spawns a fresh env. For multi-step episodes, use the WebSocket endpoint.

## Quick start

```bash
curl -X POST https://<this-space>/reset \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42, "category": "calendar_conflict", "difficulty": "medium"}'
```

```python
# Multi-step via WS (Python)
import websockets, json, asyncio

async def main():
    async with websockets.connect("wss://<this-space>/ws") as ws:
        await ws.send(json.dumps({
            "type": "reset",
            "data": {"seed": 1, "category": "message_reply", "difficulty": "hard"}
        }))
        print(json.loads(await ws.recv()))
        await ws.send(json.dumps({
            "type": "step",
            "data": {"action_id": 5, "target_id": "loaded_000",
                     "payload": {"tone": "warm", "lang": "hinglish"}}
        }))
        print(json.loads(await ws.recv()))

asyncio.run(main())
```

## Reward decomposition

```python
# Inspect the reward tree
GET /state  → {"reward_so_far": {...per-dim totals...}, "hidden": {...}}
```

Each of the six dimensions is an OpenEnv `Rubric` subclass. `env.rubric.named_rubrics()`
returns all six. Run an ablation by zeroing a dimension via the
`ablate_dimensions` constructor flag — useful for proving a specific signal
is teaching the agent the right thing.

## Action space (15 discrete)

| ID | Name | Common payload |
|---:|---|---|
| 0 | SEND_MSG | `{tone, lang, user_approved}` |
| 1 | SCHEDULE | `{title, start_hour, day_offset, participants}` |
| 2 | RESCHEDULE | `{start_hour, day_offset}` |
| 3 | CANCEL | `{proposed_alternative}` |
| 4 | DELEGATE | `{assignee_id}` |
| 5 | DRAFT_REPLY | `{tone, lang}` |
| 6 | SET_REMINDER | — |
| 7 | PURCHASE | `{amount, user_approved}` |
| 8 | RESOLVE_CONFLICT | — |
| 9 | ASK_USER | — |
| 10 | DECLINE_INVITE | — |
| 11 | PROPOSE_ALTERNATIVE | `{start_hour}` |
| 12 | BATCH_ACTION | `{email_ids: [...]}` |
| 13 | WAIT | — |
| 14 | ESCALATE | — |

## Baseline numbers (n=20 medium)

| Policy | Mean episode reward |
|---|---:|
| do_nothing | -1.759 |
| random | -0.289 |
| scripted_expert | **+0.793** |

scripted_expert beats random by **+374 % relative**.

## Links

- 📄 GitHub: https://github.com/Indrajeety993648/Aria
- 📝 Blog post: https://huggingface.co/blog/indra123/aria-relationship-aware-agent
- 🎥 Video walkthrough: https://youtu.be/REPLACE_AFTER_RECORDING

## License

Apache-2.0
