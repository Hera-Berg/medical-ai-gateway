from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.db.models import InferencePassRole, ThinkingTier


def _q_as_is(question: str) -> str:
    return question


def _q_challenge(question: str) -> str:
    return (
        f"{question} contraindications exceptions caveats conflicting guidance "
        "populations where this does not apply harms risks"
    )


def _q_factcheck(question: str) -> str:
    return (
        f"{question} specific numeric thresholds values evidence quality "
        "study limitations certainty of evidence"
    )


@dataclass(frozen=True)
class PassPlan:
    role: InferencePassRole
    retrieves: bool
    label: str
    query_transform: Callable[[str], str] = _q_as_is


TIER_MULTIPLIER = {
    ThinkingTier.low: 1,
    ThinkingTier.medium: 3,
    ThinkingTier.high: 6,
}

TIER_PLANS: dict[ThinkingTier, list[PassPlan]] = {
    ThinkingTier.low: [
        PassPlan(
            InferencePassRole.direct,
            retrieves=True,
            label="Answer",
            query_transform=_q_as_is,
        ),
    ],
    ThinkingTier.medium: [
        PassPlan(
            InferencePassRole.propose,
            retrieves=True,
            label="Initial answer",
            query_transform=_q_as_is,
        ),
        PassPlan(
            InferencePassRole.challenge,
            retrieves=True,
            label="Model challenging its own answer",
            query_transform=_q_challenge,
        ),
        PassPlan(
            InferencePassRole.reconcile,
            retrieves=True,
            label="Final synthesis",
            query_transform=_q_as_is,
        ),
    ],
    ThinkingTier.high: [
        PassPlan(
            InferencePassRole.propose,
            retrieves=True,
            label="Initial answer",
            query_transform=_q_as_is,
        ),
        PassPlan(
            InferencePassRole.fact_check,
            retrieves=True,
            label="Fact-check pass",
            query_transform=_q_factcheck,
        ),
        PassPlan(
            InferencePassRole.fact_check,
            retrieves=True,
            label="Second retrieval + check",
            query_transform=_q_challenge,
        ),
        PassPlan(
            InferencePassRole.adversarial,
            retrieves=True,
            label="Adversarial self-critique",
            query_transform=_q_challenge,
        ),
        PassPlan(
            InferencePassRole.reconcile,
            retrieves=True,
            label="Cited synthesis",
            query_transform=_q_as_is,
        ),
        PassPlan(
            InferencePassRole.reconcile,
            retrieves=False,
            label="Final polish",
            query_transform=_q_as_is,
        ),
    ],
}
