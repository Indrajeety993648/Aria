# Golden episode fixtures

Frozen trajectories used by `backend/tests/env/test_golden_episodes.py` to
prove that `AriaEnv` is byte-deterministic across machines and Python minor
versions.

Each file is a JSON record of one short episode:

```json
{
  "meta": {"category": "...", "difficulty": "...", "seed": N, "max_steps": 10},
  "reset_obs_sha256": "...",
  "steps": [
    {
      "action": {"action_id": ..., "target_id": ..., "payload": {}},
      "obs_sha256": "...",
      "reward_breakdown": {"task_completion": ..., ...},
      "done": true
    }
  ]
}
```

Full observation JSON would be ~20 KB per step, so we store SHA-256 hashes
instead. The reward breakdown is stored verbatim for diff readability —
hash drift on the observation usually shows up as reward drift too, and a
human-readable reward makes the failure message useful.

## Regenerating

After an intentional change to the env (new action, tweaked scenario generator,
reward weight bump), regenerate these fixtures:

```bash
python backend/tests/fixtures/generate_golden.py
```

Review the diff carefully — a spurious change to these files signals an
unintentional regression in determinism.
