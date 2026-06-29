"""
Admin router (begun at step 4; expanded at step 15 with Qdrant + PG stats).

Exposes operational internals for the admin panel:
  • storage/stats   — active backend usage + cost (from step 4/10)
  • cluster         — Qdrant cluster topology + per-collection shard placement
  • database        — Postgres table row counts + DB size

HONEST CAVEAT (surfaced in the UI too): the 2-node Qdrant "cluster" runs on a
single host, so it demonstrates the distributed *topology* (sharding +
replication placement) but is NOT real fault tolerance — losing the host loses
both nodes. This is a deliberate, documented demo limitation.
"""
from __future__ import annotations

import os
import socket

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Collection, Document, Query
from app.db.session import get_db
from app.rag.qdrant_client import QdrantRAG
from app.storage.registry import get_active_backend

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/whoami")
async def whoami():
    """
    Identify which backend replica served this request. With multiple backend
    replicas behind the Nginx load balancer, hitting this repeatedly returns
    rotating hostnames (Docker sets the container hostname to the container ID),
    making round-robin load balancing visible. Single-replica → constant value.
    """
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
    }


@router.get("/storage/stats")
async def storage_stats(db: AsyncSession = Depends(get_db)):
    """Current storage usage + cost for the active backend."""
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
        "disk_warning": over_threshold,  # UI shows the warning when true
    }


@router.get("/cluster")
async def cluster_stats(db: AsyncSession = Depends(get_db)):
    """Qdrant cluster topology + per-collection shard placement."""
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
    """Postgres row counts per table + total DB size."""
    counts = {}
    for label, model in [
        ("collections", Collection),
        ("documents", Document),
        ("chunks", Chunk),
        ("queries", Query),
    ]:
        n = (await db.execute(select(func.count()).select_from(model))).scalar_one()
        counts[label] = int(n)

    # DB size (Postgres-specific; degrade gracefully if unavailable)
    db_size = None
    try:
        row = (
            await db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
        ).scalar_one()
        db_size = str(row)
    except Exception:
        db_size = None

    return {"row_counts": counts, "database_size": db_size}
