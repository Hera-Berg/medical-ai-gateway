from __future__ import annotations

from app.db.session import get_db
from app.storage.registry import get_active_backend
from fastapi import APIRouter, Depends
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
