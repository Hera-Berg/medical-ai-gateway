"""
SQLAlchemy ORM models — the full Postgres schema.

This schema encodes the design decisions made during planning:

  • TRUST BOUNDARY: `collections.corpus_type` is a first-class enum
    (authoritative vs personal). The whole product is cross-corpus comparison,
    so which side a chunk came from is structural, not a tag.

  • GUIDELINE VERSIONING: `documents.source_version` + `published_date` because
    clinical guidelines change (NICE NG28 was amended 2026; an Aug-2025 draft
    revised the medicines section). A chunk's authority depends on its version.

  • PROVENANCE: `chunks` carry page/section + chunk_index so the thinking-panel
    cards can show exactly where evidence came from.

  • COST TRACKING: `queries` + `query_costs` capture model, tier, per-call
    tokens, latency, and USD — the foundation for the dashboard + break-even.

  • RELATIONAL TRACE: `trace_events` (ordered) + `retrieved_chunks` (per event)
    store the unified retrieval+inference timeline as queryable rows, NOT a
    JSON blob — so the "when do extra passes help?" evaluation is SQL, not
    Python post-processing.

  • GLOBAL CONFIG: `app_config` key-value table holds active_storage_backend,
    read by the backend on every request and switchable from the settings UI.

NOTE on access control: there is no auth layer (portfolio piece). The
authoritative corpus is "admin-managed by design" — enforcement is a documented
extension point, not implemented. The schema reflects intent (corpus_type) even
though nothing currently blocks a write.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from app.db.session import Base
from sqlalchemy import BigInteger, Boolean, Date, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class CorpusType(str, enum.Enum):
    """The trust boundary. The single most important distinction in the schema."""

    authoritative = (
        "authoritative"  # curated literature/guidelines; admin-managed by design
    )
    personal = "personal"  # user-supplied (synthetic) records; ephemeral


class ThinkingTier(str, enum.Enum):
    low = "low"  # 1 pass: retrieve -> answer
    medium = "medium"  # 3 passes: propose -> challenge -> reconcile
    high = "high"  # 6 passes: + multi-retrieval/fact-check + adversarial critique


class TraceEventType(str, enum.Enum):
    """
    Each event in the per-query timeline is exactly one of these. The frontend
    renders a collapsible mini-heading per event; clicking expands it.
    """

    retrieval = "retrieval"  # a RAG retrieval; has retrieved_chunks rows
    inference_pass = "inference_pass"  # a RunPod self-call; has prompt + output


class InferencePassRole(str, enum.Enum):
    """For inference_pass events: which role this pass plays in the tier."""

    propose = "propose"
    challenge = "challenge"  # the devil's-advocate pass
    fact_check = "fact_check"
    adversarial = "adversarial"  # "model challenging its own answer"
    reconcile = "reconcile"  # final synthesis
    direct = "direct"  # the single Low-tier pass


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge base: collections -> documents -> chunks
# ─────────────────────────────────────────────────────────────────────────────
class Collection(Base):
    """
    A named group of documents. Maps 1:1 to a Qdrant namespace/collection so RAG
    can be scoped to one collection or run across all. `corpus_type` places it on
    one side of the trust boundary.
    """

    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    corpus_type: Mapped[CorpusType] = mapped_column(
        SAEnum(CorpusType, name="corpus_type"), nullable=False
    )
    # The Qdrant collection name this maps to (derived but stored for clarity).
    qdrant_collection: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", "corpus_type", name="uq_collection_name_per_corpus"),
    )


class Document(Base):
    """
    A single uploaded/seeded file (PDF for now; the FileHandler abstraction lets
    other types be added later). Versioning fields matter for the authoritative
    corpus where guideline editions change.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)

    # Where the bytes live. For LocalStorageBackend this is a host path; for
    # AWSStorageBackend it's an S3 key. The StorageBackend interface abstracts
    # the difference; this column just records the locator.
    storage_locator: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_backend: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'local' | 'aws'

    # ── Provenance / versioning (authoritative corpus especially) ───────────
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    collection: Mapped[Collection] = relationship(back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """
    A text chunk produced from a document. The embedding VECTOR lives in Qdrant
    (keyed by `qdrant_point_id`); Postgres holds the text + metadata needed for
    provenance display and for the inspector's chunk browser.

    We deliberately store the chunk text in BOTH places' worth of need: Qdrant
    payload for retrieval display, and here for relational queries / the
    inspector / re-embedding without re-parsing the PDF.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The point id used in Qdrant for this chunk's vector.
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # order within doc
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Provenance location for the chunk card.
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_index_per_doc"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Query logging, cost, and the relational thinking trace
# ─────────────────────────────────────────────────────────────────────────────
class Query(Base):
    """
    One user query. Holds the request parameters, the final answer, and is the
    parent of the cost row and the ordered trace_events. Survives a chat reset
    (the dashboard accumulates spend across resets — a deliberate demo choice).
    """

    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_key: Mapped[str] = mapped_column(
        String(128), nullable=False
    )  # e.g. 'mistral-7b'
    thinking_tier: Mapped[ThinkingTier] = mapped_column(
        SAEnum(ThinkingTier, name="thinking_tier"), nullable=False
    )
    # Which collections were in scope (list of collection ids). JSONB here is
    # appropriate: it's request metadata, not something we evaluate over.
    collection_scope: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cost: Mapped[QueryCost | None] = relationship(
        back_populates="query", cascade="all, delete-orphan", uselist=False
    )
    trace_events: Mapped[list[TraceEvent]] = relationship(
        back_populates="query",
        cascade="all, delete-orphan",
        order_by="TraceEvent.sequence",
    )


class QueryCost(Base):
    """
    Cost + performance for a query, aggregated across all its inference passes.
    Per-pass detail lives on each inference TraceEvent; this is the roll-up the
    dashboard reads. Storage cost (when AWS active) is captured at query time so
    total platform cost is reconstructable historically.
    """

    __tablename__ = "query_costs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    n_inference_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Snapshot of storage cost context at query time (0 in Local mode).
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_cost_usd_snapshot: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    # True if inference was simulated (MOCK_INFERENCE=1) — i.e. NO GPU was billed
    # and total_cost_usd is a modelled figure, not real spend. Lets the dashboard
    # mark simulated rows so mock numbers are never mistaken for actual cost.
    mocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    query: Mapped[Query] = relationship(back_populates="cost")


class TraceEvent(Base):
    """
    One event in a query's ordered timeline — either a retrieval or an inference
    pass. `sequence` gives the strict order the frontend renders. This is the
    relational backbone of the "Show Thinking" panel.

    For inference_pass events: prompt/output/role/tokens/latency are populated.
    For retrieval events: the event has child retrieved_chunks rows instead.
    """

    __tablename__ = "trace_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 0,1,2,... render order
    event_type: Mapped[TraceEventType] = mapped_column(
        SAEnum(TraceEventType, name="trace_event_type"), nullable=False
    )

    # ── inference_pass fields (null for retrieval events) ───────────────────
    pass_role: Mapped[InferencePassRole | None] = mapped_column(
        SAEnum(InferencePassRole, name="inference_pass_role"), nullable=True
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── retrieval fields (null for inference events) ────────────────────────
    retrieval_query_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    query: Mapped[Query] = relationship(back_populates="trace_events")
    retrieved_chunks: Mapped[list[RetrievedChunk]] = relationship(
        back_populates="trace_event",
        cascade="all, delete-orphan",
        order_by="RetrievedChunk.rank",
    )

    __table_args__ = (
        UniqueConstraint("query_id", "sequence", name="uq_trace_event_sequence"),
    )


class RetrievedChunk(Base):
    """
    A single chunk retrieved during a retrieval event, with its similarity score
    and rank. References the source chunk so the card can show full provenance
    (document, page, corpus_type, version) by joining through.

    We snapshot the chunk text + provenance here rather than only FK-referencing,
    so a query's trace remains faithful even if the underlying document is later
    deleted or re-indexed. The FK is nullable-on-delete for that reason.
    """

    __tablename__ = "retrieved_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trace_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Soft reference: keep the trace if the chunk is later removed.
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = most similar
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0..1

    # Snapshot of provenance at retrieval time (so card survives doc deletion).
    chunk_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_corpus_type: Mapped[CorpusType] = mapped_column(
        SAEnum(CorpusType, name="corpus_type", create_type=False), nullable=False
    )
    source_collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)

    trace_event: Mapped[TraceEvent] = relationship(back_populates="retrieved_chunks")


# ─────────────────────────────────────────────────────────────────────────────
# Global config
# ─────────────────────────────────────────────────────────────────────────────
class AppConfig(Base):
    """
    Key-value global config. The canonical home of `active_storage_backend`,
    read by the backend on every request and switched from the settings UI.
    Generic KV so future global toggles don't need schema changes.
    """

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Well-known config keys (referenced from code so we don't stringly-type them).
CONFIG_ACTIVE_STORAGE_BACKEND = "active_storage_backend"
