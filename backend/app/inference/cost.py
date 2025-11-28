from __future__ import annotations

from app.inference.registry import ModelDescriptor
from app.inference.runpod_client import InferenceResult


def call_cost_usd(model: ModelDescriptor, result: InferenceResult) -> float:
    return (result.billable_ms / 1000.0) * model.per_second_usd
