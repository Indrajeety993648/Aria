"""WebSocket endpoints: /ws/stt and /ws/tts."""
from __future__ import annotations

import json
from typing import Any

from aria_contracts.voice import TTSRequest, VoiceTranscript
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .vad import EnergyVAD

router = APIRouter()

# Heuristic: emit a partial transcript after this much buffered audio.
_PARTIAL_EVERY_BYTES = 16000 * 2  # ~1 second at 16 kHz 16-bit
_FINAL_SILENCE_FRAMES = 25  # ~500 ms of non-speech


def _stt_holder() -> Any:
    """Late import to avoid a circular import at module load."""
    from . import api

    return api.get_stt()


def _tts_holder() -> Any:
    from . import api

    return api.get_tts()


@router.websocket("/ws/stt")
async def ws_stt(websocket: WebSocket) -> None:
    """Receive binary PCM frames, emit VoiceTranscript JSON partials + final."""
    await websocket.accept()
    session_id = websocket.query_params.get("session_id", "ws-session")
    lang = websocket.query_params.get("lang", "en")

    vad = EnergyVAD()
    buffer = bytearray()
    silence_streak = 0
    last_partial_at = 0
    stt = _stt_holder()

    try:
        while True:
            message = await websocket.receive()
            # Client can signal end-of-stream with a text "__end__" sentinel.
            if "text" in message and message["text"] is not None:
                if message["text"] == "__end__":
                    break
                # Unknown text — ignore.
                continue
            data = message.get("bytes")
            if not data:
                continue
            buffer.extend(data)

            # VAD over just-arrived bytes (aligned to frame size).
            frames = vad.iter_frames(bytes(data))
            for _frame, is_speech in frames:
                silence_streak = 0 if is_speech else silence_streak + 1

            # Emit a partial after each ~1 s of audio.
            if len(buffer) - last_partial_at >= _PARTIAL_EVERY_BYTES:
                partial = await stt.transcribe(
                    bytes(buffer), sample_rate=16000, lang=lang, session_id=session_id
                )
                # Force is_final=False for partials.
                partial_msg = VoiceTranscript(
                    session_id=partial.session_id,
                    text=partial.text,
                    is_final=False,
                    confidence=partial.confidence,
                    start_ms=0,
                    end_ms=partial.end_ms,
                    lang=partial.lang,
                )
                await websocket.send_text(partial_msg.model_dump_json())
                last_partial_at = len(buffer)

            # End of utterance on sustained silence.
            if silence_streak >= _FINAL_SILENCE_FRAMES and buffer:
                break
    except WebSocketDisconnect:
        return

    # Always attempt a final transcript, even if the buffer is tiny — mock STT
    # will still return a canned phrase so downstream clients see at least one.
    final = await stt.transcribe(
        bytes(buffer), sample_rate=16000, lang=lang, session_id=session_id
    )
    final = VoiceTranscript(
        session_id=final.session_id,
        text=final.text,
        is_final=True,
        confidence=final.confidence,
        start_ms=0,
        end_ms=final.end_ms,
        lang=final.lang,
    )
    try:
        await websocket.send_text(final.model_dump_json())
        await websocket.close()
    except Exception:
        # Client already gone; nothing to do.
        pass


@router.websocket("/ws/tts")
async def ws_tts(websocket: WebSocket) -> None:
    """Receive a single JSON TTSRequest, stream VoiceChunk messages until is_last."""
    await websocket.accept()
    try:
        payload = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        req = TTSRequest.model_validate(json.loads(payload))
    except Exception as exc:
        await websocket.send_text(json.dumps({"error": f"invalid TTSRequest: {exc}"}))
        await websocket.close()
        return

    tts = _tts_holder()
    stream = await tts.synth(req)
    try:
        async for chunk in stream:
            await websocket.send_text(chunk.model_dump_json())
    except WebSocketDisconnect:
        return
    try:
        await websocket.close()
    except Exception:
        pass
