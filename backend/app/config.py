from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://medgw:change-me-in-production@postgres:5432/medgw"
    )

    qdrant_node_1_url: str = "http://qdrant-node1:6333"
    qdrant_node_2_url: str = "http://qdrant-node2:6333"

    active_storage_backend_default: str = "local"

    local_pdf_storage_path: str = "/data/pdfs"

    runpod_api_key: str = ""

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    fastembed_cache_dir: str = "/opt/fastembed_cache"
    embedding_query_prefix: str = "query: "
    embedding_passage_prefix: str = "passage: "

    chunk_size: int = 800
    chunk_overlap: int = 120

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = ""
    s3_bucket: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
