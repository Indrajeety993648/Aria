"""Memory-service API tests — offline only, no Qdrant required."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from memory_service import vector_store as vs_mod
from memory_service.api import build_app
from memory_service.embedder import EMBED_DIM, _embed, cosine_sim
from memory_service.graph_store import GraphStore
from memory_service.vector_store import (
    InMemoryVectorStore,
    build_vector_store,
)

NAMESPACES = ("episodic", "semantic", "relationship", "preference")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client() -> TestClient:
    app = build_app(
        vector_store=InMemoryVectorStore(),
        graph_store=GraphStore(":memory:"),
    )
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Embedder
# --------------------------------------------------------------------------- #


def test_embedder_dim_and_determinism() -> None:
    v = _embed("hello world")
    assert len(v) == EMBED_DIM
    assert _embed("hello world") == v


def test_embedder_self_similarity_is_max() -> None:
    v = _embed("meeting with alice tomorrow")
    assert cosine_sim(v, v) == pytest.approx(1.0, abs=1e-6)


def test_cosine_ordering_prefers_similar_text() -> None:
    q = _embed("alice and bob met for coffee")
    near = _embed("alice met bob over coffee")
    far = _embed("serialized protobuf encoding benchmarks")
    assert cosine_sim(q, near) > cosine_sim(q, far)


# --------------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------------- #


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


# --------------------------------------------------------------------------- #
# Write / query round-trip for every namespace
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("ns", NAMESPACES)
def test_write_query_roundtrip_per_namespace(
    client: TestClient, ns: str
) -> None:
    r = client.post(
        "/write",
        json={
            "namespace": ns,
            "key": f"{ns}-k1",
            "content": f"a memory about alice in the {ns} namespace",
            "metadata": {"source": "test"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "key": f"{ns}-k1"}

    r = client.post(
        "/query",
        json={
            "namespace": ns,
            "query_text": "alice",
            "top_k": 3,
        },
    )
    assert r.status_code == 200, r.text
    hits = r.json()
    assert len(hits) == 1
    assert hits[0]["key"] == f"{ns}-k1"
    assert 0.0 <= hits[0]["score"] <= 1.0


# --------------------------------------------------------------------------- #
# Cosine ordering via the HTTP surface
# --------------------------------------------------------------------------- #


def test_query_orders_by_similarity(client: TestClient) -> None:
    items = [
        ("a", "alice scheduled coffee with bob"),
        ("b", "alice and bob met for coffee yesterday"),
        ("c", "kernel scheduler latency benchmarks on linux"),
    ]
    for key, content in items:
        r = client.post(
            "/write",
            json={
                "namespace": "episodic",
                "key": key,
                "content": content,
            },
        )
        assert r.status_code == 200, r.text

    r = client.post(
        "/query",
        json={
            "namespace": "episodic",
            "query_text": "alice met bob for coffee",
            "top_k": 3,
        },
    )
    assert r.status_code == 200
    hits = r.json()
    assert [h["key"] for h in hits[:2]] == sorted(
        ["a", "b"], key=lambda k: k
    ) or hits[0]["key"] in {"a", "b"}
    # The unrelated kernel doc must rank last.
    assert hits[-1]["key"] == "c"
    # Scores must be non-increasing.
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- #
# Metadata filtering
# --------------------------------------------------------------------------- #


def test_query_respects_metadata_filter(client: TestClient) -> None:
    for i, tag in enumerate(["work", "personal", "work"]):
        client.post(
            "/write",
            json={
                "namespace": "semantic",
                "key": f"f{i}",
                "content": f"fact {i} about the world",
                "metadata": {"tag": tag},
            },
        )
    r = client.post(
        "/query",
        json={
            "namespace": "semantic",
            "query_text": "fact",
            "top_k": 10,
            "filter_metadata": {"tag": "work"},
        },
    )
    assert r.status_code == 200
    hits = r.json()
    assert {h["key"] for h in hits} == {"f0", "f2"}


# --------------------------------------------------------------------------- #
# Delete
# --------------------------------------------------------------------------- #


def test_delete_removes_item(client: TestClient) -> None:
    client.post(
        "/write",
        json={
            "namespace": "preference",
            "key": "p1",
            "content": "user likes decaf after 3pm",
        },
    )
    r = client.delete("/memory/preference/p1")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}

    r2 = client.delete("/memory/preference/p1")
    assert r2.status_code == 200
    assert r2.json() == {"deleted": False}


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #


def test_stats_counts(client: TestClient) -> None:
    client.post(
        "/write",
        json={
            "namespace": "episodic",
            "key": "e1",
            "content": "first episode",
        },
    )
    client.post(
        "/write",
        json={
            "namespace": "relationship",
            "key": "alice",
            "content": "alice is a teammate",
            "metadata": {"to": "bob"},
        },
    )
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["episodic"] == 1
    assert body["counts"]["relationship"] == 1
    assert body["graph_nodes"] >= 2  # alice + bob placeholder
    assert body["backend"] == "InMemoryVectorStore"


# --------------------------------------------------------------------------- #
# Relationship: graph edges are materialized on write
# --------------------------------------------------------------------------- #


def test_relationship_write_creates_graph_edge() -> None:
    gstore = GraphStore(":memory:")
    app = build_app(vector_store=InMemoryVectorStore(), graph_store=gstore)
    c = TestClient(app)

    c.post(
        "/write",
        json={
            "namespace": "relationship",
            "key": "alice",
            "content": "Alice, team lead",
            "metadata": {"to": "bob", "kind": "manages"},
        },
    )
    assert "alice" in gstore.all_nodes()
    assert gstore.neighbors("alice") == ["bob"]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_query_requires_text_or_embedding(client: TestClient) -> None:
    r = client.post(
        "/query",
        json={"namespace": "episodic", "top_k": 3},
    )
    assert r.status_code == 400


def test_query_unknown_namespace_rejected(client: TestClient) -> None:
    r = client.post(
        "/query",
        json={"namespace": "bogus", "query_text": "x"},
    )
    # Pydantic rejects the Literal before we see it (422) — either is fine.
    assert r.status_code in (400, 422)


# --------------------------------------------------------------------------- #
# Qdrant fallback: monkeypatch QdrantClient to blow up on connect.
# --------------------------------------------------------------------------- #


def test_qdrant_connection_failure_falls_back_to_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BoomClient:
        def __init__(self, *a, **kw) -> None:
            raise ConnectionError("simulated: qdrant unreachable")

    # Patch the Qdrant import path so construction fails on first touch.
    import qdrant_client

    monkeypatch.setattr(qdrant_client, "QdrantClient", _BoomClient)

    store = build_vector_store("http://does-not-exist:6333")
    assert isinstance(store, InMemoryVectorStore)

    # And the end-to-end app works through it.
    app = build_app(vector_store=store, graph_store=GraphStore(":memory:"))
    c = TestClient(app)
    r = c.post(
        "/write",
        json={"namespace": "episodic", "key": "q1", "content": "hi"},
    )
    assert r.status_code == 200
    r = c.post(
        "/query",
        json={"namespace": "episodic", "query_text": "hi", "top_k": 1},
    )
    assert r.status_code == 200
    assert r.json()[0]["key"] == "q1"


def test_build_vector_store_without_url_uses_in_memory() -> None:
    store = build_vector_store(None)
    assert isinstance(store, InMemoryVectorStore)
    assert store.count("episodic") == 0


def test_vector_store_module_exports_namespaces() -> None:
    # Guardrail: keeps the module in sync with the contract Literal.
    from aria_contracts.memory import MemoryNamespace
    from typing import get_args

    assert set(get_args(MemoryNamespace)) == set(vs_mod.NAMESPACES)
