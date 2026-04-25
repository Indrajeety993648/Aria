"""ElevenLabs TTS tests — the real API never gets hit.

We stub `httpx.AsyncClient.stream` with a fake async-streaming context that
yields a canned PCM byte sequence. Verifies:
  - backend resolves when TTS_BACKEND=elevenlabs and a key is present
  - refuses to instantiate without a key
  - re-chunks PCM into 20 ms slices
  - emits at least one `is_last=True` chunk to close the stream cleanly
"""
from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager

import pytest
from aria_contracts.voice import TTSRequest


# ----------------------------------------------------------------------------
# fake httpx streaming response
# ----------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status: int, chunks: list[bytes]) -> None:
        self.status_code = status
        self._chunks = chunks

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c

    async def aread(self) -> bytes:
        return b""


class _FakeClient:
    def __init__(self, chunks: list[bytes], status: int = 200) -> None:
        self._chunks = chunks
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @asynccontextmanager
    async def stream(self, method: str, url: str, headers=None, json=None):  # noqa: ARG002
        yield _FakeResp(self._status, self._chunks)


# ----------------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------------


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    from voice_service.elevenlabs_tts import ElevenLabsTTS

    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        ElevenLabsTTS()


def test_selector_resolves_elevenlabs(monkeypatch):
    monkeypatch.setenv("MOCK_VOICE", "0")
    monkeypatch.setenv("TTS_BACKEND", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    from voice_service import api as api_mod

    api_mod.reset_backends()
    backend = api_mod.get_tts()
    assert backend.__class__.__name__ == "ElevenLabsTTS"
    api_mod.reset_backends()


@pytest.mark.asyncio
async def test_streaming_rechunks_pcm(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    import httpx

    # 20 ms @ 16 kHz, 16-bit mono = 640 bytes. Emit 3.5 frames of PCM.
    pcm = b"\x01\x02" * (320 * 3) + b"\x03\x04" * 160
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: _FakeClient([pcm[:800], pcm[800:]])
    )

    from voice_service.elevenlabs_tts import ElevenLabsTTS

    tts = ElevenLabsTTS()
    it = await tts.synth(TTSRequest(session_id="s1", text="hi"))
    chunks = [c async for c in it]
    assert len(chunks) >= 4  # 3 full + 1 tail
    # All non-last chunks decode cleanly to 20 ms of pcm
    non_last = [c for c in chunks if not c.is_last]
    for c in non_last:
        assert len(base64.b64decode(c.audio_b64)) == 640
    # Exactly one is_last
    last = [c for c in chunks if c.is_last]
    assert len(last) == 1


@pytest.mark.asyncio
async def test_http_error_raises(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    import httpx

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: _FakeClient([], status=401)
    )

    from voice_service.elevenlabs_tts import ElevenLabsTTS

    tts = ElevenLabsTTS()
    it = await tts.synth(TTSRequest(session_id="s1", text="hi"))
    with pytest.raises(RuntimeError, match="ElevenLabs stream error 401"):
        async for _ in it:
            pass
