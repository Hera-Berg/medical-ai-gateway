"""initial schema

Revision ID: 0001_initial
Revises:
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


corpus_type = postgresql.ENUM(
    "authoritative", "personal", name="corpus_type", create_type=False
)
thinking_tier = postgresql.ENUM(
    "low", "medium", "high", name="thinking_tier", create_type=False
)
trace_event_type = postgresql.ENUM(
    "retrieval", "inference_pass", name="trace_event_type", create_type=False
)
inference_pass_role = postgresql.ENUM(
    "propose",
    "challenge",
    "fact_check",
    "adversarial",
    "reconcile",
    "direct",
    name="inference_pass_role",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    corpus_type.create(bind, checkfirst=True)
    thinking_tier.create(bind, checkfirst=True)
    trace_event_type.create(bind, checkfirst=True)
    inference_pass_role.create(bind, checkfirst=True)

    op.create_table(
        "app_config",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("corpus_type", corpus_type, nullable=False),
        sa.Column("qdrant_collection", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "name", "corpus_type", name="uq_collection_name_per_corpus"
        ),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("storage_locator", sa.String(1024), nullable=False),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column("source_version", sa.String(255), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "qdrant_point_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(512), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_chunk_index_per_doc"
        ),
    )

    op.create_table(
        "queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("model_key", sa.String(128), nullable=False),
        sa.Column("thinking_tier", thinking_tier, nullable=False),
        sa.Column(
            "collection_scope",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "query_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("queries.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("n_inference_calls", sa.Integer(), nullable=False),
        sa.Column(
            "total_input_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_output_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column(
            "storage_cost_usd_snapshot", sa.Float(), nullable=False, server_default="0"
        ),
    )

    op.create_table(
        "trace_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("queries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", trace_event_type, nullable=False),
        sa.Column("pass_role", inference_pass_role, nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retrieval_query_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("query_id", "sequence", name="uq_trace_event_sequence"),
    )

    op.create_table(
        "retrieved_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trace_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trace_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("chunk_text_snapshot", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.String(512), nullable=False),
        sa.Column("source_corpus_type", corpus_type, nullable=False),
        sa.Column("source_collection_name", sa.String(255), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_section", sa.String(512), nullable=True),
        sa.Column("source_version", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("retrieved_chunks")
    op.drop_table("trace_events")
    op.drop_table("query_costs")
    op.drop_table("queries")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("collections")
    op.drop_table("app_config")

    bind = op.get_bind()
    inference_pass_role.drop(bind, checkfirst=True)
    trace_event_type.drop(bind, checkfirst=True)
    thinking_tier.drop(bind, checkfirst=True)
    corpus_type.drop(bind, checkfirst=True)
