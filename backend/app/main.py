import os
from contextlib import asynccontextmanager

import httpx
from app.config import get_settings
from app.db.models import CONFIG_ACTIVE_STORAGE_BACKEND, AppConfig
from app.db.session import AsyncSessionLocal
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    version="0.4.0-step5",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import admin, collections, documents

app.include_router(admin.router)
app.include_router(collections.router)
app.include_router(documents.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "medical-ai-gateway-backend",
        "replica": os.getenv("HOSTNAME", "unknown"),
    }


@app.get("/ready")
async def ready():
    qdrant_nodes = {
        "qdrant_node_1": os.getenv("QDRANT_NODE_1_URL", "http://qdrant-node1:6333"),
        "qdrant_node_2": os.getenv("QDRANT_NODE_2_URL", "http://qdrant-node2:6333"),
    }
    results = {}
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in qdrant_nodes.items():
            try:
                r = await client.get(f"{url}/healthz")
                results[name] = (
                    "ok" if r.status_code == 200 else f"http {r.status_code}"
                )
            except Exception as exc:
                results[name] = f"unreachable: {type(exc).__name__}"

    all_ok = all(v == "ok" for v in results.values())
    return {"ready": all_ok, "dependencies": results}


@app.get("/config/storage-backend")
async def get_storage_backend():
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
