from __future__ import annotations

from dataclasses import dataclass

from app.rag.embedder import Embedder
from app.rag.qdrant_client import QdrantRAG


@dataclass
class RetrievedItem:
    chunk_id: str | None
    document_id: str | None
    text: str
    similarity_score: float
    source_filename: str
    source_corpus_type: str
    source_collection_name: str
    source_page: int | None
    source_section: str | None
    source_version: str | None


class Retriever:
    def __init__(
        self, qdrant: QdrantRAG | None = None, embedder: Embedder | None = None
    ):
        self._qdrant = qdrant or QdrantRAG()
        self._embedder = embedder or Embedder()

    async def retrieve(
        self,
        *,
        query_text: str,
        collections: list[str],
        limit: int = 5,
    ) -> list[RetrievedItem]:
        qvec = self._embedder.embed_query(query_text)

        merged: list[RetrievedItem] = []
        for coll in collections:
            try:
                points = await self._qdrant.search(
                    collection=coll, query_vector=qvec, limit=limit
                )
            except Exception:
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

        merged.sort(key=lambda r: r.similarity_score, reverse=True)
        return merged[:limit]
