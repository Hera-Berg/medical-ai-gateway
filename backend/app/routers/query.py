from __future__ import annotations

import uuid

from app.db.models import (
    CONFIG_ACTIVE_STORAGE_BACKEND,
    AppConfig,
    Collection,
    CorpusType,
    Query,
    QueryCost,
    RetrievedChunk,
    ThinkingTier,
    TraceEvent,
    TraceEventType,
)
from app.db.session import get_db
from app.inference.orchestrator import Orchestrator, TracePass, TraceRetrieval
from app.inference.registry import all_models, default_model_key, get_model
from app.inference.tiers import TIER_MULTIPLIER
from app.rag.retriever import RetrievedItem
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/query", tags=["query"])

_ENABLED_TIERS = {ThinkingTier.low}


@router.get("/models")
async def list_models():
    return {
        "default": default_model_key(),
        "models": [
            {
                "key": m.key,
                "display_name": m.display_name,
                "gpu_tier": m.gpu_tier,
                "per_second_usd": m.per_second_usd,
                "capability_hint": m.capability_hint,
            }
            for m in all_models()
        ],
        "tiers": [
            {"key": t.value, "multiplier": mult, "enabled": t in _ENABLED_TIERS}
            for t, mult in TIER_MULTIPLIER.items()
        ],
    }


class QueryRequest(BaseModel):
    model_config = {"protected_namespaces": ()}

    question: str
    model_key: str | None = None
    thinking_tier: ThinkingTier = ThinkingTier.low
    collection_ids: list[uuid.UUID] | None = None


@router.post("")
async def run_query(body: QueryRequest, db: AsyncSession = Depends(get_db)):
    if body.thinking_tier not in _ENABLED_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Thinking tier '{body.thinking_tier.value}' is not enabled yet "
            "(Medium/High arrive in step 12).",
        )

    model = get_model(body.model_key or default_model_key())

    stmt = select(Collection)
    if body.collection_ids:
        stmt = stmt.where(Collection.id.in_(body.collection_ids))
    collections = (await db.execute(stmt)).scalars().all()
    if not collections:
        raise HTTPException(status_code=400, detail="No collections in scope.")
    qdrant_names = [c.qdrant_collection for c in collections]

    orch = Orchestrator()
    run = await orch.run(
        question=body.question,
        model=model,
        tier=body.thinking_tier,
        qdrant_collections=qdrant_names,
    )

    cfg = await db.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
    active_backend = cfg.value if cfg else "local"

    query = Query(
        id=uuid.uuid4(),
        question=body.question,
        final_answer=run.final_answer,
        model_key=model.key,
        thinking_tier=body.thinking_tier,
        collection_scope=[str(c.id) for c in collections],
    )
    db.add(query)

    for ev in run.events:
        if isinstance(ev, TraceRetrieval):
            te = TraceEvent(
                id=uuid.uuid4(),
                query_id=query.id,
                sequence=ev.sequence,
                event_type=TraceEventType.retrieval,
                retrieval_query_text=ev.query_text,
            )
            db.add(te)
            for rank, it in enumerate(ev.items):
                db.add(
                    RetrievedChunk(
                        id=uuid.uuid4(),
                        trace_event_id=te.id,
                        chunk_id=uuid.UUID(it.chunk_id) if it.chunk_id else None,
                        rank=rank,
                        similarity_score=it.similarity_score,
                        chunk_text_snapshot=it.text,
                        source_filename=it.source_filename,
                        source_corpus_type=(
                            CorpusType(it.source_corpus_type)
                            if it.source_corpus_type in ("authoritative", "personal")
                            else CorpusType.authoritative
                        ),
                        source_collection_name=it.source_collection_name,
                        source_page=it.source_page,
                        source_section=it.source_section,
                        source_version=it.source_version,
                    )
                )
        elif isinstance(ev, TracePass):
            db.add(
                TraceEvent(
                    id=uuid.uuid4(),
                    query_id=query.id,
                    sequence=ev.sequence,
                    event_type=TraceEventType.inference_pass,
                    pass_role=ev.role,
                    prompt=ev.prompt,
                    output=ev.output,
                    input_tokens=ev.input_tokens,
                    output_tokens=ev.output_tokens,
                    cost_usd=ev.cost_usd,
                    latency_ms=ev.latency_ms,
                )
            )

    db.add(
        QueryCost(
            id=uuid.uuid4(),
            query_id=query.id,
            n_inference_calls=run.n_inference_calls,
            total_input_tokens=run.total_input_tokens,
            total_output_tokens=run.total_output_tokens,
            total_cost_usd=run.total_cost_usd,
            total_latency_ms=run.total_latency_ms,
            storage_backend=active_backend,
            storage_cost_usd_snapshot=0.0,
        )
    )
    await db.commit()

    events_out = []
    for ev in run.events:
        if isinstance(ev, TraceRetrieval):
            events_out.append(
                {
                    "type": "retrieval",
                    "sequence": ev.sequence,
                    "query_text": ev.query_text,
                    "chunks": [
                        {
                            "rank": r,
                            "text": it.text,
                            "similarity_percent": round(it.similarity_score * 100, 1),
                            "source_filename": it.source_filename,
                            "source_corpus_type": it.source_corpus_type,
                            "source_page": it.source_page,
                            "source_version": it.source_version,
                        }
                        for r, it in enumerate(ev.items)
                    ],
                }
            )
        elif isinstance(ev, TracePass):
            events_out.append(
                {
                    "type": "inference_pass",
                    "sequence": ev.sequence,
                    "role": ev.role.value,
                    "label": ev.label,
                    "output": ev.output,
                    "input_tokens": ev.input_tokens,
                    "output_tokens": ev.output_tokens,
                    "cost_usd": ev.cost_usd,
                    "latency_ms": ev.latency_ms,
                }
            )

    return {
        "query_id": str(query.id),
        "answer": run.final_answer,
        "model": {
            "key": model.key,
            "display_name": model.display_name,
            "gpu_tier": model.gpu_tier,
        },
        "thinking_tier": body.thinking_tier.value,
        "mocked": run.mocked,
        "trace_events": events_out,
        "cost": {
            "n_inference_calls": run.n_inference_calls,
            "total_input_tokens": run.total_input_tokens,
            "total_output_tokens": run.total_output_tokens,
            "total_cost_usd": run.total_cost_usd,
            "total_latency_ms": run.total_latency_ms,
        },
    }
