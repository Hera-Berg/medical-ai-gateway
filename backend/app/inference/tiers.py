from __future__ import annotations

from dataclasses import dataclass

from app.db.models import InferencePassRole, ThinkingTier


@dataclass(frozen=True)
class PassPlan:
    role: InferencePassRole
    retrieves: bool
    label: str


TIER_MULTIPLIER = {
    ThinkingTier.low: 1,
    ThinkingTier.medium: 3,
    ThinkingTier.high: 6,
}

TIER_PLANS: dict[ThinkingTier, list[PassPlan]] = {
    ThinkingTier.low: [
        PassPlan(InferencePassRole.direct, retrieves=True, label="Answer"),
    ],
    ThinkingTier.medium: [
        PassPlan(InferencePassRole.propose, retrieves=True, label="Initial answer"),
        PassPlan(
            InferencePassRole.challenge,
            retrieves=True,
            label="Model challenging its own answer",
        ),
        PassPlan(InferencePassRole.reconcile, retrieves=True, label="Final synthesis"),
    ],
    ThinkingTier.high: [
        PassPlan(InferencePassRole.propose, retrieves=True, label="Initial answer"),
        PassPlan(InferencePassRole.fact_check, retrieves=True, label="Fact-check pass"),
        PassPlan(
            InferencePassRole.fact_check,
            retrieves=True,
            label="Second retrieval + check",
        ),
        PassPlan(
            InferencePassRole.adversarial,
            retrieves=True,
            label="Adversarial self-critique",
        ),
        PassPlan(InferencePassRole.reconcile, retrieves=True, label="Cited synthesis"),
        PassPlan(InferencePassRole.reconcile, retrieves=False, label="Final polish"),
    ],
}
