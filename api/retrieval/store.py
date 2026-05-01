"""ChromaDB-backed retrieval store over the public mock_sources corpus.

ChromaDB ships with a default sentence-transformers embedder, so this layer
runs with zero API keys for the demo path. For a production deployment, swap
the collection's embedding_function to OpenAI / Vertex / Cohere embeddings.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI

from api.schemas.pipeline import AuthorityType, RetrievedReference

_DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "mock_sources"
_COLLECTION_NAME = "decision_lens_corpus"


class RetrievalStore:
    """Single-process Chroma client + corpus ingest + per-issue query."""

    def __init__(self, persist_dir: str | None = None, corpus_dir: Path | None = None) -> None:
        self._client: ClientAPI = (
            chromadb.PersistentClient(path=persist_dir) if persist_dir else chromadb.Client()
        )
        self._collection = self._client.get_or_create_collection(_COLLECTION_NAME)
        self._corpus_dir = corpus_dir or _DEFAULT_CORPUS_DIR
        self._loaded = False

    def ensure_loaded(self) -> None:
        """Idempotent corpus ingest — safe to call on every request."""
        if self._loaded or self._collection.count() > 0:
            self._loaded = True
            return

        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict[str, Any]] = []
        for record in self._iter_records():
            ids.append(record["source_id"])
            docs.append(f"{record['title']}\n\n{record['passage']}")
            metas.append(
                {
                    "title": record["title"],
                    "authority_type": record["authority_type"],
                    "passage": record["passage"],
                    "url": record.get("url") or "",
                    "tags": ",".join(record.get("tags", [])),
                }
            )
        if ids:
            self._collection.add(ids=ids, documents=docs, metadatas=metas)
        self._loaded = True

    def query(self, *, query_text: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Vector search; returns a list of dicts with source_id + metadata + distance."""
        self.ensure_loaded()
        res = self._collection.query(query_texts=[query_text], n_results=top_k)
        out: list[dict[str, Any]] = []
        ids = res.get("ids", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for source_id, meta, dist in zip(ids, metas, dists, strict=False):
            out.append({"source_id": source_id, "meta": meta or {}, "distance": float(dist)})
        return out

    def to_reference(
        self, *, issue_index: int, hit: dict[str, Any]
    ) -> RetrievedReference:
        """Convert a query hit into a typed RetrievedReference."""
        meta = hit["meta"]
        # Chroma returns L2 distance by default; map to a [0,1] relevance score.
        # 0 distance -> 1.0 score; large distance -> ~0.
        score = 1.0 / (1.0 + max(0.0, hit["distance"]))
        return RetrievedReference(
            issue_index=issue_index,
            source_id=hit["source_id"],
            source_title=meta.get("title", hit["source_id"]),
            authority_type=AuthorityType(meta.get("authority_type", "secondary")),
            passage=meta.get("passage", ""),
            url=meta.get("url") or None,
            relevance_score=round(min(1.0, score), 4),
        )

    def _iter_records(self):
        for path in sorted(self._corpus_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


@lru_cache(maxsize=1)
def get_store() -> RetrievalStore:
    """Default singleton store — in-memory Chroma, default mock corpus."""
    return RetrievalStore()
