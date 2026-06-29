"""
Embedder — FastEmbed (ONNX, no PyTorch) wrapper.

Two methods on purpose, because BGE models do ASYMMETRIC retrieval:
  • embed_passages() — for document chunks at ingestion time (passage prefix)
  • embed_query()    — for the user's search at retrieval time (query prefix)
Using the right prefix on each side materially improves retrieval quality for
the short-question / long-chunk pattern this app is built around. Embedding both
sides identically is a subtle, hard-to-spot quality regression — hence two
methods rather than one.

Model + dimension come from config (single source of truth). Weights are baked
into the image at build time and loaded from fastembed_cache_dir, so first
query at runtime is fast and works offline.

The model is loaded lazily and cached at module level: loading ONNX weights
costs ~1s, so we do it once per process, not per request.
"""
from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

from app.config import get_settings


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
        """Embed document chunks for storage. Applies the passage prefix."""
        prefixed = [f"{self._passage_prefix}{t}" for t in texts]
        return [vec.tolist() for vec in self._model.embed(prefixed)]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query. Applies the query prefix."""
        prefixed = f"{self._query_prefix}{text}"
        # embed() takes an iterable and returns a generator; take the first.
        vec = next(iter(self._model.embed([prefixed])))
        return vec.tolist()
