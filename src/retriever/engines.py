"""Backward-compatible embedding factory backed by provider interfaces."""

from functools import lru_cache

from src.providers.embedding import (
    LocalSentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from src.providers.factory import get_embedding_provider
from src.providers.protocols import EmbeddingProvider

EmbeddingEngine = EmbeddingProvider
OpenAIEngine = OpenAIEmbeddingProvider
LocalEngine = LocalSentenceTransformerEmbeddingProvider


@lru_cache(maxsize=2)
def create_engine(engine_name: str) -> EmbeddingProvider:
    """Preserve the historical retriever factory API."""
    return get_embedding_provider(engine_name)
