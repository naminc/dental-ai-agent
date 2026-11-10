from __future__ import annotations

import os
from functools import lru_cache

from src.core.settings import Engine, get_settings
from src.providers.chat import OllamaChatProvider, OpenAIChatProvider
from src.providers.embedding import (
    LocalSentenceTransformerEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from src.providers.protocols import ChatProvider, EmbeddingProvider


@lru_cache(maxsize=4)
def get_chat_provider(
    engine: str | None = None,
    model_override: str | None = None,
) -> ChatProvider:
    settings = get_settings()
    selected = engine or settings.llm_engine.value
    if selected == Engine.OPENAI.value:
        api_key = settings.openai_api_key_value
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI chat provider")
        return OpenAIChatProvider(
            api_key=api_key,
            model=model_override or settings.openai_chat_model,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
            base_url=settings.openai_base_url,
        )
    if selected == Engine.LOCAL.value:
        return OllamaChatProvider(
            base_url=settings.ollama_base_url,
            model=model_override or settings.ollama_chat_model,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
        )
    raise ValueError(f"Unsupported chat provider engine: {selected}")


@lru_cache(maxsize=2)
def get_embedding_provider(engine: str | None = None) -> EmbeddingProvider:
    settings = get_settings()
    selected = engine or settings.embedding_engine.value
    if selected == Engine.OPENAI.value:
        api_key = settings.openai_api_key_value
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI embedding provider")
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=settings.openai_embedding_model,
            dimension=settings.openai_embedding_dim,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
            base_url=settings.openai_base_url,
        )
    if selected == Engine.LOCAL.value:
        return LocalSentenceTransformerEmbeddingProvider(
            model=_load_local_embedding_model(),
            model_name=settings.local_embedding_model,
            dimension=settings.local_embedding_dim,
        )
    raise ValueError(f"Unsupported embedding provider engine: {selected}")


@lru_cache(maxsize=1)
def _load_local_embedding_model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "1"
    try:
        return SentenceTransformer(
            settings.local_embedding_model,
            local_files_only=True,
        )
    except Exception:
        return SentenceTransformer(settings.local_embedding_model)


def clear_provider_caches() -> None:
    get_chat_provider.cache_clear()
    get_embedding_provider.cache_clear()
    _load_local_embedding_model.cache_clear()
