"""
Ingestion service — orchestrates the full upload pipeline:

    store bytes (StorageBackend)
      -> parse (FileHandler -> ParsedDocument)
      -> chunk (Chunker -> ChunkRecords)
      -> embed (Embedder, passage prefix)
      -> index (QdrantRAG.upsert with provenance payloads)
      -> persist (Document + Chunk rows in Postgres)

It reports progress through the stages the UI shows ("Chunking… Embedding…
Storing… Done") via an optional callback, and returns the created Document id +
chunk count.

This is deliberately a single cohesive unit so the order and the transactional
boundaries are in one readable place, rather than scattered across the router.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Collection, Document
from app.ingestion.chunker import Chunker
from app.ingestion.handlers.registry import get_handler_for
from app.rag.embedder import Embedder
from app.rag.qdrant_client import QdrantRAG
from app.storage.base import StorageBackend

ProgressCb = Callable[[str], None] | None


class IngestionService:
    def __init__(
        self,
        *,
        storage: StorageBackend,
        qdrant: QdrantRAG | None = None,
        chunker: Chunker | None = None,
        embedder: Embedder | None = None,
    ):
        self._storage = storage
        self._qdrant = qdrant or QdrantRAG()
        self._chunker = chunker or Chunker()
        self._embedder = embedder or Embedder()

    async def ingest(
        self,
        *,
        session: AsyncSession,
        collection: Collection,
        data: bytes,
        filename: str,
        source_version: str | None = None,
        published_date=None,
        source_url: str | None = None,
        progress: ProgressCb = None,
    ) -> Document:
        def _emit(stage: str) -> None:
            if progress:
                progress(stage)

        # 1. STORE raw bytes via the active backend.
        _emit("storing")
        stored = await self._storage.store_file(
            data=data, filename=filename, collection_id=str(collection.id)
        )

        # 2. PARSE -> pages.
        _emit("parsing")
        handler = get_handler_for(filename)
        parsed = handler.extract(data=data, filename=filename)

        # 3. CHUNK.
        _emit("chunking")
        chunk_records = self._chunker.chunk(parsed)
        if not chunk_records:
            raise ValueError(f"No extractable text in {filename!r}")

        # 4. EMBED (passage prefix) — batch all chunks at once.
        _emit("embedding")
        vectors = self._embedder.embed_passages([c.text for c in chunk_records])

        # 5. Persist Document + Chunk rows; build Qdrant points with provenance.
        _emit("indexing")
        document = Document(
            id=uuid.uuid4(),
            collection_id=collection.id,
            filename=filename,
            storage_locator=stored.locator,
            storage_backend=stored.backend_name,
            source_version=source_version,
            published_date=published_date,
            source_url=source_url,
            chunk_count=len(chunk_records),
        )
        session.add(document)

        point_ids: list[str] = []
        payloads: list[dict] = []
        for rec in chunk_records:
            chunk = Chunk(
                id=uuid.uuid4(),
                document_id=document.id,
                qdrant_point_id=uuid.uuid4(),
                chunk_index=rec.chunk_index,
                text=rec.text,
                page_number=rec.page_number,
                section=rec.section,
                token_count=rec.token_count,
            )
            session.add(chunk)
            point_ids.append(str(chunk.qdrant_point_id))
            payloads.append(
                {
                    "chunk_id": str(chunk.id),
                    "document_id": str(document.id),
                    "text": rec.text,
                    "filename": filename,
                    "page_number": rec.page_number,
                    "section": rec.section,
                    "corpus_type": collection.corpus_type.value,
                    "collection_name": collection.name,
                    "source_version": source_version,
                }
            )

        # 6. INDEX into Qdrant (ensure collection exists first).
        await self._qdrant.ensure_collection(collection.qdrant_collection)
        await self._qdrant.upsert_chunks(
            collection=collection.qdrant_collection,
            point_ids=point_ids,
            vectors=vectors,
            payloads=payloads,
        )

        await session.commit()
        await session.refresh(document)
        _emit("done")
        return document
