from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from fastembed import TextEmbedding


@lru_cache(maxsize=1)
def _get_model() -> TextEmbedding:
    s = get_settings()
    return TextEmbedding(model_name=s.embedding_model, cache_dir=s.fastembed_cache_dir)


class Embedder:
    def __init__(self) -> None:
        s = get_settings()
        self._model = _get_model()
        self._query_prefix = s.embedding_query_prefix
        self._passage_prefix = s.embedding_passage_prefix
        self.dim = s.embedding_dim

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"{self._passage_prefix}{t}" for t in texts]
        return [vec.tolist() for vec in self._model.embed(prefixed)]

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"{self._query_prefix}{text}"
        vec = next(iter(self._model.embed([prefixed])))
        return vec.tolist()
