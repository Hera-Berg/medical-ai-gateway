"""
Application settings, loaded from environment variables.

These mirror the env vars documented in .env.example and wired in
docker-compose.yml. pydantic-settings validates types and provides defaults so
the app fails fast with a clear message if something required is missing.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ────────────────────────────────────────────────────────────
    # Async SQLAlchemy URL. docker-compose injects this pointing at the
    # postgres service; defaults here let tests run against a local DB.
    database_url: str = (
        "postgresql+asyncpg://medgw:change-me-in-production@postgres:5432/medgw"
    )

    # ── Qdrant cluster ──────────────────────────────────────────────────────
    qdrant_node_1_url: str = "http://qdrant-node1:6333"
    qdrant_node_2_url: str = "http://qdrant-node2:6333"

    # ── Storage backend ─────────────────────────────────────────────────────
    # The DEFAULT active backend, used to seed app_config on first boot if the
    # row doesn't exist yet. After that, the value in app_config (DB) wins —
    # it's read on every request and switchable from the settings UI.
    active_storage_backend_default: str = "local"

    # Where LocalStorageBackend writes uploaded PDFs (inside the container;
    # backed by a Docker volume or bind mount in compose).
    local_pdf_storage_path: str = "/data/pdfs"

    # ── RunPod (inference) — unused until step 11 ───────────────────────────
    runpod_api_key: str = ""

    # ── Embeddings (FastEmbed / ONNX) ───────────────────────────────────────
    # CHANGING THE MODEL OR DIMENSION REQUIRES A FULL REINDEX: the vector size is
    # baked into every Qdrant collection at creation. Model + dim live here as a
    # single source of truth; the collection-creation code reads the dim from
    # this value so they can never silently diverge.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    # FastEmbed weights are baked into the image at build time and cached here;
    # build and runtime must agree on this path or the model re-downloads.
    fastembed_cache_dir: str = "/opt/fastembed_cache"
    # BGE models use these prefixes for asymmetric (query vs passage) retrieval.
    embedding_query_prefix: str = "query: "
    embedding_passage_prefix: str = "passage: "

    # ── Chunking ────────────────────────────────────────────────────────────
    chunk_size: int = 800        # characters per chunk
    chunk_overlap: int = 120     # character overlap between adjacent chunks

    # ── AWS (only read when active backend = aws) — unused until step 9 ─────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = ""
    s3_bucket: str = ""

    # AWS storage pricing for the live per-GB cost estimate (USD/GB-month).
    # Defaults are indicative us-east-1 list prices; override via env so they're
    # easy to keep current without code changes. EBS volume sizes for the Qdrant
    # nodes are read from the mounts when AWS mode is active.
    # Break-even comparison anchor for the cost dashboard. Defaults to a $20/mo
    # consumer subscription (e.g. ChatGPT Plus), but configurable so the widget
    # can compare against any baseline (Claude Pro, a Team seat, etc.) — the
    # tool shouldn't bake in one self-serving comparison.
    subscription_comparison_usd_month: float = 20.0
    subscription_comparison_label: str = "$20/mo subscription"


@lru_cache
def get_settings() -> Settings:
    """Cached so we parse the environment once per process."""
    return Settings()
