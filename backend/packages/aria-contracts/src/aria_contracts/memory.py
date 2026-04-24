"""Memory-service contracts — four namespaces, one API shape."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryNamespace = Literal["episodic", "semantic", "relationship", "preference"]


class MemoryWrite(BaseModel):
    """Write or upsert a memory in a namespace."""

    model_config = ConfigDict(extra="forbid")

    namespace: MemoryNamespace
    key: str
    content: str
    embedding: list[float] | None = Field(
        default=None,
        description="Optional pre-computed embedding; memory-service embeds if absent.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    """Query a namespace by text or embedding."""

    model_config = ConfigDict(extra="forbid")

    namespace: MemoryNamespace
    query_text: str | None = None
    query_embedding: list[float] | None = None
    top_k: int = Field(ge=1, le=100, default=5)
    filter_metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryHit(BaseModel):
    """One result from a memory query."""

    model_config = ConfigDict(extra="forbid")

    key: str
    content: str
    score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
