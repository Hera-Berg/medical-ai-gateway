"""
Cost calculation — TIME-BASED, matching RunPod Serverless's per-second billing.

cost_usd = (billable_ms / 1000) * model.per_second_usd
where billable_ms = delayTime (cold start) + executionTime, both billed by RunPod.

This is deliberately NOT token-based: RunPod bills GPU compute time, not tokens.
Tokens are still recorded (descriptive, shown in the UI) but do not drive cost.
Modelling it correctly is the whole point of a "cost-transparent" tool.
"""
from __future__ import annotations

from app.inference.registry import ModelDescriptor
from app.inference.runpod_client import InferenceResult


def call_cost_usd(model: ModelDescriptor, result: InferenceResult) -> float:
    return (result.billable_ms / 1000.0) * model.per_second_usd
