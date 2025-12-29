from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models import InferencePassRole, ThinkingTier
from app.inference.cost import call_cost_usd
from app.inference.registry import ModelDescriptor
from app.inference.runpod_client import InferenceResult, RunPodClient
from app.inference.tiers import TIER_PLANS
from app.rag.retriever import RetrievedItem, Retriever


@dataclass
class TraceRetrieval:
    sequence: int
    query_text: str
    items: list[RetrievedItem]


@dataclass
class TracePass:
    sequence: int
    role: InferencePassRole
    label: str
    prompt: str
    output: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


@dataclass
class OrchestratorResult:
    final_answer: str
    events: list[object] = field(default_factory=list)
    n_inference_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    mocked: bool = False


_SYSTEM = (
    "You are a clinical literature assistant. Answer ONLY using the provided "
    "context passages. For each claim, indicate whether it came from an "
    "AUTHORITATIVE source (published guideline/literature) or the PERSONAL "
    "record. If the context does not contain the answer, say so. This is an "
    "educational tool, not medical advice; remind the user to consult a clinician."
)


def _format_context(items: list[RetrievedItem]) -> str:
    if not items:
        return "(no relevant passages retrieved)"
    lines = []
    for i, it in enumerate(items, 1):
        src = f"[{it.source_corpus_type.upper()}] {it.source_filename}"
        if it.source_page is not None:
            src += f" p.{it.source_page}"
        lines.append(f"{i}. {src} (sim {it.similarity_score:.2f}):\n{it.text}")
    return "\n\n".join(lines)


class Orchestrator:
    def __init__(
        self,
        *,
        retriever: Retriever | None = None,
        client: RunPodClient | None = None,
        retrieval_limit: int = 5,
    ):
        self._retriever = retriever or Retriever()
        self._client = client or RunPodClient()
        self._k = retrieval_limit

    async def run(
        self,
        *,
        question: str,
        model: ModelDescriptor,
        tier: ThinkingTier,
        qdrant_collections: list[str],
    ) -> OrchestratorResult:
        plans = TIER_PLANS[tier]
        result = OrchestratorResult(final_answer="")
        seq = 0
        last_output = ""
        last_items: list[RetrievedItem] = []

        for plan in plans:
            items: list[RetrievedItem] = []
            if plan.retrieves:

                retrieval_query = plan.query_transform(question)
                items = await self._retriever.retrieve(
                    query_text=retrieval_query,
                    collections=qdrant_collections,
                    limit=self._k,
                )
                last_items = items
                result.events.append(
                    TraceRetrieval(
                        sequence=seq, query_text=retrieval_query, items=items
                    )
                )
                seq += 1
            else:
                items = last_items

            prompt = self._build_prompt(
                role=plan.role,
                question=question,
                context=_format_context(items),
                prior=last_output,
            )
            inf: InferenceResult = await self._client.generate(
                model=model, prompt=prompt
            )
            cost = call_cost_usd(model, inf)

            result.events.append(
                TracePass(
                    sequence=seq,
                    role=plan.role,
                    label=plan.label,
                    prompt=prompt,
                    output=inf.text,
                    input_tokens=inf.input_tokens,
                    output_tokens=inf.output_tokens,
                    cost_usd=cost,
                    latency_ms=inf.billable_ms,
                )
            )
            seq += 1

            result.n_inference_calls += 1
            result.total_input_tokens += inf.input_tokens
            result.total_output_tokens += inf.output_tokens
            result.total_cost_usd += cost
            result.total_latency_ms += inf.billable_ms
            result.mocked = result.mocked or inf.mocked
            last_output = inf.text

        result.final_answer = last_output
        return result

    def _build_prompt(
        self,
        *,
        role: InferencePassRole,
        question: str,
        context: str,
        prior: str,
    ) -> str:
        ctx = f"CONTEXT PASSAGES:\n{context}\n\n"
        if role in (InferencePassRole.direct, InferencePassRole.propose):
            return f"{_SYSTEM}\n\n{ctx}QUESTION: {question}\n\nAnswer:"
        if role == InferencePassRole.challenge:
            return (
                f"{_SYSTEM}\n\n{ctx}QUESTION: {question}\n\n"
                f"A draft answer was:\n{prior}\n\n"
                "Acting as a devil's advocate, identify any claim not supported by "
                "the context, anything contradicted by a passage, or missing "
                "caveats. Cite the passages."
            )
        if role in (InferencePassRole.fact_check, InferencePassRole.adversarial):
            return (
                f"{_SYSTEM}\n\n{ctx}QUESTION: {question}\n\n"
                f"Prior reasoning:\n{prior}\n\n"
                "Rigorously check each claim against the context. Flag unsupported "
                "or overstated claims."
            )
        return (
            f"{_SYSTEM}\n\n{ctx}QUESTION: {question}\n\n"
            f"Prior analysis (including critiques):\n{prior}\n\n"
            "Produce a final, grounded answer that incorporates the critiques, "
            "cites authoritative vs personal sources, and notes uncertainty."
        )
