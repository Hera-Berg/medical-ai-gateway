"""
Thinking-tier definitions.

A tier is a sequence of PASSES. Each pass either retrieves (RAG) or runs an
inference call, and emits an ordered trace event. Framed honestly as a
DEPTH / THOROUGHNESS dial, not a guaranteed-quality dial (see architecture.md):
more passes = more retrieval + more scrutiny + more citations, instrumented so
the "when do extra passes help?" question is answerable, not asserted.

  Low    (1 pass) : retrieve -> answer directly
  Medium (3 passes): propose -> challenge (devil's advocate) -> reconcile
  High   (6 passes): propose -> fact_check -> fact_check -> adversarial ->
                     reconcile -> reconcile(polish)

KEY MECHANIC — per-pass retrieval reframing:
Each pass retrieves with a query REFRAMED for its role, not the original question
verbatim. This is what lets a later pass surface evidence an earlier pass missed
(e.g. the challenge pass searches for contradictions/exceptions). Without this,
all passes see identical chunks and self-critique just re-argues the same
evidence — the failure mode where extra passes add cost but not information.

The reframe is a CONSERVATIVE heuristic (append role-oriented terms, don't
discard the question). It's not guaranteed-better; it's instrumented so you can
measure whether the reframed retrieval actually pulls new, useful chunks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.db.models import InferencePassRole, ThinkingTier


# ── per-role retrieval query transforms ─────────────────────────────────────
def _q_as_is(question: str) -> str:
    return question


def _q_challenge(question: str) -> str:
    # steer retrieval toward dissenting / limiting evidence
    return (
        f"{question} contraindications exceptions caveats conflicting guidance "
        "populations where this does not apply harms risks"
    )


def _q_factcheck(question: str) -> str:
    # steer toward specifics that verify or refute precise claims
    return (
        f"{question} specific numeric thresholds values evidence quality "
        "study limitations certainty of evidence"
    )


@dataclass(frozen=True)
class PassPlan:
    role: InferencePassRole
    # whether this pass re-retrieves RAG context before its inference call
    retrieves: bool
    # short description shown in the thinking panel mini-heading
    label: str
    # how to reframe the retrieval query for this pass's role
    query_transform: Callable[[str], str] = _q_as_is


# Cost-multiplier hints (indicative, shown pre-submit; real cost logged after).
TIER_MULTIPLIER = {
    ThinkingTier.low: 1,
    ThinkingTier.medium: 3,
    ThinkingTier.high: 6,
}

TIER_PLANS: dict[ThinkingTier, list[PassPlan]] = {
    ThinkingTier.low: [
        PassPlan(InferencePassRole.direct, retrieves=True, label="Answer", query_transform=_q_as_is),
    ],
    ThinkingTier.medium: [
        PassPlan(
            InferencePassRole.propose, retrieves=True, label="Initial answer",
            query_transform=_q_as_is,
        ),
        PassPlan(
            InferencePassRole.challenge, retrieves=True,
            label="Model challenging its own answer",
            query_transform=_q_challenge,
        ),
        PassPlan(
            InferencePassRole.reconcile, retrieves=True, label="Final synthesis",
            query_transform=_q_as_is,
        ),
    ],
    ThinkingTier.high: [
        PassPlan(
            InferencePassRole.propose, retrieves=True, label="Initial answer",
            query_transform=_q_as_is,
        ),
        PassPlan(
            InferencePassRole.fact_check, retrieves=True, label="Fact-check pass",
            query_transform=_q_factcheck,
        ),
        PassPlan(
            InferencePassRole.fact_check, retrieves=True,
            label="Second retrieval + check",
            query_transform=_q_challenge,
        ),
        PassPlan(
            InferencePassRole.adversarial, retrieves=True,
            label="Adversarial self-critique",
            query_transform=_q_challenge,
        ),
        PassPlan(
            InferencePassRole.reconcile, retrieves=True, label="Cited synthesis",
            query_transform=_q_as_is,
        ),
        PassPlan(
            InferencePassRole.reconcile, retrieves=False, label="Final polish",
            query_transform=_q_as_is,
        ),
    ],
}
