"""Mock-mode tests for voice-service.

All tests run with MOCK_VOICE=1 — no network, no model weights required.
"""
from __future__ import annotations

import io
import json
import os
import wave

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin MOCK_VOICE=1 and reset cached backends before every test."""
    monkeypatch.setenv("MOCK_VOICE", "1")
    # Reset any cached singletons left over from prior tests.
    from voice_service import api

    api.reset_backends()


@pytest.fixture()
def client() -> TestClient:
    from voice_service.server import app

    return TestClient(app)


def _tiny_wav_bytes(duration_ms: int = 120, sample_rate: int = 16000) -> bytes:
    """Build a tiny silent WAV for upload to /stt."""
    n = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "voice-service"
    assert body["mock"] is True


def test_post_stt_returns_voice_transcript(client: TestClient) -> None:
    wav = _tiny_wav_bytes()
    r = client.post(
        "/stt",
        files={"audio": ("hello.wav", wav, "audio/wav")},
        data={"session_id": "t-1", "lang": "en"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # VoiceTranscript shape
    for k in ("session_id", "text", "is_final", "confidence", "start_ms", "end_ms", "lang"):
        assert k in body
    assert body["session_id"] == "t-1"
    assert body["is_final"] is True
    assert body["text"].strip() != ""
    assert 0.0 <= body["confidence"] <= 1.0


def test_post_tts_returns_audio_wav(client: TestClient) -> None:
    r = client.post(
        "/tts",
        json={"session_id": "t-2", "text": "hello world", "voice": "en_US-amy-medium"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("audio/wav")
    data = r.content
    # Valid RIFF/WAVE header
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    # Parseable by stdlib wave
    with wave.open(io.BytesIO(data), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        assert w.getnframes() > 0


def test_ws_stt_emits_transcript(client: TestClient) -> None:
    # Build ~1.5 s of silent 16 kHz 16-bit PCM and stream it in chunks.
    pcm = b"\x00\x00" * (16000 + 8000)
    chunk = 3200  # 100 ms per send

    with client.websocket_connect("/ws/stt?session_id=ws-1&lang=en") as ws:
        try:
            for i in range(0, len(pcm), chunk):
                ws.send_bytes(pcm[i : i + chunk])
            # Signal end-of-stream to force the final transcript.
            ws.send_text("__end__")
        except Exception:
            # Server may have already closed on sustained silence — that's fine.
            pass

        messages: list[dict] = []
        # Drain until close.
        try:
            while True:
                msg = ws.receive_text()
                messages.append(json.loads(msg))
        except Exception:
            pass

    assert messages, "expected at least one transcript message"
    # At least one message must carry the VoiceTranscript shape.
    assert any("text" in m and "is_final" in m for m in messages)
    # And at least one final transcript with non-empty text.
    finals = [m for m in messages if m.get("is_final") is True]
    assert finals, f"expected a final transcript, got: {messages}"
    assert finals[-1]["text"].strip() != ""


def test_voice_intent_hint_from_partial_text() -> None:
    from voice_service.intent import classify_partial_intent

    hint = classify_partial_intent("reply to Priya that I'll be late")
    assert hint.intent_id is not None
    assert hint.confidence >= 0.5


def test_ws_tts_streams_chunks(client: TestClient) -> None:
    with client.websocket_connect("/ws/tts") as ws:
        ws.send_text(
            json.dumps({"session_id": "ws-tts-1", "text": "hello", "voice": "en_US-amy-medium"})
        )
        chunks: list[dict] = []
        try:
            while True:
                msg = ws.receive_text()
                chunks.append(json.loads(msg))
        except Exception:
            pass
    assert chunks, "expected at least one VoiceChunk"
    last = chunks[-1]
    for k in ("session_id", "seq", "audio_b64", "sample_rate", "is_last"):
        assert k in last
    assert last["is_last"] is True


def test_vad_detects_silence_vs_loud() -> None:
    """Sanity-check the energy VAD — silence below threshold, loud above."""
    from voice_service.vad import EnergyVAD

    vad = EnergyVAD()
    silence = b"\x00\x00" * 320  # 20 ms @ 16 kHz
    # int16 max amplitude square wave-ish = definitely speech.
    import struct

    loud = struct.pack("<320h", *([20000, -20000] * 160))
    assert vad.is_speech(silence) is False
    assert vad.is_speech(loud) is True


def test_mock_mode_does_not_import_real_backends() -> None:
    """In mock mode, faster-whisper/piper must NOT be imported by the service."""
    import sys

    # Force backends to re-instantiate in mock mode.
    from voice_service import api

    api.reset_backends()
    os.environ["MOCK_VOICE"] = "1"
    _ = api.get_stt()
    _ = api.get_tts()
    assert "faster_whisper" not in sys.modules
    assert "piper" not in sys.modules
