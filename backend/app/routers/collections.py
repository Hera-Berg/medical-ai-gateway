from __future__ import annotations

import re
import uuid

from app.db.models import Collection
from app.db.session import get_db
from app.rag.qdrant_client import QdrantRAG
from app.schemas.rag import CollectionCreate, CollectionOut
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/collections", tags=["collections"])


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "collection"


@router.post("", response_model=CollectionOut)
async def create_collection(body: CollectionCreate, db: AsyncSession = Depends(get_db)):
    qdrant_name = (
        f"{body.corpus_type.value}__{_slug(body.name)}__{uuid.uuid4().hex[:8]}"
    )
    coll = Collection(
        id=uuid.uuid4(),
        name=body.name,
        corpus_type=body.corpus_type,
        qdrant_collection=qdrant_name,
        description=body.description,
    )
    db.add(coll)
    await db.commit()
    await db.refresh(coll)

    await QdrantRAG().ensure_collection(qdrant_name)
    return coll


@router.get("", response_model=list[CollectionOut])
async def list_collections(db: AsyncSession = Depends(get_db)):
    rows = (
        (await db.execute(select(Collection).order_by(Collection.created_at)))
        .scalars()
        .all()
    )
    return list(rows)


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    coll = await db.get(Collection, collection_id)
    if coll is None:
        raise HTTPException(status_code=404, detail="collection not found")
    qdrant_name = coll.qdrant_collection
    await db.delete(coll)
    await db.commit()
    try:
        await QdrantRAG().client.delete_collection(qdrant_name)
    except Exception:
        pass
    return {"deleted": str(collection_id)}
