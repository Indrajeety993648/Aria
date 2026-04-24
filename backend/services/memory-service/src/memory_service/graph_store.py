"""SQLite + NetworkX relationship graph for the ``relationship`` namespace.

The vector store covers semantic-lookup (\"who have we discussed near this
context\"). The graph store covers *structural* queries (\"who are Alice's
direct collaborators?\"). Both get written on `relationship` writes so callers
can pick the view they need.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

import networkx as nx


class GraphStore:
    """SQLite-backed relationship graph with a NetworkX view.

    Schema:
        nodes(key TEXT PRIMARY KEY, content TEXT, metadata TEXT)
        edges(src TEXT, dst TEXT, kind TEXT, metadata TEXT,
              PRIMARY KEY(src, dst, kind))

    The NetworkX ``DiGraph`` is kept as an in-memory mirror that we rebuild
    from SQLite on startup. SQLite is the source of truth; the graph is the
    query accelerator.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        # ``check_same_thread=False`` is safe because every call path goes
        # through ``self._lock``.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                key       TEXT PRIMARY KEY,
                content   TEXT NOT NULL,
                metadata  TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS edges (
                src       TEXT NOT NULL,
                dst       TEXT NOT NULL,
                kind      TEXT NOT NULL DEFAULT 'knows',
                metadata  TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (src, dst, kind)
            );
            """
        )
        self._conn.commit()

        self._graph: nx.DiGraph = nx.DiGraph()
        self._rehydrate()

    def _rehydrate(self) -> None:
        with self._lock:
            self._graph.clear()
            for key, content, md_json in self._conn.execute(
                "SELECT key, content, metadata FROM nodes"
            ):
                self._graph.add_node(
                    key, content=content, metadata=json.loads(md_json)
                )
            for src, dst, kind, md_json in self._conn.execute(
                "SELECT src, dst, kind, metadata FROM edges"
            ):
                self._graph.add_edge(
                    src, dst, kind=kind, metadata=json.loads(md_json)
                )

    # ------------------------------------------------------------------ nodes

    def upsert_node(
        self, key: str, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        md = metadata or {}
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO nodes(key, content, metadata) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    content = excluded.content,
                    metadata = excluded.metadata
                """,
                (key, content, json.dumps(md)),
            )
            self._conn.commit()
            self._graph.add_node(key, content=content, metadata=md)

    def get_node(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT key, content, metadata FROM nodes WHERE key = ?", (key,)
            ).fetchone()
            if not row:
                return None
            return {
                "key": row[0],
                "content": row[1],
                "metadata": json.loads(row[2]),
            }

    def delete_node(self, key: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM nodes WHERE key = ?", (key,))
            self._conn.execute(
                "DELETE FROM edges WHERE src = ? OR dst = ?", (key, key)
            )
            self._conn.commit()
            if self._graph.has_node(key):
                self._graph.remove_node(key)
            return cur.rowcount > 0

    # ------------------------------------------------------------------ edges

    def upsert_edge(
        self,
        src: str,
        dst: str,
        kind: str = "knows",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        md = metadata or {}
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO edges(src, dst, kind, metadata) VALUES (?, ?, ?, ?)
                ON CONFLICT(src, dst, kind) DO UPDATE SET
                    metadata = excluded.metadata
                """,
                (src, dst, kind, json.dumps(md)),
            )
            self._conn.commit()
            self._graph.add_edge(src, dst, kind=kind, metadata=md)

    def neighbors(self, key: str) -> list[str]:
        with self._lock:
            if not self._graph.has_node(key):
                return []
            return list(self._graph.successors(key))

    def all_nodes(self) -> list[str]:
        with self._lock:
            return list(self._graph.nodes())

    def count(self) -> int:
        with self._lock:
            return self._graph.number_of_nodes()
