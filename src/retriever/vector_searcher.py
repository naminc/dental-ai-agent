from __future__ import annotations

import logging
import time

import faiss
import numpy as np

from src.retriever.engines import EmbeddingEngine

logger = logging.getLogger(__name__)


class VectorSearcher:
    """Runs vector similarity search against an injected FAISS index."""

    def __init__(self, index: faiss.Index, embedder: EmbeddingEngine) -> None:
        self.index = index
        self.embedder = embedder

    def embed_query(self, query: str) -> np.ndarray:
        return self.embedder.embed_query(query)

    def search(
        self,
        query: str,
        top_k: int,
        valid_indices: set[int] | None,
        query_label: str = "",
    ) -> list[int]:
        tag = f" [{query_label}]" if query_label else ""
        started = time.perf_counter()
        query_vector = np.array([self.embed_query(query)], dtype="float32")
        logger.info(
            "[TIME-LOG]   Embedding%s mất: %.3fs",
            tag,
            time.perf_counter() - started,
        )

        started = time.perf_counter()
        n_search = min(top_k * 5, self.index.ntotal)
        scores, indices = self.index.search(query_vector, n_search)
        logger.info(
            "[TIME-LOG]   FAISS Search%s mất: %.3fs",
            tag,
            time.perf_counter() - started,
        )

        ranked: list[int] = []
        for _, index in zip(scores[0], indices[0]):
            if index == -1:
                continue
            index = int(index)
            if valid_indices is not None and index not in valid_indices:
                continue
            ranked.append(index)
        return ranked
