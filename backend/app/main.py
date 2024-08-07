import os

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Medical AI Gateway",
    description=(
        "Cost-transparent, data-sovereign, domain-specialised RAG. "
        "DEMO & EDUCATIONAL TOOL — NOT MEDICAL ADVICE."
    ),
    version="0.1.0-scaffold",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "medical-ai-gateway-backend",
        "replica": os.getenv("HOSTNAME", "unknown"),  # container id => visible LB
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
            except Exception as exc:  # noqa: BLE001 — scaffold-level reporting
                results[name] = f"unreachable: {type(exc).__name__}"

    all_ok = all(v == "ok" for v in results.values())
    return {"ready": all_ok, "dependencies": results}


@app.get("/")
async def root():
    return {
        "name": "Medical AI Gateway API",
        "disclaimer": "Demo & educational tool. Not medical advice. Not a diagnostic device.",
        "docs": "/docs",
    }
