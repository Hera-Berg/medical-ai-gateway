"""
Settings router — the active storage backend control (step 10).

  GET  /settings/storage           current backend + available options + labels
  GET  /settings/storage/readiness/{name}   probe whether a backend is usable
  POST /settings/storage           switch the active backend (writes app_config)

Switching only updates app_config.active_storage_backend. The per-request
resolver (get_active_backend) reads that on the next request, so the switch
takes effect immediately with no restart. Switching does NOT migrate existing
data — the UI warns about this and requires confirmation; enforcement of "fresh
index" is simply that the new backend starts empty (old vectors/files remain in
the old backend, unreferenced).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CONFIG_ACTIVE_STORAGE_BACKEND, AppConfig
from app.db.session import get_db
from app.storage.registry import available_backends, get_backend

router = APIRouter(prefix="/settings", tags=["settings"])

# UI metadata per backend (labels straight from the spec).
BACKEND_META = {
    "local": {
        "label": "Local Storage",
        "tagline": "not recommended for large datasets",
        "description": "Qdrant writes to Docker volumes on this host; PDFs on local disk.",
        "requires_config": False,
    },
    "aws": {
        "label": "AWS Storage",
        "tagline": "scalable, pay-per-GB",
        "description": "PDFs in S3; Qdrant node data on EBS-mounted paths. Requires AWS configuration.",
        "requires_config": True,
    },
}


async def _current(db: AsyncSession) -> str:
    row = await db.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
    return row.value if row else "local"


@router.get("/storage")
async def get_storage_settings(db: AsyncSession = Depends(get_db)):
    current = await _current(db)
    options = []
    for name in available_backends():
        meta = BACKEND_META.get(name, {"label": name, "tagline": "", "description": "", "requires_config": False})
        options.append({"name": name, **meta})
    return {"active": current, "options": options}


@router.get("/storage/readiness/{name}")
async def storage_readiness(name: str):
    """Probe whether a backend is usable right now (used before switching)."""
    try:
        backend = get_backend(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    r = await backend.check_ready()
    return {"name": name, "ready": r.ready, "detail": r.detail}


class SwitchRequest(BaseModel):
    backend: str
    confirm: bool = False  # UI sets true after the fresh-index warning


@router.post("/storage")
async def switch_storage_backend(
    body: SwitchRequest, db: AsyncSession = Depends(get_db)
):
    if body.backend not in available_backends():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{body.backend}'. Available: {available_backends()}",
        )
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required: switching starts a fresh index.",
        )

    # Safety: don't switch INTO a backend that isn't ready (e.g. AWS misconfigured).
    backend = get_backend(body.backend)
    readiness = await backend.check_ready()
    if not readiness.ready:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot switch to '{body.backend}': {readiness.detail}",
        )

    row = await db.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
    if row is None:
        row = AppConfig(key=CONFIG_ACTIVE_STORAGE_BACKEND, value=body.backend)
        db.add(row)
    else:
        row.value = body.backend
    await db.commit()

    return {"active": body.backend, "detail": readiness.detail}
