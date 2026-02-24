from __future__ import annotations

from app.db.models import Chunk, Collection, Document, Query
from app.db.session import get_db
from app.rag.qdrant_client import QdrantRAG
from app.storage.registry import get_active_backend
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/storage/stats")
async def storage_stats(db: AsyncSession = Depends(get_db)):
    backend = await get_active_backend(db)
    stats = await backend.get_stats()
    over_threshold = (
        stats.disk_usage_percent is not None and stats.disk_usage_percent >= 80.0
    )
    return {
        "backend_name": stats.backend_name,
        "total_bytes": stats.total_bytes,
        "disk_usage_percent": stats.disk_usage_percent,
        "estimated_monthly_cost_usd": stats.estimated_monthly_cost_usd,
        "disk_warning": over_threshold,
    }


@router.get("/cluster")
async def cluster_stats(db: AsyncSession = Depends(get_db)):
    qdrant = QdrantRAG()
    cluster = await qdrant.cluster_info()

    collections = (await db.execute(select(Collection))).scalars().all()
    coll_out = []
    for c in collections:
        try:
            stats = await qdrant.collection_stats(c.qdrant_collection)
        except Exception:
            stats = {}
        shards = await qdrant.collection_shards(c.qdrant_collection)
        coll_out.append(
            {
                "name": c.name,
                "qdrant_collection": c.qdrant_collection,
                "corpus_type": c.corpus_type.value,
                "points_count": stats.get("points_count"),
                "status": stats.get("status"),
                "shard_number": stats.get("shard_number"),
                "replication_factor": stats.get("replication_factor"),
                "shards": shards,
            }
        )

    return {
        "cluster": cluster,
        "collections": coll_out,
        "caveat": (
            "Both Qdrant nodes run on a single host: this demonstrates "
            "distributed sharding + replication topology, not real fault "
            "tolerance (losing the host loses both nodes)."
        ),
    }


@router.get("/database")
async def database_stats(db: AsyncSession = Depends(get_db)):
    counts = {}
    for label, model in [
        ("collections", Collection),
        ("documents", Document),
        ("chunks", Chunk),
        ("queries", Query),
    ]:
        n = (await db.execute(select(func.count()).select_from(model))).scalar_one()
        counts[label] = int(n)

    db_size = None
    try:
        row = (
            await db.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
        ).scalar_one()
        db_size = str(row)
    except Exception:
        db_size = None

    return {"row_counts": counts, "database_size": db_size}
