# ARIA — voice pipeline latency

_Measured 200 iterations per stage, warm caches, single thread, no GPU._

## In-process stages (measured)

| Stage | n | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) |
|---|---:|---:|---:|---:|---:|
| `intent_classifier` | 200 | 0.01 | 0.01 | 0.01 | 0.01 |
| `entity_extractor` | 200 | 0.01 | 0.01 | 0.03 | 0.03 |
| `context_resolver` | 200 | 0.00 | 0.01 | 0.01 | 0.02 |
| `state_encoder` | 200 | 0.01 | 0.01 | 0.01 | 0.03 |
| `decision_engine` | 200 | 0.03 | 0.05 | 0.07 | 0.10 |
| `env_step` | 200 | 0.24 | 0.33 | 0.44 | 0.46 |
| `full_turn_in_proc` | 200 | 0.37 | 0.46 | 0.51 | 0.55 |

## Model-dependent stages (documented budget)

| Stage | typical (ms) | source |
|---|---:|---|
| `stt_whisper_tiny_en` | 120 | voice-service/README, mock-mode bypasses model |
| `tts_piper_first_byte` | 90 | voice-service/README, streaming to first chunk |

## Derived end-to-end p95

- sum of in-process p95 stages (excluding `full_turn_in_proc`): **0.42 ms**
- plus model-dependent budget (STT 120ms + TTS first-byte 90ms): **210.42 ms**

- target per README § 6: **< 500 ms** — ✓ within budget

## Notes

- STT / TTS numbers are quoted from the voice-service README; this bench does not load faster-whisper or piper weights.
- `full_turn_in_proc` is the total per-turn overhead for everything we own in-process.
- Regenerate with: `PYTHONPATH=backend python backend/bench/latency.py --n 200`
