"""FastAPI routes for the ARIA memory-service.

Implements the ``MemoryWrite`` / ``MemoryQuery`` / ``MemoryHit`` contracts
across four namespaces (episodic, semantic, relationship, preference). The
``relationship`` namespace additionally maintains a SQLite + NetworkX edge
graph; the other three are vector-only.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from aria_contracts.memory import MemoryHit, MemoryQuery, MemoryWrite
from fastapi import Depends, FastAPI, HTTPException, Path
from pydantic import BaseModel

from .embedder import _embed
from .graph_store import GraphStore
from .vector_store import NAMESPACES, VectorStore, build_vector_store

logger = logging.getLogger(__name__)

# Metadata keys the relationship namespace uses to hint at graph structure.
# Presence of either triggers an edge upsert in addition to the vector upsert.
_REL_TO_KEYS = ("to", "target", "dst", "contact")
_REL_KIND_KEYS = ("kind", "relation", "edge")


class WriteResponse(BaseModel):
    ok: bool
    key: str


class DeleteResponse(BaseModel):
    deleted: bool


class StatsResponse(BaseModel):
    counts: dict[str, int]
    backend: str
    graph_nodes: int


class HealthResponse(BaseModel):
    status: str


def _rel_edge_from_metadata(
    key: str, metadata: dict[str, Any]
) -> tuple[str, str, str] | None:
    """Pull (src, dst, kind) out of metadata for a relationship write.

    The convention is simple: the write's ``key`` is the source, and any of
    ``to`` / ``target`` / ``dst`` / ``contact`` in ``metadata`` supplies the
    destination. Edge kind defaults to ``knows`` unless overridden.
    """
    dst: str | None = None
    for k in _REL_TO_KEYS:
        v = metadata.get(k)
        if isinstance(v, str) and v:
            dst = v
            break
    if dst is None:
        return None
    kind = "knows"
    for k in _REL_KIND_KEYS:
        v = metadata.get(k)
        if isinstance(v, str) and v:
            kind = v
            break
    return (key, dst, kind)


def build_app(
    vector_store: VectorStore | None = None,
    graph_store: GraphStore | None = None,
) -> FastAPI:
    """Construct the FastAPI app. Injectable stores make testing trivial."""
    app = FastAPI(
        title="ARIA memory-service",
        version="0.1.0",
        description=(
            "Four-namespace memory: episodic, semantic, relationship, "
            "preference. Vector backend is Qdrant with in-memory fallback; "
            "relationship namespace additionally maintains a SQLite + "
            "NetworkX graph."
        ),
    )

    # Lazy construction — never hit the network at import time.
    vstore = vector_store or build_vector_store(os.getenv("QDRANT_URL"))
    gstore = graph_store or GraphStore(
        os.getenv("MEMORY_GRAPH_DB", ":memory:")
    )

    app.state.vector_store = vstore
    app.state.graph_store = gstore

    def get_vector_store() -> VectorStore:
        return app.state.vector_store

    def get_graph_store() -> GraphStore:
        return app.state.graph_store

    # --------------------------------------------------------------- health

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="healthy")

    # ---------------------------------------------------------------- write

    @app.post("/write", response_model=WriteResponse)
    def write(
        payload: MemoryWrite,
        vs: VectorStore = Depends(get_vector_store),
        gs: GraphStore = Depends(get_graph_store),
    ) -> WriteResponse:
        if payload.namespace not in NAMESPACES:
            raise HTTPException(
                status_code=400,
                detail=f"unknown namespace: {payload.namespace}",
            )

        embedding = payload.embedding or _embed(payload.content)
        vs.upsert(
            payload.namespace,
            payload.key,
            payload.content,
            embedding,
            payload.metadata,
        )

        if payload.namespace == "relationship":
            gs.upsert_node(payload.key, payload.content, payload.metadata)
            edge = _rel_edge_from_metadata(payload.key, payload.metadata)
            if edge is not None:
                src, dst, kind = edge
                # Make sure the destination node exists as an empty placeholder
                # if we haven't seen it yet — keeps neighbors() honest.
                if gs.get_node(dst) is None:
                    gs.upsert_node(dst, content="", metadata={})
                gs.upsert_edge(src, dst, kind=kind, metadata=payload.metadata)

        return WriteResponse(ok=True, key=payload.key)

    # ---------------------------------------------------------------- query

    @app.post("/query", response_model=list[MemoryHit])
    def query(
        payload: MemoryQuery,
        vs: VectorStore = Depends(get_vector_store),
    ) -> list[MemoryHit]:
        if payload.namespace not in NAMESPACES:
            raise HTTPException(
                status_code=400,
                detail=f"unknown namespace: {payload.namespace}",
            )
        if payload.query_text is None and payload.query_embedding is None:
            raise HTTPException(
                status_code=400,
                detail="query_text or query_embedding is required",
            )

        query_emb = payload.query_embedding or _embed(payload.query_text or "")
        hits = vs.query(
            payload.namespace,
            query_emb,
            payload.top_k,
            payload.filter_metadata or None,
        )
        return [
            MemoryHit(key=k, content=c, score=float(s), metadata=md)
            for (k, c, s, md) in hits
        ]

    # --------------------------------------------------------------- delete

    @app.delete(
        "/memory/{namespace}/{key}", response_model=DeleteResponse
    )
    def delete(
        namespace: str = Path(...),
        key: str = Path(...),
        vs: VectorStore = Depends(get_vector_store),
        gs: GraphStore = Depends(get_graph_store),
    ) -> DeleteResponse:
        if namespace not in NAMESPACES:
            raise HTTPException(
                status_code=400, detail=f"unknown namespace: {namespace}"
            )
        deleted = vs.delete(namespace, key)
        if namespace == "relationship":
            deleted = gs.delete_node(key) or deleted
        return DeleteResponse(deleted=deleted)

    # ---------------------------------------------------------------- stats

    @app.get("/stats", response_model=StatsResponse)
    def stats(
        vs: VectorStore = Depends(get_vector_store),
        gs: GraphStore = Depends(get_graph_store),
    ) -> StatsResponse:
        counts = {ns: vs.count(ns) for ns in NAMESPACES}
        return StatsResponse(
            counts=counts,
            backend=type(vs).__name__,
            graph_nodes=gs.count(),
        )

    return app
