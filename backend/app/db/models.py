from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from app.db.session import Base
from sqlalchemy import BigInteger, Date, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class CorpusType(str, enum.Enum):
    authoritative = "authoritative"
    personal = "personal"


class ThinkingTier(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TraceEventType(str, enum.Enum):
    retrieval = "retrieval"
    inference_pass = "inference_pass"


class InferencePassRole(str, enum.Enum):
    propose = "propose"
    challenge = "challenge"
    fact_check = "fact_check"
    adversarial = "adversarial"
    reconcile = "reconcile"
    direct = "direct"


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    corpus_type: Mapped[CorpusType] = mapped_column(
        SAEnum(CorpusType, name="corpus_type"), nullable=False
    )
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
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)

    storage_locator: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)

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
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

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


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    thinking_tier: Mapped[ThinkingTier] = mapped_column(
        SAEnum(ThinkingTier, name="thinking_tier"), nullable=False
    )
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

    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_cost_usd_snapshot: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    query: Mapped[Query] = relationship(back_populates="cost")


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[TraceEventType] = mapped_column(
        SAEnum(TraceEventType, name="trace_event_type"), nullable=False
    )

    pass_role: Mapped[InferencePassRole | None] = mapped_column(
        SAEnum(InferencePassRole, name="inference_pass_role"), nullable=True
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    __tablename__ = "retrieved_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trace_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)

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


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


CONFIG_ACTIVE_STORAGE_BACKEND = "active_storage_backend"
