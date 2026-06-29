"""
Cost dashboard router — aggregates the QueryCost rows written by /query.

  GET /costs/summary    totals, averages, cold-start share, break-even
  GET /costs/by-model   per-model spend/count/avg
  GET /costs/by-tier    per-tier spend/count/avg
  GET /costs/timeline   spend bucketed by day
  GET /costs/recent     recent per-query rows for the history table

COST MODEL: everything here is TIME-BASED (RunPod bills per GPU-second).
total_cost_usd on each row already reflects billable seconds × per-second rate.
The break-even compares measured average cost/query against a configurable
monthly subscription anchor — honest because it's computed from real logged
spend, not assumptions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Query, QueryCost
from app.db.session import get_db

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/summary")
async def cost_summary(db: AsyncSession = Depends(get_db)):
    s = get_settings()

    totals = (
        await db.execute(
            select(
                func.count(QueryCost.id),
                func.coalesce(func.sum(QueryCost.total_cost_usd), 0.0),
                func.coalesce(func.sum(QueryCost.total_input_tokens), 0),
                func.coalesce(func.sum(QueryCost.total_output_tokens), 0),
                func.coalesce(func.avg(QueryCost.total_cost_usd), 0.0),
                func.coalesce(func.avg(QueryCost.total_latency_ms), 0.0),
                func.coalesce(func.sum(QueryCost.n_inference_calls), 0),
            )
        )
    ).one()
    (n_queries, total_cost, in_tok, out_tok, avg_cost, avg_latency, n_calls) = totals

    # How many of those query-costs were simulated (no GPU billed)? Lets the
    # dashboard be honest about whether the spend shown is real or modelled.
    n_mocked = (
        await db.execute(
            select(func.count(QueryCost.id)).where(QueryCost.mocked.is_(True))
        )
    ).scalar_one()

    # Break-even: how many queries/month before per-query cost beats the sub.
    sub = s.subscription_comparison_usd_month
    avg_cost_f = float(avg_cost)
    break_even_queries = (sub / avg_cost_f) if avg_cost_f > 0 else None

    return {
        "n_queries": int(n_queries),
        "n_mocked": int(n_mocked),
        "all_mocked": int(n_mocked) == int(n_queries) and int(n_queries) > 0,
        "any_mocked": int(n_mocked) > 0,
        "total_cost_usd": round(float(total_cost), 6),
        "total_input_tokens": int(in_tok),
        "total_output_tokens": int(out_tok),
        "avg_cost_per_query_usd": round(avg_cost_f, 6),
        "avg_latency_ms": round(float(avg_latency), 1),
        "total_inference_calls": int(n_calls),
        "break_even": {
            "subscription_usd_month": sub,
            "subscription_label": s.subscription_comparison_label,
            "queries_per_month_to_break_even": (
                round(break_even_queries, 1) if break_even_queries else None
            ),
            "explanation": (
                "At the measured average cost per query, this many queries per "
                "month would cost the same as the subscription. Below it, "
                "per-second self-hosting is cheaper; above it, the subscription "
                "wins. Computed from real logged spend."
            ),
        },
    }


@router.get("/by-model")
async def cost_by_model(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(
                Query.model_key,
                func.count(QueryCost.id),
                func.coalesce(func.sum(QueryCost.total_cost_usd), 0.0),
                func.coalesce(func.avg(QueryCost.total_cost_usd), 0.0),
            )
            .join(Query, Query.id == QueryCost.query_id)
            .group_by(Query.model_key)
            .order_by(func.sum(QueryCost.total_cost_usd).desc())
        )
    ).all()
    return {
        "by_model": [
            {
                "model_key": r[0],
                "n_queries": int(r[1]),
                "total_cost_usd": round(float(r[2]), 6),
                "avg_cost_usd": round(float(r[3]), 6),
            }
            for r in rows
        ]
    }


@router.get("/by-tier")
async def cost_by_tier(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(
                Query.thinking_tier,
                func.count(QueryCost.id),
                func.coalesce(func.sum(QueryCost.total_cost_usd), 0.0),
                func.coalesce(func.avg(QueryCost.total_cost_usd), 0.0),
                func.coalesce(func.avg(QueryCost.n_inference_calls), 0.0),
            )
            .join(Query, Query.id == QueryCost.query_id)
            .group_by(Query.thinking_tier)
        )
    ).all()
    return {
        "by_tier": [
            {
                "tier": r[0].value if hasattr(r[0], "value") else str(r[0]),
                "n_queries": int(r[1]),
                "total_cost_usd": round(float(r[2]), 6),
                "avg_cost_usd": round(float(r[3]), 6),
                "avg_inference_calls": round(float(r[4]), 1),
            }
            for r in rows
        ]
    }


@router.get("/timeline")
async def cost_timeline(db: AsyncSession = Depends(get_db)):
    # bucket by calendar day (UTC). func.date works on both sqlite & postgres.
    rows = (
        await db.execute(
            select(
                func.date(Query.created_at).label("day"),
                func.count(QueryCost.id),
                func.coalesce(func.sum(QueryCost.total_cost_usd), 0.0),
            )
            .join(Query, Query.id == QueryCost.query_id)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    return {
        "timeline": [
            {"day": str(r[0]), "n_queries": int(r[1]), "cost_usd": round(float(r[2]), 6)}
            for r in rows
        ]
    }


@router.get("/recent")
async def recent_queries(limit: int = 25, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(Query, QueryCost)
            .join(QueryCost, QueryCost.query_id == Query.id)
            .order_by(Query.created_at.desc())
            .limit(limit)
        )
    ).all()
    return {
        "recent": [
            {
                "query_id": str(q.id),
                "question": q.question,
                "model_key": q.model_key,
                "thinking_tier": q.thinking_tier.value,
                "n_inference_calls": c.n_inference_calls,
                "total_cost_usd": round(c.total_cost_usd, 6),
                "total_latency_ms": c.total_latency_ms,
                "mocked": c.mocked,
                "created_at": q.created_at.isoformat(),
            }
            for q, c in rows
        ]
    }
