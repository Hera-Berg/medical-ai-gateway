"""
Documents router — upload / list / delete.

Upload drives the full ingestion pipeline via IngestionService, using the
ACTIVE storage backend (resolved per request from app_config). Delete removes
the PG rows (cascading to chunks), the stored file, and the Qdrant vectors —
the three-place cleanup the spec calls for.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Collection, Document
from app.db.session import get_db
from app.ingestion.service import IngestionService
from app.rag.qdrant_client import QdrantRAG
from app.schemas.rag import DocumentOut
from app.storage.registry import get_active_backend

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut)
async def upload_document(
    collection_id: uuid.UUID = Form(...),
    source_version: str | None = Form(None),
    published_date: date | None = Form(None),
    source_url: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    coll = await db.get(Collection, collection_id)
    if coll is None:
        raise HTTPException(status_code=404, detail="collection not found")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")

    storage = await get_active_backend(db)
    service = IngestionService(storage=storage)
    try:
        document = await service.ingest(
            session=db,
            collection=coll,
            data=data,
            filename=file.filename or "upload.pdf",
            source_version=source_version,
            published_date=published_date,
            source_url=source_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    collection_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).order_by(Document.uploaded_at.desc())
    if collection_id is not None:
        stmt = stmt.where(Document.collection_id == collection_id)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


@router.delete("/{document_id}")
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    coll = await db.get(Collection, doc.collection_id)

    locator = doc.storage_locator
    qdrant_collection = coll.qdrant_collection if coll else None

    # 1. PG rows (chunks cascade via FK).
    await db.delete(doc)
    await db.commit()

    # 2. Qdrant vectors for this document.
    if qdrant_collection:
        try:
            await QdrantRAG().delete_document(
                collection=qdrant_collection, document_id=str(document_id)
            )
        except Exception:
            pass

    # 3. Stored file via the active backend.
    try:
        storage = await get_active_backend(db)
        await storage.delete_file(locator=locator)
    except Exception:
        pass

    return {"deleted": str(document_id)}
