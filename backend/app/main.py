"""
Medical AI Gateway — FastAPI backend.

SCAFFOLD STAGE: this is a deliberately minimal but *runnable* app. It exposes a
health check and a readiness check that pings Postgres and both Qdrant nodes, so
that `docker-compose up` lets you confirm the whole topology is wired correctly
before any real feature code exists.

Later build steps fill in: storage backends, RAG pipeline, inference
orchestration, cost tracking, and the feature routers.
"""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.db.models import CONFIG_ACTIVE_STORAGE_BACKEND, AppConfig
from app.db.session import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup, ensure app_config has an active_storage_backend row. We seed it
    from ACTIVE_STORAGE_BACKEND_DEFAULT only if absent — after that, the DB value
    is authoritative and is switched from the settings UI. Idempotent across
    replica restarts.
    """
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        existing = await session.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
        if existing is None:
            session.add(
                AppConfig(
                    key=CONFIG_ACTIVE_STORAGE_BACKEND,
                    value=settings.active_storage_backend_default,
                )
            )
            await session.commit()
    yield


app = FastAPI(
    title="Medical AI Gateway",
    description=(
        "Cost-transparent, data-sovereign, domain-specialised RAG. "
        "DEMO & EDUCATIONAL TOOL — NOT MEDICAL ADVICE."
    ),
    version="0.8.0-step13",
    lifespan=lifespan,
)

# No auth by design (portfolio piece). CORS is open; the only real ingress is
# via Nginx behind the Cloudflare tunnel anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from app.routers import (  # noqa: E402
    admin,
    collections,
    costs,
    documents,
    inspector,
    query,
    settings,
)

app.include_router(admin.router)
app.include_router(collections.router)
app.include_router(costs.router)
app.include_router(documents.router)
app.include_router(inspector.router)
app.include_router(query.router)
app.include_router(settings.router)


@app.get("/health")
async def health():
    """Liveness: is this backend replica up at all?"""
    return {
        "status": "ok",
        "service": "medical-ai-gateway-backend",
        "replica": os.getenv("HOSTNAME", "unknown"),  # container id => visible LB
    }


@app.get("/ready")
async def ready():
    """
    Readiness: can this replica reach its dependencies?
    Pings Postgres (via a trivial TCP-ish check through asyncpg later; for the
    scaffold we just check the two Qdrant nodes' HTTP APIs, which is enough to
    prove the distributed cluster is alive and reachable on the Docker network).
    """
    qdrant_nodes = {
        "qdrant_node_1": os.getenv("QDRANT_NODE_1_URL", "http://qdrant-node1:6333"),
        "qdrant_node_2": os.getenv("QDRANT_NODE_2_URL", "http://qdrant-node2:6333"),
    }
    results = {}
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in qdrant_nodes.items():
            try:
                r = await client.get(f"{url}/healthz")
                results[name] = "ok" if r.status_code == 200 else f"http {r.status_code}"
            except Exception as exc:  # noqa: BLE001 — scaffold-level reporting
                results[name] = f"unreachable: {type(exc).__name__}"

    all_ok = all(v == "ok" for v in results.values())
    return {"ready": all_ok, "dependencies": results}


@app.get("/config/storage-backend")
async def get_storage_backend():
    """
    Read the active storage backend from app_config. Proves the DB layer +
    startup seed work end to end. The real settings router (step 10) adds the
    switch-with-confirmation flow; this is read-only.
    """
    async with AsyncSessionLocal() as session:
        row = await session.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
        return {
            "active_storage_backend": row.value if row else None,
            "seeded": row is not None,
        }


@app.get("/")
async def root():
    return {
        "name": "Medical AI Gateway API",
        "disclaimer": "Demo & educational tool. Not medical advice. Not a diagnostic device.",
        "docs": "/docs",
    }
