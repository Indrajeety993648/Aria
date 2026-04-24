"""Vector store abstraction with Qdrant + in-memory NumPy implementations."""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from .embedder import EMBED_DIM, cosine_sim

logger = logging.getLogger(__name__)

# Keep the four contract namespaces mirrored here; the graph backend handles
# 'relationship' separately but relationship vectors are still written to the
# vector store so they can be retrieved by similarity too.
NAMESPACES: tuple[str, ...] = ("episodic", "semantic", "relationship", "preference")


class VectorStore(ABC):
    """Abstract key-value vector store, partitioned by namespace."""

    @abstractmethod
    def upsert(
        self,
        ns: str,
        key: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None: ...

    @abstractmethod
    def query(
        self,
        ns: str,
        query_emb: list[float],
        top_k: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, str, float, dict[str, Any]]]:
        """Return ``[(key, content, score, metadata), ...]`` ordered by score desc."""

    @abstractmethod
    def delete(self, ns: str, key: str) -> bool: ...

    @abstractmethod
    def count(self, ns: str) -> int: ...


# ---------------------------------------------------------------------------
# In-memory fallback — zero dependencies at runtime beyond NumPy.
# ---------------------------------------------------------------------------


class InMemoryVectorStore(VectorStore):
    """Dict-of-dicts store with NumPy cosine similarity.

    Good enough for dev, CI, and the offline grader. Thread-safe via a single
    coarse lock; memory-service is IO-bound so contention isn't a concern at
    hackathon scale.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # {ns: {key: {"content": ..., "embedding": ..., "metadata": ...}}}
        self._data: dict[str, dict[str, dict[str, Any]]] = {
            ns: {} for ns in NAMESPACES
        }

    def _bucket(self, ns: str) -> dict[str, dict[str, Any]]:
        if ns not in self._data:
            self._data[ns] = {}
        return self._data[ns]

    def upsert(
        self,
        ns: str,
        key: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        with self._lock:
            self._bucket(ns)[key] = {
                "content": content,
                "embedding": list(embedding),
                "metadata": dict(metadata),
            }

    def query(
        self,
        ns: str,
        query_emb: list[float],
        top_k: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, str, float, dict[str, Any]]]:
        with self._lock:
            bucket = self._bucket(ns)
            if not bucket:
                return []

            filter_metadata = filter_metadata or {}

            def _matches(md: dict[str, Any]) -> bool:
                return all(md.get(k) == v for k, v in filter_metadata.items())

            results: list[tuple[str, str, float, dict[str, Any]]] = []
            for key, row in bucket.items():
                if not _matches(row["metadata"]):
                    continue
                score = cosine_sim(query_emb, row["embedding"])
                results.append((key, row["content"], score, dict(row["metadata"])))

            results.sort(key=lambda t: t[2], reverse=True)
            return results[:top_k]

    def delete(self, ns: str, key: str) -> bool:
        with self._lock:
            bucket = self._bucket(ns)
            if key in bucket:
                del bucket[key]
                return True
            return False

    def count(self, ns: str) -> int:
        with self._lock:
            return len(self._bucket(ns))


# ---------------------------------------------------------------------------
# Qdrant-backed store — real vector DB when QDRANT_URL is reachable.
# ---------------------------------------------------------------------------


class QdrantVectorStore(VectorStore):
    """Qdrant-backed store, one collection per namespace.

    We always fall back to :class:`InMemoryVectorStore` at the factory level if
    construction or any per-namespace bootstrap fails; callers should rely on
    :func:`build_vector_store` rather than instantiating this directly.
    """

    def __init__(self, url: str) -> None:
        # Import lazily so the module imports cleanly even if qdrant_client
        # isn't installed in a slim dev environment.
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        self._client = QdrantClient(url=url, timeout=2.0)
        self._VectorParams = VectorParams
        self._Distance = Distance

        # Probe connection — this is the early failure point we want.
        self._client.get_collections()

        for ns in NAMESPACES:
            self._ensure_collection(ns)

    def _ensure_collection(self, ns: str) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if ns not in existing:
            self._client.create_collection(
                collection_name=ns,
                vectors_config=self._VectorParams(
                    size=EMBED_DIM, distance=self._Distance.COSINE
                ),
            )

    @staticmethod
    def _point_id(key: str) -> int:
        # Qdrant point IDs must be unsigned int or UUID. Hash the user key to a
        # stable uint64 so callers can keep using arbitrary string keys.
        import hashlib

        return int.from_bytes(
            hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest(),
            "big",
            signed=False,
        )

    def upsert(
        self,
        ns: str,
        key: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        from qdrant_client.http.models import PointStruct

        payload = {"key": key, "content": content, "metadata": dict(metadata)}
        self._client.upsert(
            collection_name=ns,
            points=[
                PointStruct(
                    id=self._point_id(key), vector=list(embedding), payload=payload
                )
            ],
        )

    def query(
        self,
        ns: str,
        query_emb: list[float],
        top_k: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, str, float, dict[str, Any]]]:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue

        qfilter = None
        if filter_metadata:
            qfilter = Filter(
                must=[
                    FieldCondition(
                        key=f"metadata.{k}", match=MatchValue(value=v)
                    )
                    for k, v in filter_metadata.items()
                ]
            )

        hits = self._client.search(
            collection_name=ns,
            query_vector=list(query_emb),
            limit=top_k,
            query_filter=qfilter,
        )
        out: list[tuple[str, str, float, dict[str, Any]]] = []
        for h in hits:
            payload = h.payload or {}
            key = payload.get("key", str(h.id))
            content = payload.get("content", "")
            md = payload.get("metadata", {}) or {}
            # Qdrant cosine ranges in [-1, 1] after normalization; normalize
            # into the [0, 1] contract band to match InMemory behavior.
            raw = float(h.score)
            score = max(0.0, min(1.0, (raw + 1.0) / 2.0))
            out.append((key, content, score, md))
        return out

    def delete(self, ns: str, key: str) -> bool:
        from qdrant_client.http.models import PointIdsList

        try:
            self._client.delete(
                collection_name=ns,
                points_selector=PointIdsList(points=[self._point_id(key)]),
            )
            return True
        except Exception:  # pragma: no cover — defensive only
            logger.exception("qdrant delete failed for ns=%s key=%s", ns, key)
            return False

    def count(self, ns: str) -> int:
        try:
            return int(self._client.count(collection_name=ns, exact=True).count)
        except Exception:  # pragma: no cover — defensive only
            logger.exception("qdrant count failed for ns=%s", ns)
            return 0


def build_vector_store(url: str | None) -> VectorStore:
    """Factory: try Qdrant, log and fall back to in-memory on any failure."""
    if not url:
        logger.info("QDRANT_URL not set — using InMemoryVectorStore")
        return InMemoryVectorStore()
    try:
        store = QdrantVectorStore(url)
        logger.info("connected to Qdrant at %s", url)
        return store
    except Exception as exc:
        logger.warning(
            "Qdrant unreachable at %s (%s) — falling back to InMemoryVectorStore",
            url,
            exc,
        )
        return InMemoryVectorStore()


# Kept for tests: small helper to build a numpy matrix from a list of vectors.
def _stack(vectors: list[list[float]]) -> np.ndarray:
    return np.asarray(vectors, dtype=np.float32)
