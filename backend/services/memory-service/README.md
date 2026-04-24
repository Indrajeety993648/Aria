# memory-service

Four-namespace long-term memory for ARIA.

| Namespace      | Backend                      | Use for                                   |
| -------------- | ---------------------------- | ----------------------------------------- |
| `episodic`     | vector                       | Past turns / events                       |
| `semantic`     | vector                       | Facts about the world                     |
| `relationship` | vector **+** graph (SQLite)  | Who-knows-who edges between contacts      |
| `preference`   | vector                       | User tastes, routines, preferences        |

The vector backend is Qdrant when `QDRANT_URL` is set and reachable,
otherwise an in-process NumPy cosine store (logs a warning at startup). Both
paths implement the same `VectorStore` interface.

## Endpoints

| Method | Path                          | Body / Response                        |
| ------ | ----------------------------- | -------------------------------------- |
| POST   | `/write`                      | `MemoryWrite` → `{ok, key}`            |
| POST   | `/query`                      | `MemoryQuery` → `list[MemoryHit]`      |
| DELETE | `/memory/{namespace}/{key}`   | → `{deleted}`                          |
| GET    | `/stats`                      | → `{counts, backend, graph_nodes}`     |
| GET    | `/health`                     | → `{status: "healthy"}`                |

DTOs are defined in `aria_contracts.memory`.

### Relationship writes

For `namespace: "relationship"`, the write's `key` becomes the source node. If
`metadata` contains any of `to` / `target` / `dst` / `contact` (string), an
edge is added from `key` → that value. Edge kind defaults to `knows` but can
be overridden via `kind` / `relation` / `edge` in metadata.

Example:

```json
{
  "namespace": "relationship",
  "key": "alice",
  "content": "Alice — teammate, designer",
  "metadata": {"to": "bob", "kind": "reports_to"}
}
```

## Run

### Local

```bash
pip install -e backend/packages/aria-contracts
pip install -e backend/services/memory-service
python -m memory_service.server             # http://localhost:8004
```

### Docker

```bash
docker build -f backend/services/memory-service/Dockerfile -t aria-memory .
docker run --rm -p 8004:8004 aria-memory
```

Set `QDRANT_URL=http://qdrant:6333` to use Qdrant; unset or unreachable ⇒
in-memory fallback.

## Test

```bash
pytest backend/services/memory-service/tests -q
```

All tests run fully offline — no Qdrant, no model downloads.

## Swapping the embedder

`src/memory_service/embedder.py` ships a deterministic hash-based 128-dim
embedder. It is **not** a real language model; it's a dependency-free stand-in
for offline demos and CI. To wire a real model in production:

```python
# memory_service/embedder.py
from sentence_transformers import SentenceTransformer
_model = SentenceTransformer("all-MiniLM-L6-v2")

def _embed(text: str) -> list[float]:
    return _model.encode(text, normalize_embeddings=True).tolist()
```

Keep `EMBED_DIM` in sync with the model's output dimension and clear any
existing Qdrant collections (dimensions are baked into the collection).
