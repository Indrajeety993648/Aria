# env-service — `aria-personal-manager-v1`

The OpenEnv-compliant FastAPI server that **is the hackathon deliverable**.
Judges can run this container in isolation.

## Run standalone

```bash
docker build -t aria-env -f backend/services/env-service/Dockerfile .
docker run --rm -p 8001:8001 aria-env
```

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/reset` | `{seed?, episode_id?, category?, difficulty?}` | `{observation, reward, done}` |
| `POST` | `/step` | `{action: {action_id: int, target_id?, payload?, metadata?}, timeout_s?}` | `{observation, reward, done}` |
| `GET` | `/state` | — | full `AriaState` |
| `GET` | `/schema` | — | JSON schemas for action, observation, state |
| `GET` | `/health` | — | `{status: "healthy"}` |
| `GET` | `/docs` | — | OpenAPI (Swagger) |

`category` ∈ `{calendar_conflict, email_triage, message_reply, dinner_planning, delegation, shopping}`

`difficulty` ∈ `{easy, medium, hard}`

## Quick walkthrough

```bash
curl -s -X POST http://localhost:8001/reset \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42, "category": "calendar_conflict", "difficulty": "medium"}' | jq '.done, .observation.calendar | length'

curl -s -X POST http://localhost:8001/step \
  -H 'Content-Type: application/json' \
  -d '{"action": {"action_id": 8, "target_id": "conflict_personal"}}' | jq '.reward, .done'
```

## Action cheatsheet (integer IDs)

| ID | Name | Common payload keys |
|---|---|---|
| 0 | SEND_MSG | `tone`, `high_stakes`, `user_approved` |
| 1 | SCHEDULE | `day_offset`, `start_hour`, `end_hour`, `title`, `priority`, `flexibility`, `participants` |
| 2 | RESCHEDULE | target = `event_id`; `start_hour` / `day_offset` |
| 3 | CANCEL | target = `event_id`; `proposed_alternative: bool` |
| 4 | DELEGATE | target = `task_id`; `assignee_id` |
| 5 | DRAFT_REPLY | target = `email_id`; `tone` |
| 6 | SET_REMINDER | target = `task_id` |
| 7 | PURCHASE | target = `task_id`; `amount`, `user_approved` |
| 8 | RESOLVE_CONFLICT | target = one of the conflict event_ids |
| 9 | ASK_USER | — |
| 10 | DECLINE_INVITE | target = `event_id` |
| 11 | PROPOSE_ALTERNATIVE | target = `event_id`; `start_hour` |
| 12 | BATCH_ACTION | `email_ids: [str]` |
| 13 | WAIT | — |
| 14 | ESCALATE | — |

See [OPENENV_API_NOTES.md](OPENENV_API_NOTES.md) for how the README's conceptual action/observation spaces translate to OpenEnv's Pydantic-based contract.
