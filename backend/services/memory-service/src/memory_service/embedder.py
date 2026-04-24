"""Tiny deterministic hash-based text embedder.

IMPORTANT — PRODUCTION NOTE
---------------------------
This embedder is *not* a real language model. It hashes character n-grams into a
fixed-dimension vector and L2-normalizes. It preserves enough signal that
identical text scores 1.0 against itself and similar text outscores unrelated
text, which is all we need for offline demos, CI, and hackathon judging.

For production, replace ``_embed`` with a real model:

    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer("all-MiniLM-L6-v2")
    def _embed(text: str) -> list[float]:
        return _model.encode(text, normalize_embeddings=True).tolist()

No model files, no network calls, no downloads happen in the current module —
the judge can run us fully offline.
"""

from __future__ import annotations

import hashlib
import math

EMBED_DIM: int = 128


def _embed(text: str) -> list[float]:
    """Deterministically hash ``text`` to a 128-dim L2-normalized vector.

    Strategy: collect character n-grams (n=3 and n=4), hash each to a bucket in
    ``[0, EMBED_DIM)`` with a sign bit, accumulate, then normalize. Works
    offline, is stable across runs, and gives non-trivial cosine similarity
    between texts that share substrings.
    """
    if not text:
        # Zero vector for empty input. cosine_sim treats this as score 0.
        return [0.0] * EMBED_DIM

    normalized = text.lower().strip()
    vec = [0.0] * EMBED_DIM

    tokens: list[str] = []
    tokens.extend(normalized.split())
    for n in (3, 4):
        for i in range(len(normalized) - n + 1):
            tokens.append(normalized[i : i + n])

    for tok in tokens:
        h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(h[:4], "little") % EMBED_DIM
        sign = 1.0 if (h[4] & 1) else -1.0
        vec[bucket] += sign

    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity, clamped to ``[0.0, 1.0]`` for the MemoryHit contract.

    The contract's ``score`` field is bounded in ``[0, 1]``; we map raw cosine
    in ``[-1, 1]`` to that range via ``(x + 1) / 2`` so negative similarities
    still appear as small positive scores.
    """
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    cos = dot / (math.sqrt(na) * math.sqrt(nb))
    # Clamp numerical drift, map [-1, 1] -> [0, 1].
    cos = max(-1.0, min(1.0, cos))
    return (cos + 1.0) / 2.0
