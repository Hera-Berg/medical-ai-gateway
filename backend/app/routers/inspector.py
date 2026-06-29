"""
RAG Inspector router — the developer/diagnostic surface.

Endpoints:
  GET  /inspector/overview
        Per-collection + global chunk/vector counts.
  GET  /inspector/collections/{collection_id}/chunks
        Every chunk in a collection (text, index, page, provenance) WITH its
        embedding vector pulled from Qdrant — for the expandable chunk view and
        the truncated-vector / copy-full-vector display.
  POST /inspector/dry-run
        Live similarity search: embed a query, return ranked chunks with scores
        and provenance. NO LLM is called — this is pure retrieval, exactly what
        the inspector's "live RAG dry-run" needs.
  GET  /inspector/collections/{collection_id}/scatter
        Server-side PCA -> 2D coords per chunk (+ text/provenance for hover),
        for the similarity scatter plot.

All read-only and side-effect-free; safe to hammer from the UI.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Collection, Document
from app.db.session import get_db
from app.rag.qdrant_client import QdrantRAG
from app.rag.reducer import reduce_to_2d
from app.rag.retriever import Retriever

router = APIRouter(prefix="/inspector", tags=["inspector"])


# ── overview ────────────────────────────────────────────────────────────────
@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    """Per-collection and global chunk/vector counts."""
    collections = (await db.execute(select(Collection))).scalars().all()
    qdrant = QdrantRAG()

    out_collections = []
    global_chunks = 0
    global_vectors = 0
    for c in collections:
        # chunk count from PG
        n_chunks = len(
            (
                await db.execute(
                    select(Chunk.id)
                    .join(Document, Chunk.document_id == Document.id)
                    .where(Document.collection_id == c.id)
                )
            )
            .scalars()
            .all()
        )
        # vector count from Qdrant (source of truth for what's indexed)
        try:
            stats = await qdrant.collection_stats(c.qdrant_collection)
            n_vectors = stats["points_count"] or 0
        except Exception:
            n_vectors = 0
        global_chunks += n_chunks
        global_vectors += n_vectors
        out_collections.append(
            {
                "id": str(c.id),
                "name": c.name,
                "corpus_type": c.corpus_type.value,
                "qdrant_collection": c.qdrant_collection,
                "chunk_count": n_chunks,
                "vector_count": n_vectors,
            }
        )

    return {
        "collections": out_collections,
        "global_chunk_count": global_chunks,
        "global_vector_count": global_vectors,
    }


# ── chunks with vectors ─────────────────────────────────────────────────────
@router.get("/collections/{collection_id}/chunks")
async def collection_chunks(
    collection_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Every chunk in the collection, grouped by document, each with its vector."""
    coll = await db.get(Collection, collection_id)
    if coll is None:
        raise HTTPException(status_code=404, detail="collection not found")

    documents = (
        (
            await db.execute(
                select(Document)
                .where(Document.collection_id == collection_id)
                .order_by(Document.uploaded_at)
            )
        )
        .scalars()
        .all()
    )

    qdrant = QdrantRAG()
    out_docs = []
    for doc in documents:
        chunks = (
            (
                await db.execute(
                    select(Chunk)
                    .where(Chunk.document_id == doc.id)
                    .order_by(Chunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )
        # pull vectors for all this doc's points in one call
        point_ids = [str(ch.qdrant_point_id) for ch in chunks]
        vectors = await qdrant.get_vectors_by_point_ids(
            collection=coll.qdrant_collection, point_ids=point_ids
        )
        out_chunks = []
        for ch in chunks:
            vec = vectors.get(str(ch.qdrant_point_id))
            out_chunks.append(
                {
                    "id": str(ch.id),
                    "chunk_index": ch.chunk_index,
                    "text": ch.text,
                    "page_number": ch.page_number,
                    "section": ch.section,
                    "token_count": ch.token_count,
                    "vector": vec,           # full vector (frontend truncates display)
                    "vector_dim": len(vec) if vec else None,
                }
            )
        out_docs.append(
            {
                "document_id": str(doc.id),
                "filename": doc.filename,
                "source_version": doc.source_version,
                "chunk_count": doc.chunk_count,
                "chunks": out_chunks,
            }
        )

    return {
        "collection": {
            "id": str(coll.id),
            "name": coll.name,
            "corpus_type": coll.corpus_type.value,
        },
        "documents": out_docs,
    }


# ── dry-run search (no LLM) ─────────────────────────────────────────────────
class DryRunRequest(BaseModel):
    query: str
    collection_ids: list[uuid.UUID] | None = None  # None = all collections
    limit: int = 8


@router.post("/dry-run")
async def dry_run(body: DryRunRequest, db: AsyncSession = Depends(get_db)):
    """Embed the query and return ranked chunks with scores — no LLM call."""
    # Resolve scope -> qdrant collection names.
    stmt = select(Collection)
    if body.collection_ids:
        stmt = stmt.where(Collection.id.in_(body.collection_ids))
    collections = (await db.execute(stmt)).scalars().all()
    qdrant_names = [c.qdrant_collection for c in collections]
    if not qdrant_names:
        return {"query": body.query, "results": []}

    retriever = Retriever()
    items = await retriever.retrieve(
        query_text=body.query, collections=qdrant_names, limit=body.limit
    )
    return {
        "query": body.query,
        "results": [
            {
                "text": it.text,
                "similarity_score": it.similarity_score,
                "similarity_percent": round(it.similarity_score * 100, 1),
                "source_filename": it.source_filename,
                "source_corpus_type": it.source_corpus_type,
                "source_collection_name": it.source_collection_name,
                "source_page": it.source_page,
                "source_version": it.source_version,
            }
            for it in items
        ],
    }


# ── scatter (server-side PCA) ───────────────────────────────────────────────
@router.get("/collections/{collection_id}/scatter")
async def scatter(collection_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """PCA-project all chunk vectors to 2D for the similarity scatter plot."""
    coll = await db.get(Collection, collection_id)
    if coll is None:
        raise HTTPException(status_code=404, detail="collection not found")

    qdrant = QdrantRAG()
    points = await qdrant.scroll_all_points(
        collection=coll.qdrant_collection, with_vectors=True
    )
    vectors = [p["vector"] for p in points if p["vector"] is not None]
    coords = reduce_to_2d(vectors)

    out = []
    vi = 0
    for p in points:
        if p["vector"] is None:
            continue
        pt = coords[vi]
        vi += 1
        payload = p["payload"]
        out.append(
            {
                "x": pt.x,
                "y": pt.y,
                "text": payload.get("text", ""),
                "page_number": payload.get("page_number"),
                "filename": payload.get("filename"),
            }
        )

    return {
        "collection": {"id": str(coll.id), "name": coll.name, "corpus_type": coll.corpus_type.value},
        "method": "pca",
        "point_count": len(out),
        "points": out,
    }
