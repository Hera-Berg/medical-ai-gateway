"""
Retriever — the RAG read path.

Cross-corpus by design: a query can be scoped to one collection or run across
several (e.g. authoritative guidelines + the personal record). We query each
collection, then merge by similarity score and take the global top-k. Every
result carries the provenance the thinking-panel chunk cards and the
retrieved_chunks rows need — including which corpus it came from, so the
trust-boundary distinction is visible end to end.

This module does NOT call any LLM — it's pure retrieval, which is exactly what
the RAG Inspector's "live dry-run" surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rag.embedder import Embedder
from app.rag.qdrant_client import QdrantRAG


@dataclass
class RetrievedItem:
    """One retrieved chunk with score + full provenance (mirrors payload)."""

    chunk_id: str | None
    document_id: str | None
    text: str
    similarity_score: float          # cosine, 0..1 (higher = more similar)
    source_filename: str
    source_corpus_type: str          # 'authoritative' | 'personal'
    source_collection_name: str
    source_page: int | None
    source_section: str | None
    source_version: str | None


class Retriever:
    def __init__(self, qdrant: QdrantRAG | None = None, embedder: Embedder | None = None):
        self._qdrant = qdrant or QdrantRAG()
        self._embedder = embedder or Embedder()

    async def retrieve(
        self,
        *,
        query_text: str,
        collections: list[str],
        limit: int = 5,
    ) -> list[RetrievedItem]:
        """
        Embed the query once, search each collection, merge, return global top-k.
        `collections` are Qdrant collection names (resolved from the app
        Collection rows in scope).
        """
        qvec = self._embedder.embed_query(query_text)

        merged: list[RetrievedItem] = []
        for coll in collections:
            try:
                points = await self._qdrant.search(
                    collection=coll, query_vector=qvec, limit=limit
                )
            except Exception:
                # A missing/empty collection shouldn't abort a cross-corpus query.
                continue
            for p in points:
                payload = p.payload or {}
                merged.append(
                    RetrievedItem(
                        chunk_id=payload.get("chunk_id"),
                        document_id=payload.get("document_id"),
                        text=payload.get("text", ""),
                        similarity_score=float(p.score),
                        source_filename=payload.get("filename", "unknown"),
                        source_corpus_type=payload.get("corpus_type", "unknown"),
                        source_collection_name=payload.get("collection_name", coll),
                        source_page=payload.get("page_number"),
                        source_section=payload.get("section"),
                        source_version=payload.get("source_version"),
                    )
                )

        # Global ranking across all queried collections.
        merged.sort(key=lambda r: r.similarity_score, reverse=True)
        return merged[:limit]
