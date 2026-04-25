# voice-service

ARIA's voice pipeline: STT (speech-to-text) and TTS (text-to-speech) behind a FastAPI
service. Mock-mode by default, real backends opt-in.

## What

Implements the voice contracts from `aria-contracts`:

- `VoiceTranscript` — one STT emission (partial or final)
- `TTSRequest`     — ask for synthesis
- `VoiceChunk`     — one PCM/audio chunk emitted by TTS

HTTP surface:

| Method | Path        | Purpose                                              |
|-------:|-------------|------------------------------------------------------|
| GET    | `/health`   | liveness                                             |
| POST   | `/stt`      | multipart WAV → `VoiceTranscript` JSON               |
| POST   | `/tts`      | `TTSRequest` JSON → `audio/wav` bytes                |
| WS     | `/ws/stt`   | binary PCM frames in → `VoiceTranscript` JSON out    |
| WS     | `/ws/tts`   | `TTSRequest` JSON in → stream of `VoiceChunk` JSON   |

## Modes

### Mock mode (default: `MOCK_VOICE=1`)

- STT returns a canned `VoiceTranscript` from a small pool of realistic phrases
  (e.g. "hey ARIA what's on my calendar", "reply to Priya that I'll be late").
- TTS now streams by sentence/clause so `/ws/tts` can start audio emission early.
- Partial STT websocket messages also include lightweight intent hints so the
  orchestrator can start routing before the final transcript lands.
- Zero network calls, zero model weights, zero optional deps. Always works.

### Real mode (`MOCK_VOICE=0` and `ARIA_DOWNLOAD_MODELS=1`)

- STT: [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) with `tiny.en`.
- TTS: [`piper-tts`](https://github.com/rhasspy/piper) streaming synthesis by default.
- Backends are lazy-loaded on first request; the service starts healthy even if
  the weights are absent — it only errors on first real-use.

### ElevenLabs TTS (optional)

For higher-quality conversational voice, swap the TTS backend:

```bash
MOCK_VOICE=0 \
TTS_BACKEND=elevenlabs \
ELEVENLABS_API_KEY=sk_... \
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM \
ELEVENLABS_MODEL=eleven_turbo_v2_5 \
  python -m voice_service.server
```

- Pure-`httpx` streaming (no `elevenlabs` SDK required).
- Requests `pcm_16000` directly, re-chunked into 20 ms `VoiceChunk`s so
  first-byte latency is typically 150–250 ms over a good link.
- `optimize_streaming_latency=3` is the sweet spot for conversational agents.
- STT still uses faster-whisper; this flag only swaps the voice-out side.

Blueprint alignment notes:

- If you want the blueprint STT baseline, set `WHISPER_MODEL=large-v3-turbo`.
- The repo currently ships piper-backed TTS; sentence-level streaming is now in
  place, but the edge-tts / Coqui XTTS swap-in remains an explicit follow-up.
- Local mock streaming benchmark on this machine for `"hello. world. how are you?"`:
  first chunk `0.000024s`, total `0.000043s`, `3` chunks.
- The exact blueprint stack latency numbers are not yet published in-repo;
  current mock streaming emits a chunk per sentence/clause and the websocket
  starts sending as soon as the first segment is rendered.

The websocket STT path still uses a simple energy VAD and keyword intent hints;
the blueprint wake-word detector and exact production voice stack remain open
items.

## How to run

### Local (mock mode)

```bash
pip install -e backend/services/voice-service
MOCK_VOICE=1 python -m voice_service.server
# or: uvicorn voice_service.server:app --port 8003
```

### Local (real mode)

```bash
pip install -e 'backend/services/voice-service[real]'
MOCK_VOICE=0 ARIA_DOWNLOAD_MODELS=1 python -m voice_service.server
```

You may also point Piper at a specific voice model path via `PIPER_VOICE_PATH`.

### Docker

The default image is mock-only (no model weights, no real-backend deps):

```bash
docker compose -f backend/docker-compose.yml up voice-service
```

## How to test

```bash
MOCK_VOICE=1 pytest backend/services/voice-service/tests -q
```

All tests run in mock mode and require no network / weights.

## Environment variables

| Name                    | Default | Meaning                                                        |
|-------------------------|---------|----------------------------------------------------------------|
| `MOCK_VOICE`            | `1`     | `1` = canned STT/TTS. `0` = real backends (lazy-loaded).       |
| `ARIA_DOWNLOAD_MODELS`  | `0`     | In real mode, set to `1` to permit model download at first use.|
| `WHISPER_MODEL`         | `tiny.en` | faster-whisper model name.                                   |
| `TTS_BACKEND`           | `piper` | `piper` \| `elevenlabs` \| `mock`. Ignored when `MOCK_VOICE=1`.  |
| `PIPER_VOICE`           | `en_US-amy-medium` | Default Piper voice ID.                             |
| `PIPER_VOICE_PATH`      | (unset) | Optional path to a local `.onnx` Piper voice file.             |
| `ELEVENLABS_API_KEY`    | (unset) | Required when `TTS_BACKEND=elevenlabs`.                        |
| `ELEVENLABS_VOICE_ID`   | `21m00Tcm4TlvDq8ikWAM` | ElevenLabs voice ID (Rachel by default).        |
| `ELEVENLABS_MODEL`      | `eleven_turbo_v2_5` | Low-latency streaming model.                       |
| `VAD_THRESHOLD`         | `0.01`  | Energy threshold for the built-in VAD (RMS over int16 frame).  |
