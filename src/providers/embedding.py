from __future__ import annotations

import time
from typing import Any

import numpy as np
from openai import OpenAI
from tqdm import tqdm

from src.providers.chat import translate_provider_error
from src.providers.errors import ProviderUnavailableError


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        timeout: float,
        max_retries: int,
        base_url: str | None = None,
    ) -> None:
        options: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            options["base_url"] = base_url
        self._client = OpenAI(**options)
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "openai"

    def embed_query(self, query: str) -> np.ndarray:
        try:
            response = self._client.embeddings.create(model=self._model, input=query)
            return np.array(response.data[0].embedding, dtype="float32")
        except Exception as exc:
            raise translate_provider_error(exc, self.name) from exc

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        all_embeddings: list[list[float]] = []
        batch_size = 100
        for offset in tqdm(
            range(0, len(texts), batch_size),
            desc="  OpenAI Embedding",
            unit="batch",
        ):
            batch = texts[offset : offset + batch_size]
            try:
                response = self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                )
            except Exception as exc:
                raise translate_provider_error(exc, self.name) from exc
            sorted_data = sorted(response.data, key=lambda item: item.index)
            all_embeddings.extend(item.embedding for item in sorted_data)
            if offset + batch_size < len(texts):
                time.sleep(0.3)
        return np.array(all_embeddings, dtype="float32")


class LocalSentenceTransformerEmbeddingProvider:
    def __init__(self, *, model: Any, model_name: str, dimension: int) -> None:
        self._model = model
        self._model_name = model_name
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "local"

    def embed_query(self, query: str) -> np.ndarray:
        try:
            vector = self._model.encode(
                query,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return np.asarray(vector, dtype="float32")
        except Exception as exc:
            raise ProviderUnavailableError("local_embedding") from exc

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        try:
            vectors = self._model.encode(
                texts,
                batch_size=64,
                show_progress_bar=True,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return np.asarray(vectors, dtype="float32")
        except Exception as exc:
            raise ProviderUnavailableError("local_embedding") from exc
